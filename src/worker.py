#!/usr/bin/env python
# src/worker.py
import pika
import json
import numpy as np
import random
import time
from common.broker import RabbitMQBroker
from common.config import (QUEUE_ESCENARIOS, QUEUE_RESULTADOS, 
                           QUEUE_VISUALES, EXCHANGE_MODELO)

class Worker(RabbitMQBroker):
    def __init__(self):
        super().__init__() # Usa config automáticamente
        self.worker_id = f"worker-{random.randint(100, 999)}"
        self.modelo_actual = None
        self.connect()

        # 1. Configurar recepción del MODELO
        result = self.channel.queue_declare(queue='', exclusive=True)
        q_name = result.method.queue
        self.channel.queue_bind(exchange=EXCHANGE_MODELO, queue=q_name)
        self.channel.basic_consume(queue=q_name, on_message_callback=self.recibir_modelo, auto_ack=True)

        # 2. Configurar recepción de TRABAJO
        self.declare_queue(QUEUE_ESCENARIOS, durable=True)
        self.declare_queue(QUEUE_RESULTADOS, durable=True)
        self.declare_queue(QUEUE_VISUALES, durable=True)
        
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(queue=QUEUE_ESCENARIOS, on_message_callback=self.procesar_trabajo)

    def recibir_modelo(self, ch, method, props, body):
        self.modelo_actual = json.loads(body)
        print(f"\n[★] NUEVO MODELO: {self.modelo_actual['nombre']}")

    def procesar_trabajo(self, ch, method, props, body):
        if not self.modelo_actual:
            print(" [!] Esperando modelo...", end='\r')
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            time.sleep(1)
            return

        data = json.loads(body)
        datos = data['datos']
        
        # Contexto seguro para Numpy
        contexto = {"np": np, "abs": np.abs, "sin": np.sin, "cos": np.cos, "sqrt": np.sqrt}
        for nombre, lista in datos.items():
            contexto[nombre] = np.array(lista)

        try:
            # Evaluación Dinámica
            formula = self.modelo_actual['funcion_evaluacion']
            resultado = eval(formula, {"__builtins__": None}, contexto)
            aciertos = np.sum(resultado)
        except Exception as e:
            print(f" [!] Error: {e}")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        # Visualización (Muestra)
        puntos_visuales = []
        if 'x' in datos and 'y' in datos:
            limit = 100
            bx, by, bres = datos['x'][:limit], datos['y'][:limit], resultado[:limit]
            for i in range(len(bx)):
                puntos_visuales.append({'x': bx[i], 'y': by[i], 'acierto': bool(bres[i])})

        # Resultados
        msg_res = {
            'worker_id': self.worker_id,
            'total_lanzados': data['total'],
            'total_aciertos': int(aciertos)
        }
        self.channel.basic_publish(exchange='', routing_key=QUEUE_RESULTADOS, 
                                   body=json.dumps(msg_res),
                                   properties=pika.BasicProperties(delivery_mode=2))
        
        if puntos_visuales:
            self.channel.basic_publish(exchange='', routing_key=QUEUE_VISUALES, 
                                       body=json.dumps(puntos_visuales))

        ch.basic_ack(delivery_tag=method.delivery_tag)
        print(f" [Worker {self.worker_id}] Lote {data['id_lote']} OK. Aciertos: {aciertos}")

    def iniciar(self):
        print(f" [*] Worker {self.worker_id} LISTO. Esperando...")
        self.channel.start_consuming()

if __name__ == "__main__":
    Worker().iniciar()