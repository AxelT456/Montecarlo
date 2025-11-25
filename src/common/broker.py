# src/common/broker.py
import pika
import sys
from common.config import RABBITMQ_HOST, RABBITMQ_USER, RABBITMQ_PASS, RABBITMQ_PORT

class RabbitMQBroker:
    def __init__(self, host=None, user=None, password=None):
        # Prioridad: 1. Argumentos pasados manual, 2. Configuración global
        self.host = host if host else RABBITMQ_HOST
        self.user = user if user else RABBITMQ_USER
        self.password = password if password else RABBITMQ_PASS
        self.port = RABBITMQ_PORT
        
        self.connection = None
        self.channel = None

    def connect(self):
        try:
            credentials = pika.PlainCredentials(self.user, self.password)
            params = pika.ConnectionParameters(
                host=self.host, 
                port=self.port, 
                credentials=credentials
            )
            self.connection = pika.BlockingConnection(params)
            self.channel = self.connection.channel()
            print(f"✅ [Broker] Conectado a {self.host} ({self.user})")
        except Exception as e:
            print(f"❌ [Broker] Error fatal conectando a {self.host}: {e}")
            sys.exit(1)

    def close(self):
        if self.connection and not self.connection.is_closed:
            self.connection.close()

    def declare_queue(self, queue_name, durable=True):
        if self.channel:
            self.channel.queue_declare(queue=queue_name, durable=durable)