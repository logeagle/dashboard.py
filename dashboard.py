#!/usr/bin/env python3

import os
import pandas as pd
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
from flask_caching import Cache
import plotly.graph_objs as go
import glob
import socket
from datetime import datetime, timedelta

class Config:
    def __init__(self):
        self.log_dir = os.path.expanduser("~/logeagle")
        self.cache_dir = os.path.join(self.log_dir, "cache")
        self.refresh_interval = 10  # seconds
        self.port = 8050
        
        # Create necessary directories
        os.makedirs(self.log_dir, exist_ok=True)
        os.makedirs(self.cache_dir, exist_ok=True)

def find_free_port(start_port=8050, max_port=9000):
    """Find an available port to run the server."""
    for port in range(start_port, max_port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('', port))
                return port
            except OSError:
                continue
    return start_port

def read_latest_parquet_files(directory, prefix):
    """Read the most recent parquet files for the given prefix."""
    try:
        files = glob.glob(os.path.join(directory, f"{prefix}*.parquet"))
        if not files:
            return pd.DataFrame()

        # Read last 5 files
        dfs = []
        for file in sorted(files, reverse=True)[:5]:
            try:
                df = pd.read_parquet(file)
                dfs.append(df)
            except Exception:
                continue

        if not dfs:
            return pd.DataFrame()

        return pd.concat(dfs, ignore_index=True)
    except Exception:
        return pd.DataFrame()

# Initialize configuration
config = Config()

# Initialize Dash app
app = dash.Dash(__name__, 
    suppress_callback_exceptions=True,
    title="Log Eagle Dashboard"
)

# Initialize cache
cache = Cache(app.server, config={
    'CACHE_TYPE': 'filesystem',
    'CACHE_DIR': config.cache_dir,
    'CACHE_DEFAULT_TIMEOUT': config.refresh_interval
})

# Cache data reading
@cache.memoize(timeout=config.refresh_interval)
def get_dataframe(log_type):
    return read_latest_parquet_files(config.log_dir, log_type)

# Dashboard layout with some basic styling
app.layout = html.Div([
    html.Div([
        html.H1("Log Eagle Dashboard", 
                style={'textAlign': 'center', 'color': '#2c3e50', 'marginBottom': 20}),
        
        dcc.Tabs(id='tabs', value='tab-1', children=[
            dcc.Tab(label='Access Logs', value='tab-1',
                   style={'padding': '10px', 'fontWeight': 'bold'}),
            dcc.Tab(label='Error Logs', value='tab-2',
                   style={'padding': '10px', 'fontWeight': 'bold'}),
        ], style={'marginBottom': 20}),
        
        html.Div(id='tabs-content'),
        
        dcc.Interval(
            id='interval-component',
            interval=config.refresh_interval * 1000,  # Convert to milliseconds
            n_intervals=0
        )
    ], style={'padding': '20px'})
])

@app.callback(
    Output('tabs-content', 'children'),
    [Input('tabs', 'value'),
     Input('interval-component', 'n_intervals')]
)
def update_content(tab, n):
    """Update dashboard content based on selected tab."""
    # Determine which logs to show
    if tab == 'tab-1':
        df = get_dataframe('access')
        title = 'Access Logs'
    else:
        df = get_dataframe('error')
        title = 'Error Logs'

    if df.empty:
        return html.Div([
            html.H3("No Data Available",
                    style={'textAlign': 'center', 'color': '#e74c3c'}),
            html.P("Please check if the log processor is running and generating log files.",
                  style={'textAlign': 'center'})
        ])

    # Process the data
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
    df = df.set_index('timestamp').sort_index()
    
    # Create time series plot
    time_series = create_time_series(df, title)
    
    # Create log entries table
    log_table = create_log_table(df)

    return html.Div([
        html.Div([
            dcc.Graph(figure=time_series),
        ], style={'marginBottom': 20}),
        
        html.H3("Recent Log Entries",
                style={'color': '#2c3e50', 'marginBottom': 10}),
        
        log_table,
        
        html.Div(
            f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            style={'textAlign': 'right', 'color': '#7f8c8d', 'marginTop': 10}
        )
    ])

def create_time_series(df, title):
    """Create time series plot of log frequency."""
    df_resampled = df.resample('1min').count()
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_resampled.index,
        y=df_resampled['line'],
        mode='lines',
        name='Log Entries',
        line={'color': '#3498db'}
    ))
    
    fig.update_layout(
        title={
            'text': f'{title} Frequency Over Time',
            'x': 0.5,
            'xanchor': 'center'
        },
        xaxis_title='Time',
        yaxis_title='Number of Log Entries',
        template='plotly_white',
        height=400
    )
    
    return fig

def create_log_table(df):
    """Create a table of recent log entries."""
    recent_logs = df.tail(10).reset_index()
    
    return html.Table(
        [html.Tr([html.Th('Timestamp'), html.Th('Log Entry')],
                 style={'backgroundColor': '#2c3e50', 'color': 'white'})] +
        [html.Tr([
            html.Td(row['timestamp'].strftime('%Y-%m-%d %H:%M:%S')),
            html.Td(row['line'])
        ]) for _, row in recent_logs.iterrows()],
        style={
            'width': '100%',
            'border': '1px solid #bdc3c7',
            'borderCollapse': 'collapse'
        }
    )

def main():
    port = find_free_port(config.port)
    print(f"\nStarting Log Eagle Dashboard:")
    print(f"* Dashboard URL: http://localhost:{port}")
    print(f"* Reading logs from: {config.log_dir}")
    print(f"* Refresh interval: {config.refresh_interval} seconds\n")
    
    app.run_server(
        host='0.0.0.0',
        port=port,
        debug=False
    )

if __name__ == '__main__':
    main()