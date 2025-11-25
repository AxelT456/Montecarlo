#!/usr/bin/env python
# src/dashboard.py
import json
import numpy as np
import sys
from collections import deque
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objs as go
import dash_bootstrap_components as dbc
from common.broker import RabbitMQBroker
from common.config import QUEUE_RESULTADOS, QUEUE_VISUALES

# --- ESTADO ---
global_stats = {'total_lanzados': 0, 'total_aciertos': 0}
pi_history = deque(maxlen=300) 
points_data_green = {'x': deque(maxlen=2000), 'y': deque(maxlen=2000)}
points_data_red = {'x': deque(maxlen=2000), 'y': deque(maxlen=2000)}

# --- CONEXIÓN ---
try:
    broker = RabbitMQBroker()
    broker.connect()
    broker.declare_queue(QUEUE_RESULTADOS, durable=True)
    broker.declare_queue(QUEUE_VISUALES, durable=True)
    global_channel = broker.channel
except Exception as e:
    print(f"❌ Error Dashboard: {e}")
    sys.exit(1)

# --- APP ---
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.CYBORG])
app.title = "Montecarlo Distribuido"

def create_card(title, id_val, color="primary"):
    return dbc.Card(dbc.CardBody([
        html.H6(title, className="card-title text-muted"),
        html.H2("0", id=id_val, className=f"text-{color} font-weight-bold")
    ]), className="mb-3 shadow-sm")

app.layout = dbc.Container(fluid=True, className="p-4", children=[
    dbc.Row([
        dbc.Col(html.H2("🧬 Simulación Distribuida: Método Montecarlo", className="text-white"), width=8),
        dbc.Col(html.H5("Estado: 🟢 Activo", className="text-success text-end"), width=4),
    ], className="mb-4 border-bottom border-secondary pb-2"),

    dbc.Row([
        dbc.Col(create_card("Valor Calculado de π", "kpi-pi", "info"), width=4),
        dbc.Col(create_card("Error Absoluto (%)", "kpi-error", "danger"), width=4),
        dbc.Col(create_card("Total Dardos Lanzados", "kpi-total", "success"), width=4),
    ], className="mb-2"),

    dbc.Row([
        dbc.Col([dbc.Card([
            dbc.CardHeader("Visualización de Impactos (Muestra en TR)"),
            dbc.CardBody(dcc.Graph(id='scatter-plot', style={'height': '600px'}))
        ])], width=8),

        dbc.Col([
            dbc.Card([dbc.CardHeader("Convergencia hacia π"), dbc.CardBody(dcc.Graph(id='convergence-plot', style={'height': '250px'}))], className="mb-3"),
            dbc.Card([dbc.CardHeader("Información"), dbc.CardBody([
                html.P("Arquitectura: Productor-Consumidor", className="small"),
                html.P("Broker: RabbitMQ", className="small"),
                html.P("Nodos Workers: Dinámicos", className="small"),
                html.Hr(),
                html.P("Objetivo: π ≈ 3.14159265...", className="text-muted small")
            ])])
        ], width=4),
    ]),
    dcc.Interval(id='updater', interval=3000, n_intervals=0)
])

def consumir_mensajes():
    global global_stats, pi_history, points_data_green, points_data_red
    while True:
        m, _, b = global_channel.basic_get(QUEUE_RESULTADOS, auto_ack=True)
        if not m: break
        d = json.loads(b)
        global_stats['total_lanzados'] += d['total_lanzados']
        global_stats['total_aciertos'] += d['total_aciertos']
        if global_stats['total_lanzados'] > 0:
            pi_history.append(4 * (global_stats['total_aciertos'] / global_stats['total_lanzados']))

    while True:
        m, _, b = global_channel.basic_get(QUEUE_VISUALES, auto_ack=True)
        if not m: break
        pts = json.loads(b)
        for p in pts:
            if p['acierto']:
                points_data_green['x'].append(p['x'])
                points_data_green['y'].append(p['y'])
            else:
                points_data_red['x'].append(p['x'])
                points_data_red['y'].append(p['y'])

@app.callback(
    [Output('kpi-pi', 'children'), Output('kpi-error', 'children'), Output('kpi-total', 'children'),
     Output('scatter-plot', 'figure'), Output('convergence-plot', 'figure')],
    [Input('updater', 'n_intervals')]
)
def update_dashboard(n):
    consumir_mensajes()
    total = global_stats['total_lanzados']
    curr_pi = pi_history[-1] if pi_history else 0
    err = abs((curr_pi - np.pi) / np.pi) * 100 if total > 0 else 0

    scatter = go.Figure()
    scatter.add_trace(go.Scattergl(x=list(points_data_red['x']), y=list(points_data_red['y']), mode='markers', name='Fuera', marker=dict(color='#e74c3c', size=3, opacity=0.6)))
    scatter.add_trace(go.Scattergl(x=list(points_data_green['x']), y=list(points_data_green['y']), mode='markers', name='Dentro', marker=dict(color='#2ecc71', size=3, opacity=0.6)))
    
    # Círculo Completo
    th = np.linspace(0, 2*np.pi, 100)
    scatter.add_trace(go.Scatter(x=np.cos(th), y=np.sin(th), mode='lines', name='Límite', line=dict(color='white', width=2, dash='dash')))

    scatter.update_layout(template='plotly_dark', margin=dict(l=20, r=20, t=20, b=20),
                          xaxis=dict(range=[-1.1, 1.1], showgrid=False, zeroline=False),
                          yaxis=dict(range=[-1.1, 1.1], showgrid=False, zeroline=False, scaleanchor="x", scaleratio=1),
                          paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                          legend=dict(orientation="h", y=1.02, x=1))

    line = go.Figure()
    line.add_trace(go.Scatter(y=list(pi_history), mode='lines', line=dict(color='#3498db', width=2)))
    line.add_trace(go.Scatter(y=[np.pi]*len(pi_history), mode='lines', line=dict(color='#f1c40f', width=1, dash='dot'), name='π Real'))
    line.update_layout(template='plotly_dark', margin=dict(l=40, r=20, t=10, b=30), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=False, yaxis=dict(range=[3.10, 3.18]))

    return f"{curr_pi:.6f}", f"{err:.4f}%", f"{total:,}", scatter, line

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=8050)