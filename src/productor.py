#!/usr/bin/env python
# src/productor.py
import json
import time
import sys
import numpy as np
import pika
from common.broker import RabbitMQBroker
from common.config import (QUEUE_ESCENARIOS, EXCHANGE_MODELO, 
                           TOTAL_DARDOS, DARDOS_POR_LOTE, TTL_MODELO)

class Productor(RabbitMQBroker):
    def __init__(self):
        super().__init__() # Usa config automáticamente
        self.connect()
        self.declare_queue(QUEUE_ESCENARIOS, durable=True)
        # Exchange Fanout para enviar el modelo a todos los workers
        self.channel.exchange_declare(exchange=EXCHANGE_MODELO, exchange_type='fanout')
        self.modelo_config = None

    def cargar_modelo(self, archivo_path):
        try:
            with open(archivo_path, 'r') as f:
                self.modelo_config = json.load(f)
            print(f"[*] Modelo cargado: {self.modelo_config['nombre']}")
        except FileNotFoundError:
            print(f"❌ Error: No se encuentra {archivo_path}")
            sys.exit(1)

    def publicar_modelo(self):
        if not self.modelo_config: return
        
        mensaje = json.dumps(self.modelo_config)
        self.channel.basic_publish(
            exchange=EXCHANGE_MODELO,
            routing_key='',
            body=mensaje,
            properties=pika.BasicProperties(
                expiration=TTL_MODELO,
                delivery_mode=2
            )
        )
        print("[*] Definición del modelo enviada a los workers.")

    def generar_valores(self, config_var, n):
        dist = config_var['distribucion']
        p = config_var['params']
        
        if dist == 'uniform':
            return np.random.uniform(p[0], p[1], n)
        elif dist == 'normal':
            return np.random.normal(p[0], p[1], n)
        elif dist == 'exponential':
            return np.random.exponential(p[0], n)
        elif dist == 'beta':
            return np.random.beta(p[0], p[1], n)
        else:
            return np.zeros(n)

    def iniciar_simulacion(self, total_dardos, dardos_por_lote):
        if not self.modelo_config: return

        self.publicar_modelo()
        time.sleep(1) # Espera breve para propagación

        total_lotes = int(total_dardos // dardos_por_lote)
        print(f"[*] Generando {total_lotes} lotes...")

        vars_config = self.modelo_config['variables']

        try:
            for i in range(total_lotes):
                datos_lote = {}
                for var in vars_config:
                    datos_lote[var['nombre']] = self.generar_valores(var, dardos_por_lote).tolist()

                mensaje = {
                    'id_lote': i + 1,
                    'datos': datos_lote,
                    'total': dardos_por_lote
                }

                self.channel.basic_publish(
                    exchange='',
                    routing_key=QUEUE_ESCENARIOS,
                    body=json.dumps(mensaje),
                    properties=pika.BasicProperties(delivery_mode=2)
                )
                
                if (i+1) % 10 == 0: 
                    print(f" -> Lote {i+1}/{total_lotes} enviado.", end='\r')
            
            print(f"\n[✔] Carga de trabajo completa enviada.")
        
        except KeyboardInterrupt:
            print("\n[!] Interrumpido.")
        finally:
            self.close()

if __name__ == "__main__":
    productor = Productor()
    productor.cargar_modelo('modelo.json')
    productor.iniciar_simulacion(total_dardos=TOTAL_DARDOS, dardos_por_lote=DARDOS_POR_LOTE)