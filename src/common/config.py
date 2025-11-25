# src/common/config.py

# --- CONFIGURACIÓN DE RED (RABBITMQ) ---
# 'localhost' si eres el servidor, o la IP (ej '192.168.1.50') si eres worker externo.
RABBITMQ_HOST = 'localhost' 
RABBITMQ_PORT = 5672

# Credenciales (El usuario administrador que creaste)
RABBITMQ_USER = 'admin'
RABBITMQ_PASS = 'admin123'

# --- NOMBRES DE COLAS Y EXCHANGES ---
# Centralizamos los nombres para no equivocarnos al escribirlos
QUEUE_ESCENARIOS = 'cola_escenarios'
QUEUE_RESULTADOS = 'cola_resultados'
QUEUE_VISUALES = 'cola_puntos_visuales'
EXCHANGE_MODELO = 'modelo_exchange'

# --- PARÁMETROS POR DEFECTO ---
TOTAL_DARDOS = 5_000_000
DARDOS_POR_LOTE = 50_000
TTL_MODELO = '60000' # 60 segundos