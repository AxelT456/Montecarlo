import pika
import sys

class RabbitMQBroker:
    def __init__(self, host='localhost', user=None, password=None):
        self.host = host
        self.user = user
        self.password = password
        self.connection = None
        self.channel = None

    def connect(self):
        try:
            # Si hay usuario y contraseña, usarlos
            if self.user and self.password:
                credentials = pika.PlainCredentials(self.user, self.password)
                params = pika.ConnectionParameters(host=self.host, credentials=credentials)
            else:
                # Si no, intentar conexión anónima o local (guest)
                params = pika.ConnectionParameters(host=self.host)

            self.connection = pika.BlockingConnection(params)
            self.channel = self.connection.channel()
            print(f"✅ Conectado a RabbitMQ en '{self.host}'")
        except Exception as e:
            print(f"❌ ERROR conectando a RabbitMQ en '{self.host}': {e}")
            sys.exit(1)

    def close(self):
        if self.connection and not self.connection.is_closed:
            self.connection.close()

    def declare_queue(self, queue_name, durable=True):
        if self.channel:
            self.channel.queue_declare(queue=queue_name, durable=durable)