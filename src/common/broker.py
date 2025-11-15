import pika
import sys

class RabbitMQBroker:
    """
    Clase base para manejar la conexión y el canal de RabbitMQ.
    """
    def __init__(self, host='localhost'):
        self.host = host
        self.connection = None
        self.channel = None

    def connect(self):
        """
        Establece la conexión y el canal.
        """
        try:
            self.connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=self.host)
            )
            self.channel = self.connection.channel()
            print(f"✅ Conectado exitosamente a RabbitMQ en '{self.host}'")
        except pika.exceptions.AMQPConnectionError as e:
            print(f"❌ ERROR: No se pudo conectar a RabbitMQ en '{self.host}'.")
            print("Asegúrate de que el servicio esté corriendo (sudo systemctl start rabbitmq-server)")
            sys.exit(1) # Salir del programa si no hay conexión

    def close(self):
        """
        Cierra la conexión.
        """
        if self.connection and not self.connection.is_closed:
            self.connection.close()
            print("Conexión con RabbitMQ cerrada.")

    def declare_queue(self, queue_name, durable=True):
        """
        Declara una cola (la hace 'durable' por defecto).
        Durable = la cola sobrevive si RabbitMQ se reinicia.
        """
        if not self.channel:
            print("ERROR: No hay canal. Conéctese primero.")
            return
            
        print(f"Declarando cola: {queue_name}")
        self.channel.queue_declare(queue=queue_name, durable=durable)

# --- Fin del archivo ---