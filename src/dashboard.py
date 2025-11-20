#!/usr/bin/env python
import json
import numpy as np
import sys
from collections import deque

import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objs as go
import dash_bootstrap_components as dbc # Asegúrate de tener pip install dash-bootstrap-components

from common.broker import RabbitMQBroker

# --- CONFIGURACIÓN GLOBAL ---

global_stats = {'total_lanzados': 0, 'total_aciertos': 0}
pi_history = deque(maxlen=300) 
# Aumentamos un poco el historial visual
points_data_green = {'x': deque(maxlen=2000), 'y': deque(maxlen=2000)}
points_data_red = {'x': deque(maxlen=2000), 'y': deque(maxlen=2000)}

# Conexión a RabbitMQ
try:
    broker = RabbitMQBroker() # Recuerda configurar user/pass si es necesario aquí
    broker.connect()
    broker.declare_queue('cola_resultados', durable=True)
    broker.declare_queue('cola_puntos_visuales', durable=True)
    global_channel = broker.channel
except Exception as e:
    print(f"❌ Error fatal RabbitMQ: {e}")
    sys.exit(1)

# --- ESTILOS Y TEMA ---
# Usamos el tema CYBORG (Negro y Azul Neón)
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.CYBORG])
app.title = "Montecarlo Pi Distributed"

# --- COMPONENTES VISUALES (KPI CARDS) ---
def create_card(title, id_value, color="primary"):
    return dbc.Card(
        dbc.CardBody([
            html.H6(title, className="card-title text-muted"),
            html.H2("0", id=id_value, className=f"text-{color} font-weight-bold")
        ]),
        className="mb-3 shadow-sm" # Sombra suave
    )

# --- LAYOUT PRINCIPAL ---
app.layout = dbc.Container(fluid=True, className="p-4", children=[
    
    # 1. Encabezado
    dbc.Row([
        dbc.Col(html.H2("🧬 Simulación Distribuida: Método Montecarlo", className="text-white"), width=8),
        dbc.Col(html.H5("Estado: 🟢 Activo", className="text-success text-end"), width=4),
    ], className="mb-4 border-bottom border-secondary pb-2"),

    # 2. Fila de Métricas (KPIs)
    dbc.Row([
        dbc.Col(create_card("Valor Calculado de π", "kpi-pi", "info"), width=4),
        dbc.Col(create_card("Error Absoluto (%)", "kpi-error", "danger"), width=4),
        dbc.Col(create_card("Total Dardos Lanzados", "kpi-total", "success"), width=4),
    ], className="mb-2"),

    # 3. Fila de Gráficos
    dbc.Row([
        # Columna Izquierda: El Círculo (Scatter) - EL HÉROE VISUAL
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Visualización de Impactos (Muestra en TR)"),
                dbc.CardBody(dcc.Graph(id='scatter-plot', style={'height': '600px'}))
            ])
        ], width=8),

        # Columna Derecha: Convergencia
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Convergencia hacia π"),
                dbc.CardBody(dcc.Graph(id='convergence-plot', style={'height': '250px'}))
            ], className="mb-3"),
            
            dbc.Card([
                dbc.CardHeader("Información del Sistema"),
                dbc.CardBody([
                    html.P("Arquitectura: Productor-Consumidor", className="small"),
                    html.P("Broker: RabbitMQ", className="small"),
                    html.P("Nodos Workers: Dinámicos", className="small"),
                    html.Hr(),
                    html.P("Objetivo: π ≈ 3.14159265...", className="text-muted small")
                ])
            ])
        ], width=4),
    ]),

    # Actualizador (3 segundos para estabilidad)
    dcc.Interval(id='updater', interval=3000, n_intervals=0)
])

# --- LÓGICA ---

