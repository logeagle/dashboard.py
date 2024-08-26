import os
import pandas as pd
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import logging
from flask_caching import Cache
from waitress import serve
import yaml
from typing import Dict, Any
import plotly.graph_objs as go
from dataclasses import dataclass

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("dashboard.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class Config:
    access_log_path: str
    error_log_path: str
    cache_dir: str
    cache_timeout: int
    port: int

def load_config(config_path: str) -> Config:
    try:
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        return Config(**config_data)
    except Exception as e:
        logger.error(f"Error loading configuration: {str(e)}")
        raise

# Define a function to read and describe the Parquet files
def read_parquet_file(file_path: str) -> pd.DataFrame:
    try:
        if os.path.exists(file_path):
            df = pd.read_parquet(file_path)
            return df
        else:
            logger.error(f"File not found: {file_path}")
            return pd.DataFrame()  # Return an empty DataFrame if file not found
    except Exception as e:
        logger.error(f"Error reading Parquet file {file_path}: {str(e)}")
        return pd.DataFrame()

# Initialize the Dash app
app = dash.Dash(__name__, suppress_callback_exceptions=True)
server = app.server

# Load configuration
config = load_config('config.yaml')

# Initialize caching
cache = Cache(app.server, config={
    'CACHE_TYPE': 'filesystem',
    'CACHE_DIR': config.cache_dir
})

# Read the Parquet files using the function with caching
@cache.memoize(timeout=config.cache_timeout)
def get_dataframe(file_path: str) -> pd.DataFrame:
    return read_parquet_file(file_path)

# Define the layout of the dashboard
app.layout = html.Div([
    html.H1("Log Dashboard"),
    dcc.Tabs(id='tabs', value='tab-1', children=[
        dcc.Tab(label='Access Logs', value='tab-1'),
        dcc.Tab(label='Error Logs', value='tab-2'),
    ]),
    html.Div(id='tabs-content'),
    dcc.Interval(
        id='interval-component',
        interval=60*1000,  # in milliseconds
        n_intervals=0
    )
])

# Callback to update the content based on the selected tab
@app.callback(
    Output('tabs-content', 'children'),
    [Input('tabs', 'value'),
     Input('interval-component', 'n_intervals')]
)
def render_content(tab: str, n: int) -> html.Div:
    if tab == 'tab-1':
        df = get_dataframe(config.access_log_path)
        title = 'Access Logs'
    elif tab == 'tab-2':
        df = get_dataframe(config.error_log_path)
        title = 'Error Logs'
    else:
        return html.Div("Invalid tab selected")

    if df.empty:
        return html.Div(f"No data available for {title}")

    # Perform some basic analysis
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.set_index('timestamp')
    df = df.resample('1H').count()  # Resample to hourly data

    # Create a line plot
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df['line'], mode='lines', name='Log Entries'))
    fig.update_layout(title=f'{title} Over Time', xaxis_title='Time', yaxis_title='Number of Log Entries')

    return html.Div([
        html.H3(title),
        dcc.Graph(
            id=f'{tab}-graph',
            figure=fig
        ),
        html.Div(f"Last updated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")
    ])

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Run the Log Dashboard app.')
    parser.add_argument('--debug', action='store_true', help='Run in debug mode')
    args = parser.parse_args()

    if args.debug:
        app.run_server(debug=True, port=config.port)
    else:
        logger.info(f"Starting server on port {config.port}")
        serve(server, host='0.0.0.0', port=config.port)
