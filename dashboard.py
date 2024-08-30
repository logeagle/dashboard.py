#!/usr/bin/env python3

import os
import pandas as pd
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import logging
from flask_caching import Cache
from waitress import serve
import plotly.graph_objs as go
from dataclasses import dataclass
from typing import Dict, Any
import glob
import socket
import traceback

# Configuration
@dataclass
class Config:
    username: str = os.getenv('USER', 'default_user')
    log_dir: str = os.path.expanduser("~/logeagle")
    cache_dir: str = os.path.join(os.path.expanduser("~/logeagle"), "cache")
    cache_timeout: int = 10  # Reduced to 10 seconds for more frequent updates
    port: int = 8050

config = Config()

# Ensure the log and cache directories exist
os.makedirs(config.log_dir, exist_ok=True)
os.makedirs(config.cache_dir, exist_ok=True)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(config.log_dir, "dashboard.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def find_free_port(start_port: int = 8050, max_port: int = 9000) -> int:
    """Find a free port to use for the server."""
    for port in range(start_port, max_port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('', port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"Could not find a free port between {start_port} and {max_port}")

def read_latest_parquet_files(directory: str, prefix: str) -> pd.DataFrame:
    """Read and return the latest Parquet files as a DataFrame."""
    try:
        files = glob.glob(os.path.join(directory, f"{prefix}*.parquet"))
        if not files:
            logger.warning(f"No {prefix} files found in {directory}")
            return pd.DataFrame()

        dfs = []
        for file in sorted(files, reverse=True)[:5]:  # Read last 5 files
            try:
                logger.info(f"Attempting to read file: {file}")
                df = pd.read_parquet(file)
                dfs.append(df)
                logger.info(f"Successfully read file: {file}")
            except Exception as e:
                logger.error(f"Error reading file {file}: {str(e)}")
                logger.error(traceback.format_exc())

        if not dfs:
            logger.warning(f"No valid Parquet files found for {prefix}")
            return pd.DataFrame()

        result = pd.concat(dfs, ignore_index=True)
        logger.info(f"Combined DataFrame shape: {result.shape}")
        return result
    except Exception as e:
        logger.error(f"Error reading Parquet files: {str(e)}")
        logger.error(traceback.format_exc())
        return pd.DataFrame()

# Initialize the Dash app
app = dash.Dash(__name__, suppress_callback_exceptions=True)
server = app.server

# Initialize caching
cache = Cache(app.server, config={
    'CACHE_TYPE': 'filesystem',
    'CACHE_DIR': config.cache_dir
})

@cache.memoize(timeout=config.cache_timeout)
def get_dataframe(log_type: str) -> pd.DataFrame:
    """Cached function to read Parquet files."""
    return read_latest_parquet_files(config.log_dir, log_type)

# Define the layout of the dashboard
app.layout = html.Div([
    html.H1("Real-time Log Dashboard", className="dashboard-title"),
    dcc.Tabs(id='tabs', value='tab-1', children=[
        dcc.Tab(label='Access Logs', value='tab-1'),
        dcc.Tab(label='Error Logs', value='tab-2'),
    ]),
    html.Div(id='tabs-content'),
    dcc.Interval(
        id='interval-component',
        interval=10*1000,  # in milliseconds, update every 10 seconds
        n_intervals=0
    )
])

@app.callback(
    Output('tabs-content', 'children'),
    [Input('tabs', 'value'),
     Input('interval-component', 'n_intervals')]
)
def render_content(tab: str, n: int) -> html.Div:
    """Callback to update the content based on the selected tab."""
    logger.info(f"Rendering content for tab: {tab}")
    if tab == 'tab-1':
        df = get_dataframe('access')
        title = 'Access Logs'
    elif tab == 'tab-2':
        df = get_dataframe('error')
        title = 'Error Logs'
    else:
        logger.warning(f"Invalid tab selected: {tab}")
        return html.Div("Invalid tab selected")

    if df.empty:
        logger.warning(f"No data available for {title}")
        return html.Div(f"No data available for {title}. Please check if the log processor is running and generating log files.")

    logger.info(f"DataFrame shape for {title}: {df.shape}")
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
    df = df.set_index('timestamp').sort_index()
    df_resampled = df.resample('1min').count()  # Resample to 1-minute intervals

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_resampled.index, y=df_resampled['line'], mode='lines', name='Log Entries'))
    fig.update_layout(
        title=f'{title} Over Time (Last 5 Files)',
        xaxis_title='Time',
        yaxis_title='Number of Log Entries',
        template='plotly_white'
    )

    return html.Div([
        html.H3(title, className="section-title"),
        dcc.Graph(id=f'{tab}-graph', figure=fig),
        html.Div(f"Last updated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}", className="update-time")
    ])

def main(debug: bool = False):
    """Main function to run the application."""
    port = find_free_port(config.port)
    if debug:
        app.run_server(debug=True, port=port)
    else:
        logger.info(f"Starting server on port {port}")
        logger.info(f"Reading log files from: {config.log_dir}")
        serve(app.server, host='0.0.0.0', port=port)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Run the Real-time Log Dashboard app.')
    parser.add_argument('--debug', action='store_true', help='Run in debug mode')
    args = parser.parse_args()

    main(debug=args.debug)