def consumir_mensajes():
    global global_stats, pi_history, points_data_green, points_data_red, global_channel
    
    # Consumir Resultados Numéricos
    while True:
        method, _, body = global_channel.basic_get('cola_resultados', auto_ack=True)
        if not method: break
        data = json.loads(body)
        global_stats['total_lanzados'] += data['total_lanzados']
        global_stats['total_aciertos'] += data['total_aciertos']
        
        if global_stats['total_lanzados'] > 0:
            pi_val = 4 * (global_stats['total_aciertos'] / global_stats['total_lanzados'])
            pi_history.append(pi_val)

    # Consumir Puntos Visuales
    while True:
        method, _, body = global_channel.basic_get('cola_puntos_visuales', auto_ack=True)
        if not method: break
        points = json.loads(body)
        for p in points:
            if p['acierto']:
                points_data_green['x'].append(p['x'])
                points_data_green['y'].append(p['y'])
            else:
                points_data_red['x'].append(p['x'])
                points_data_red['y'].append(p['y'])

@app.callback(
    [Output('kpi-pi', 'children'),
     Output('kpi-error', 'children'),
     Output('kpi-total', 'children'),
     Output('scatter-plot', 'figure'),
     Output('convergence-plot', 'figure')],
    [Input('updater', 'n_intervals')]
)
def update_dashboard(n):
    consumir_mensajes()
    
    # Cálculos
    total = global_stats['total_lanzados']
    current_pi = pi_history[-1] if pi_history else 0
    real_pi = np.pi
    error = abs((current_pi - real_pi) / real_pi) * 100 if total > 0 else 0

    # 1. Formatear KPIs
    str_pi = f"{current_pi:.6f}"
    str_error = f"{error:.4f}%"
    str_total = f"{total:,}"

    # 2. Gráfico Scatter (El Círculo)
    scatter_fig = go.Figure()
    # Puntos Rojos (Fondo)
    scatter_fig.add_trace(go.Scattergl(
        x=list(points_data_red['x']), y=list(points_data_red['y']),
        mode='markers', name='Fuera',
        marker=dict(color='#e74c3c', size=3, opacity=0.6) # Rojo suave
    ))
    # Puntos Verdes (Círculo)
    scatter_fig.add_trace(go.Scattergl(
        x=list(points_data_green['x']), y=list(points_data_green['y']),
        mode='markers', name='Dentro',
        marker=dict(color='#2ecc71', size=3, opacity=0.6) # Verde esmeralda
    ))
    # Arco del círculo real (Visual aid)
    x_arc = np.linspace(0, 1, 100)
    y_arc = np.sqrt(1 - x_arc**2)
    scatter_fig.add_trace(go.Scatter(
        x=x_arc, y=y_arc, mode='lines', name='Límite Real',
        line=dict(color='white', width=2, dash='dash')
    ))

    scatter_fig.update_layout(
        template='plotly_dark',
        margin=dict(l=20, r=20, t=20, b=20),
        xaxis=dict(range=[0, 1], showgrid=False, zeroline=False), # Limpio sin grid
        yaxis=dict(range=[0, 1], showgrid=False, zeroline=False, scaleanchor="x", scaleratio=1),
        paper_bgcolor='rgba(0,0,0,0)', # Fondo transparente para mezclarse con la tarjeta
        plot_bgcolor='rgba(0,0,0,0)',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    # 3. Gráfico Convergencia (Línea)
    line_fig = go.Figure()
    line_fig.add_trace(go.Scatter(y=list(pi_history), mode='lines', line=dict(color='#3498db', width=2)))
    # Línea de referencia Pi Real
    line_fig.add_trace(go.Scatter(
        y=[np.pi]*len(pi_history), mode='lines', 
        line=dict(color='#f1c40f', width=1, dash='dot'), name='π Real'
    ))
    
    line_fig.update_layout(
        template='plotly_dark',
        margin=dict(l=40, r=20, t=10, b=30),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        showlegend=False,
        yaxis=dict(range=[3.10, 3.18]) # Zoom en la zona de interés
    )

    return str_pi, str_error, str_total, scatter_fig, line_fig

if __name__ == '__main__':
    # debug=False para evitar el loop infinito de recarga
    app.run(debug=False, host='0.0.0.0', port=8050)