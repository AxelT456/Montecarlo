#!/usr/bin/env python
import pika
import json
import sys
import numpy as np
import random
from common.broker import RabbitMQBroker

class Worker(RabbitMQBroker):
    """
    El Worker consume lotes de trabajo, calcula su parte de Pi, 
    y publica los resultados.
    """
    def __init__(self, host='localhost', user=None, password=None):
        super().__init__(host=host, user=user, password=password)
        
        # Identificador único para este worker (para el dashboard)
        self.worker_id = f"worker-{random.randint(1000, 9999)}"
        print(f"[*] Iniciando {self.worker_id}...")

        # Colas que usaremos
        self.cola_trabajo = 'cola_escenarios'
        self.cola_resultados = 'cola_resultados'
        self.cola_puntos_visuales = 'cola_puntos_visuales'
        
        # Conectar y declarar colas
        self.connect()
        self.declare_queues()

    def declare_queues(self):
        """Declara todas las colas para asegurarse de que existan."""
        self.declare_queue(self.cola_trabajo, durable=True)
        self.declare_queue(self.cola_resultados, durable=True)
        self.declare_queue(self.cola_puntos_visuales, durable=True)

    def procesar_lote(self, dardos_a_lanzar):
        """
        Realiza la simulación de Montecarlo para un lote.
        Usa Numpy para alta velocidad.
        """
        # Generar 'n' puntos (x, y) aleatorios entre 0 y 1
        # [x_coords], [y_coords]
        puntos = np.random.rand(2, dardos_a_lanzar)
        
        # Calcular la distancia al origen (x^2 + y^2)
        distancias = np.square(puntos[0]) + np.square(puntos[1])
        
        # Contar cuántos cayeron dentro del círculo (distancia < 1)
        aciertos_circulo = np.sum(distancias < 1)
        
        # --- Para el dashboard visual ---
        # Tomamos una pequeña muestra (ej. 100 puntos) para no saturar la red
        sample_size = min(dardos_a_lanzar, 100)
        indices_muestra = np.random.choice(dardos_a_lanzar, sample_size, replace=False)
        
        # Obtenemos los puntos de la muestra
        puntos_muestra = puntos[:, indices_muestra].T # Transponer para tener pares (x,y)
        
        # Comprobamos cuáles de la muestra cayeron dentro
        aciertos_muestra = distancias[indices_muestra] < 1

        # Empaquetamos los puntos para visualización
        puntos_visuales = [
            {"x": punto[0], "y": punto[1], "acierto": bool(acierto)}
            for punto, acierto in zip(puntos_muestra, aciertos_muestra)
        ]
        
        return int(aciertos_circulo), puntos_visuales

    def on_mensaje_recibido(self, ch, method, properties, body):
        """
        Función 'Callback' que se ejecuta cada vez que llega un mensaje.
        """
        try:
            # 1. Decodificar el mensaje de trabajo
            lote = json.loads(body)
            id_lote = lote['id_lote']
            dardos = lote['dardos_a_lanzar']
            
            print(f" [x] Recibido Lote {id_lote}. Procesando {dardos:,} dardos...")

            # 2. Realizar el trabajo pesado
            aciertos, puntos_visuales = self.procesar_lote(dardos)
            
            print(f" [✔] Lote {id_lote} terminado. Aciertos: {aciertos:,}")

            # 3. Preparar el mensaje de resultado numérico
            mensaje_resultado = {
                'worker_id': self.worker_id,
                'id_lote': id_lote,
                'total_lanzados': dardos,
                'total_aciertos': aciertos
            }
            
            # 4. Publicar en la cola de resultados
            self.channel.basic_publish(
                exchange='',
                routing_key=self.cola_resultados,
                body=json.dumps(mensaje_resultado),
                properties=pika.BasicProperties(delivery_mode=2) # Persistente
            )

            # 5. Publicar en la cola de puntos visuales
            # (No es crítico si se pierden, así que no los hacemos persistentes)
            self.channel.basic_publish(
                exchange='',
                routing_key=self.cola_puntos_visuales,
                body=json.dumps(puntos_visuales)
            )

            # 6. Confirmar (Acknowledge) a RabbitMQ que el mensaje fue procesado.
            # Esto lo borra de la 'cola_escenarios'.
            ch.basic_ack(delivery_tag=method.delivery_tag)

        except Exception as e:
            print(f" [!] Error procesando Lote {id_lote}: {e}")
            # Rechazar el mensaje sin re-encolar
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    def iniciar_consumo(self):
        """
        Inicia el bucle infinito de consumo de mensajes.
        """
        # 1. QOS (Quality of Service)
        # Esto le dice a RabbitMQ: "No me envíes más de 1 mensaje a la vez".
        # Es clave para el balanceo de carga.
        self.channel.basic_qos(prefetch_count=1)

        # 2. Configurar el consumidor
        self.channel.basic_consume(
            queue=self.cola_trabajo,
            on_message_callback=self.on_mensaje_recibido
            # auto_ack=False por defecto, lo hacemos manual (basic_ack)
        )

        try:
            print(f" [*] {self.worker_id} esperando lotes de trabajo en '{self.cola_trabajo}'. CTRL+C para salir.")
            self.channel.start_consuming()
        except KeyboardInterrupt:
            print("\nSaliendo del worker...")
            self.close()
        except pika.exceptions.ConnectionClosedByBroker:
            print("Conexión cerrada por el broker.")
        finally:
            self.close()


# --- Punto de entrada del script ---
if __name__ == "__main__":
    worker = Worker()
    worker.iniciar_consumo()