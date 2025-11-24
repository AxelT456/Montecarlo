#!/usr/bin/env python
import json
import time
import sys
import numpy as np
import pika
from common.broker import RabbitMQBroker

class Productor(RabbitMQBroker):
    def __init__(self, host='localhost', user=None, password=None):
        super().__init__(host=host, user=user, password=password)
        self.connect()
        self.declare_queue('cola_escenarios', durable=True)
        # Exchange Fanout para enviar el modelo a todos los workers
        self.channel.exchange_declare(exchange='modelo_exchange', exchange_type='fanout')
        self.modelo_config = None

    def cargar_modelo(self, archivo_path):
        with open(archivo_path, 'r') as f:
            self.modelo_config = json.load(f)
        print(f"[*] Modelo cargado: {self.modelo_config['nombre']}")

    def publicar_modelo(self):
        """Publica el JSON del modelo con TTL (Caducidad)"""
        if not self.modelo_config: return
        
        mensaje = json.dumps(self.modelo_config)
        self.channel.basic_publish(
            exchange='modelo_exchange',
            routing_key='',
            body=mensaje,
            properties=pika.BasicProperties(
                expiration='60000', # El modelo caduca en 60s si nadie lo lee
                delivery_mode=2
            )
        )
        print("[*] Definición del modelo enviada a los workers.")

    def generar_valores(self, config_var, n):
        """Generador de distribuciones extendido"""
        dist = config_var['distribucion']
        p = config_var['params'] # Lista de parametros
        
        if dist == 'uniform':
            return np.random.uniform(p[0], p[1], n)
        elif dist == 'normal':
            return np.random.normal(p[0], p[1], n) # Media, Desviación Estándar
        elif dist == 'exponential':
            return np.random.exponential(p[0], n)  # Escala
        elif dist == 'beta':
            return np.random.beta(p[0], p[1], n)   # Alpha, Beta
        else:
            print(f"Advertencia: Distribución '{dist}' no reconocida. Usando ceros.")
            return np.zeros(n)

    def iniciar_simulacion(self, total_dardos, dardos_por_lote=50000):
        if not self.modelo_config:
            print("❌ Error: Carga el modelo.json primero.")
            return

        # 1. Enviar la definición del problema a los workers
        self.publicar_modelo()
        time.sleep(1) # Dar tiempo a que los workers reciban el modelo

        # 2. Generar escenarios
        total_lotes = int(total_dardos // dardos_por_lote)
        print(f"[*] Generando {total_lotes} lotes basados en '{self.modelo_config['nombre']}'...")

        vars_config = self.modelo_config['variables']

        try:
            for i in range(total_lotes):
                # Generamos datos dinámicamente según el JSON
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
                    routing_key='cola_escenarios',
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
    # --- CONFIGURACIÓN ---
    productor = Productor(host='localhost') 
    
    productor.cargar_modelo('modelo.json')
    productor.iniciar_simulacion(total_dardos=5_000_000, dardos_por_lote=20_000)