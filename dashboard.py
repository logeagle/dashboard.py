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

# Configuration
@dataclass
class Config:
    username: str = os.getenv('USER', 'default_user')
    access_log_dir: str = f"/home/{username}/logeagle"
    error_log_dir: str = f"/home/{username}/logeagle"
    cache_dir: str = "cache-directory"
    cache_timeout: int = 10  # Reduced to 10 seconds for more frequent updates
    port: int = 8050

config = Config()

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

def read_latest_parquet_files(directory: str, prefix: str) -> pd.DataFrame:
    """Read and return the latest Parquet files as a DataFrame."""
    try:
        files = glob.glob(os.path.join(directory, f"{prefix}*.parquet"))
        if not files:
            logger.warning(f"No {prefix} files found in {directory}")
            return pd.DataFrame()

        dfs = []
        for file in sorted(files, reverse=True)[:5]:  # Read last 5 files
            df = pd.read_parquet(file)
            dfs.append(df)

        return pd.concat(dfs, ignore_index=True)
    except Exception as e:
        logger.error(f"Error reading Parquet files: {str(e)}")
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
    if log_type == 'access':
        return read_latest_parquet_files(config.access_log_dir, "access")
    elif log_type == 'error':
        return read_latest_parquet_files(config.error_log_dir, "error")
    else:
        return pd.DataFrame()

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
    if tab == 'tab-1':
        df = get_dataframe('access')
        title = 'Access Logs'
    elif tab == 'tab-2':
        df = get_dataframe('error')
        title = 'Error Logs'
    else:
        return html.Div("Invalid tab selected")

    if df.empty:
        return html.Div(f"No data available for {title}")

    df['timestamp'] = pd.to_datetime(df['timestamp'])
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
    if debug:
        app.run_server(debug=True, port=config.port)
    else:
        logger.info(f"Starting server on port {config.port}")
        serve(server, host='0.0.0.0', port=config.port)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Run the Real-time Log Dashboard app.')
    parser.add_argument('--debug', action='store_true', help='Run in debug mode')
    args = parser.parse_args()

    main(debug=args.debug)