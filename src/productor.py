#!/usr/bin/env python
import pika
import json
import time
import sys
from common.broker import RabbitMQBroker # Importamos nuestra clase

class Productor(RabbitMQBroker):
    """
    El Productor se encarga de generar y enviar los lotes de trabajo.
    Hereda de RabbitMQBroker para reusar la lógica de conexión.
    """
    def __init__(self, host='localhost', cola_trabajo='cola_escenarios'):
        # Llama al __init__ de la clase padre (RabbitMQBroker)
        super().__init__(host=host) 
        self.cola_trabajo = cola_trabajo
        self.connect() # Se conecta al broker al ser creado
        
        # Declara las colas que vamos a usar
        self.declare_queues()

    def declare_queues(self):
        """
        Declara las colas necesarias para el sistema.
        """

        # cola_escenarios: Donde ponemos el trabajo. 
        # Es 'durable' para que los trabajos no se pierdan si RabbitMQ se reinicia.

        self.declare_queue(self.cola_trabajo, durable=True)
        self.declare_queue('cola_resultados', durable=True)
        self.declare_queue('cola_puntos_visuales', durable=True)
        

    def iniciar_simulacion(self, total_dardos, dardos_por_lote=100000):
        """
        Inicia el proceso de enviar lotes de trabajo a la cola.
        """
        if not self.channel:
            print("ERROR: El canal no está disponible.", file=sys.stderr)
            return

        total_lotes = total_dardos // dardos_por_lote
        if total_dardos % dardos_por_lote != 0:
            total_lotes += 1 # Asegura un lote extra para los restantes

        print(f"[*] Iniciando simulación...")
        print(f"    Total de dardos: {total_dardos:,}")
        print(f"    Dardos por lote: {dardos_por_lote:,}")
        print(f"    Total de lotes a enviar: {total_lotes:,}")
        print(f"[*] Enviando lotes a la cola '{self.cola_trabajo}'...")
        
        try:
            for i in range(total_lotes):
                # 1. Crear el mensaje (el lote de trabajo)
                # Usamos JSON, el estándar para mensajería.
                lote_trabajo = {
                    'id_lote': i + 1,
                    'dardos_a_lanzar': dardos_por_lote
                }
                mensaje_json = json.dumps(lote_trabajo)

                # 2. Publicar el mensaje
                self.channel.basic_publish(
                    exchange='',           # Usamos el exchange por defecto
                    routing_key=self.cola_trabajo, # El nombre de la cola
                    body=mensaje_json,
                    properties=pika.BasicProperties(
                        delivery_mode=2,  # Hacer mensajes persistentes
                    )
                )
                
                # Imprimir un progreso (cada 100 lotes)
                if (i + 1) % 100 == 0:
                    print(f"    -> Enviado lote {i+1}/{total_lotes}")

            print(f"[✔] Todos los {total_lotes} lotes han sido enviados.")

        except KeyboardInterrupt:
            print("\n[!] Simulación interrumpida por el usuario.")
        except Exception as e:
            print(f"\n[!] Error publicando mensajes: {e}")
        finally:
            self.close() # Cierra la conexión al terminar


# --- Punto de entrada del script ---
if __name__ == "__main__":
    try:
        # --- PARÁMETROS DE LA SIMULACIÓN ---
        TOTAL_DARDOS_A_SIMULAR = 100_000 
        DARDOS_POR_LOTE = 100            
        # -----------------------------------
        
        # 1. Creamos una instancia del Productor
        productor = Productor()
        
        # 2. Iniciamos la simulación
        productor.iniciar_simulacion(TOTAL_DARDOS_A_SIMULAR, DARDOS_POR_LOTE)

    except KeyboardInterrupt:
        print("\nSaliendo del productor...")
        sys.exit(0)