#!/usr/bin/env python
import pika
import json
import numpy as np
import random
import time
from common.broker import RabbitMQBroker

class Worker(RabbitMQBroker):
    def __init__(self, host='localhost', user=None, password=None):
        super().__init__(host=host, user=user, password=password)
        self.worker_id = f"worker-{random.randint(100, 999)}"
        self.modelo_actual = None
        self.connect()

        # 1. Configurar recepción del MODELO (Cola temporal exclusiva)
        result = self.channel.queue_declare(queue='', exclusive=True)
        q_name = result.method.queue
        self.channel.queue_bind(exchange='modelo_exchange', queue=q_name)
        self.channel.basic_consume(queue=q_name, on_message_callback=self.recibir_modelo, auto_ack=True)

        # 2. Configurar recepción de TRABAJO
        self.declare_queue('cola_escenarios', durable=True)
        self.declare_queue('cola_resultados', durable=True)
        self.declare_queue('cola_puntos_visuales', durable=True)
        
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(queue='cola_escenarios', on_message_callback=self.procesar_trabajo)

    def recibir_modelo(self, ch, method, props, body):
        self.modelo_actual = json.loads(body)
        print(f"\n[★] NUEVA CONFIGURACIÓN RECIBIDA: {self.modelo_actual['nombre']}")
        print(f"    Función a evaluar: {self.modelo_actual['funcion_evaluacion']}")

    def procesar_trabajo(self, ch, method, props, body):
        if not self.modelo_actual:
            print(" [!] Recibí trabajo pero no tengo el modelo. Esperando...", end='\r')
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            time.sleep(1)
            return

        data = json.loads(body)
        datos_variables = data['datos'] # {'x': [...], 'y': [...]}
        
        # Preparar contexto para EVAL (Numpy seguro)
        contexto = {"np": np, "abs": np.abs, "sin": np.sin, "cos": np.cos, "sqrt": np.sqrt}
        # Inyectar las variables del JSON (x, y) como arrays de numpy
        for nombre, lista in datos_variables.items():
            contexto[nombre] = np.array(lista)

        try:
            # --- EVALUACIÓN DINÁMICA ---
            formula = self.modelo_actual['funcion_evaluacion']
            # Esto devuelve un array de True/False
            resultado = eval(formula, {"__builtins__": None}, contexto)
            aciertos = np.sum(resultado)
        except Exception as e:
            print(f" [!] Error evaluando fórmula: {e}")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        # Visualización (Muestra de 100 puntos)
        puntos_visuales = []
        if 'x' in datos_variables and 'y' in datos_variables:
            limit = 100
            bx = datos_variables['x'][:limit]
            by = datos_variables['y'][:limit]
            bres = resultado[:limit]
            for i in range(len(bx)):
                puntos_visuales.append({'x': bx[i], 'y': by[i], 'acierto': bool(bres[i])})

        # Enviar Resultados
        msg_res = {
            'worker_id': self.worker_id,
            'total_lanzados': data['total'],
            'total_aciertos': int(aciertos)
        }
        self.channel.basic_publish(exchange='', routing_key='cola_resultados', 
                                   body=json.dumps(msg_res),
                                   properties=pika.BasicProperties(delivery_mode=2))
        
        if puntos_visuales:
            self.channel.basic_publish(exchange='', routing_key='cola_puntos_visuales', 
                                       body=json.dumps(puntos_visuales))

        ch.basic_ack(delivery_tag=method.delivery_tag)
        print(f" [Worker {self.worker_id}] Lote {data['id_lote']} procesado. Aciertos: {aciertos}")

    def iniciar(self):
        print(f" [*] Worker {self.worker_id} LISTO. Esperando modelo...")
        self.channel.start_consuming()

if __name__ == "__main__":
    IP_LINUX = '192.168.1.XX' 
    USUARIO = 'admin'      
    PASSWORD = 'admin123'  
    
    try:
        w = Worker(host=IP_LINUX, user=USUARIO, password=PASSWORD)
        w.iniciar()
    except Exception as e:
        print(f"Error conectando: {e}")
        input("Presiona Enter para salir...")