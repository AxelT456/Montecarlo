#!/usr/bin/env python
import pika
import json
import numpy as np
import sys
from collections import deque

import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objs as go
import dash_bootstrap_components as dbc # ¡NUEVO!

from common.broker import RabbitMQBroker

# --- Configuración Global ---

# Estructuras de datos para mantener el estado
global_stats = {'total_lanzados': 0, 'total_aciertos': 0}
pi_history = deque(maxlen=200) # Guardar solo los últimos 200 valores de Pi

# Deque (cola de doble extremo) es súper eficiente.
# Limitamos los puntos en el scatter plot a 2000 para que la web no se sature.
# ¡CAMBIO! Separamos los puntos por color para un renderizado más robusto.
points_data_green = {'x': deque(maxlen=1000), 'y': deque(maxlen=1000)}
points_data_red = {'x': deque(maxlen=1000), 'y': deque(maxlen=1000)}

# Conexión global a RabbitMQ
try:
    broker = RabbitMQBroker()
    broker.connect()
    broker.declare_queue('cola_resultados', durable=True)
    broker.declare_queue('cola_puntos_visuales', durable=True)
    global_channel = broker.channel
except Exception as e:
    print(f"❌ Error fatal al conectar con RabbitMQ: {e}")
    sys.exit(1)

# --- Aplicación Dash ---

# ¡CAMBIO! Usamos un tema profesional de Bootstrap (DARKLY)
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.DARKLY])
app.title = "Dashboard Montecarlo Pi"

# ¡CAMBIO! Layout rehecho con Bootstrap (Contenedores, Filas, Columnas)
app.layout = dbc.Container(fluid=True, children=[
    dbc.Row(dbc.Col(html.H1(
        children='Simulación Montecarlo Distribuida - Cálculo de π',
        className="text-center text-light my-4" # Clases de Bootstrap
    ))),

    dbc.Row([
        # Columna Izquierda (Pi y Stats)
        dbc.Col(width=5, children=[
            dcc.Graph(id='pi-gauge'),
            html.H3("Valor de π (convergencia)", className="text-center mt-4"),
            dcc.Graph(id='pi-convergence-chart'),
        ]),
        
        # Columna Derecha (Scatter Plot)
        dbc.Col(width=7, children=[
            html.H3("Muestra de 'Dardos' (Últimos 2000)", className="text-center"),
            dcc.Graph(id='scatter-plot', style={'height': '70vh'}),
        ]),
    ]),

    # Componente invisible que actualiza todo cada segundo
    dcc.Interval(
        id='interval-component',
        interval=1*1000, # en milisegundos (1 segundo)
        n_intervals=0
    )
])

# --- Lógica de Callbacks (Magia en tiempo real) ---

def consumir_mensajes_de_rabbitmq():
    """
    Función helper para consumir TODOS los mensajes pendientes 
    de las colas usando basic_get (no bloqueante).
    """
    global global_stats, pi_history, points_data_green, points_data_red, global_channel
    
    # 1. Consumir de 'cola_resultados' (Cálculo de Pi)
    while True:
        method_frame, header_frame, body = global_channel.basic_get(
            queue='cola_resultados', 
            auto_ack=True
        )
        if method_frame is None:
            break # No hay más mensajes

        data = json.loads(body)
        global_stats['total_lanzados'] += data['total_lanzados']
        global_stats['total_aciertos'] += data['total_aciertos']
        
        # Calcular Pi y añadirlo al historial
        if global_stats['total_lanzados'] > 0:
            current_pi = 4 * (global_stats['total_aciertos'] / global_stats['total_lanzados'])
            pi_history.append(current_pi)

    # 2. Consumir de 'cola_puntos_visuales' (Scatter plot)
    while True:
        method_frame, header_frame, body = global_channel.basic_get(
            queue='cola_puntos_visuales', 
            auto_ack=True
        )
        if method_frame is None:
            break # No hay más mensajes
        
        points = json.loads(body)
        
        # ¡CAMBIO! Separamos los puntos en sus listas correspondientes
        for p in points:
            if p['acierto']:
                points_data_green['x'].append(p['x'])
                points_data_green['y'].append(p['y'])
            else:
                points_data_red['x'].append(p['x'])
                points_data_red['y'].append(p['y'])


# El "Callback" principal que se ejecuta cada segundo
@app.callback(
    [Output('pi-gauge', 'figure'),
     Output('pi-convergence-chart', 'figure'),
     Output('scatter-plot', 'figure')],
    [Input('interval-component', 'n_intervals')]
)
def update_graphics(n):
    # 1. Vaciar las colas de RabbitMQ y actualizar datos globales
    consumir_mensajes_de_rabbitmq()

    # 2. Calcular valores actuales
    current_pi = pi_history[-1] if len(pi_history) > 0 else 0
    total_dardos = global_stats['total_lanzados']
    
    # 3. Crear las figuras (gráficos)
    
    # Figura 1: El Medidor (Gauge) de Pi
    # (Este usa un tema 'plotly_dark' para encajar con el fondo)
    gauge_fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = current_pi,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': f'Valor de π (Total dardos: {total_dardos:,})'},
        gauge = {
            'axis': {'range': [3.10, 3.18], 'tickwidth': 1},
            'bar': {'color': "#4CAF50"},
            'steps' : [
                {'range': [3.10, 3.14159], 'color': 'gray'},
                {'range': [3.14159, 3.18], 'color': 'darkgray'}],
            'threshold' : {'line': {'color': "cyan", 'width': 4}, 'thickness': 0.75, 'value': np.pi}
        }
    ))
    gauge_fig.update_layout(template='plotly_dark')

    # Figura 2: Gráfico de Convergencia
    line_fig = go.Figure(data=[
        go.Scatter(y=list(pi_history), mode='lines', line={'color': '#4CAF50'}, name='π Calculado'),
        go.Scatter(y=[np.pi] * len(pi_history), mode='lines', line={'color': 'cyan', 'dash': 'dash'}, name='π Real')
    ])
    line_fig.update_layout(
        template='plotly_dark',
        yaxis_range=[3.1, 3.2] # Rango fijo para ver la convergencia
    )

    # Figura 3: El Scatter Plot (Dardos)
    # ¡CAMBIO! Creamos dos "trazas" (traces), una para verdes y otra para rojos.
    # Esto garantiza que los colores y la leyenda funcionen bien.
    scatter_fig = go.Figure()
    
    scatter_fig.add_trace(go.Scattergl( # Puntos ROJOS
        x=list(points_data_red['x']),
        y=list(points_data_red['y']),
        mode='markers', name='Falla (Fuera)',
        marker=dict(color='red', size=2, opacity=0.5)
    ))
    
    scatter_fig.add_trace(go.Scattergl( # Puntos VERDES
        x=list(points_data_green['x']),
        y=list(points_data_green['y']),
        mode='markers', name='Acierto (Dentro)',
        marker=dict(color='lightgreen', size=2, opacity=0.5)
    ))
    
    # ¡CAMBIO! Forzamos los ejes de 0 a 1 y el aspecto cuadrado.
    scatter_fig.update_layout(
        template='plotly_dark',
        legend_orientation="h",
        legend=dict(x=0, y=1.1),
        xaxis=dict(range=[0,1]),
        yaxis=dict(range=[0,1], scaleanchor="x", scaleratio=1),
    )
    
    return gauge_fig, line_fig, scatter_fig


# --- Punto de entrada del script ---
if __name__ == '__main__':
    print("Iniciando Dashboard. Abre tu navegador en http://localhost:8050")
    app.run(debug=True, host='0.0.0.0', port=8050)