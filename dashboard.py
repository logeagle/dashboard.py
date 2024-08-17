import os
import pandas as pd
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import logging
from flask_caching import Cache
from waitress import serve

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Define a function to read and describe the Parquet files
def read_parquet_file(file_path):
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

# Initialize caching
cache = Cache(app.server, config={
    'CACHE_TYPE': 'filesystem',
    'CACHE_DIR': 'cache-directory'
})
TIMEOUT = 300  # Cache timeout in seconds

# Paths to the Parquet files
access_file_path = os.path.expanduser('~/logeagle/access.parquet')
error_file_path = os.path.expanduser('~/logeagle/error.parquet')

# Read the Parquet files using the function with caching
@cache.memoize(timeout=TIMEOUT)
def get_dataframe(file_path):
    return read_parquet_file(file_path)

# Define the layout of the dashboard
app.layout = html.Div([
    html.H1("Log Dashboard"),
    dcc.Tabs(id='tabs', value='tab-1', children=[
        dcc.Tab(label='Access Logs', value='tab-1'),
        dcc.Tab(label='Error Logs', value='tab-2'),
    ]),
    html.Div(id='tabs-content')
])

# Callback to update the content based on the selected tab
@app.callback(Output('tabs-content', 'children'),
              [Input('tabs', 'value')])
def render_content(tab):
    if tab == 'tab-1':
        df = get_dataframe(access_file_path)
        title = 'Access Logs'
    elif tab == 'tab-2':
        df = get_dataframe(error_file_path)
        title = 'Error Logs'
    else:
        return html.Div("Invalid tab selected")

    if df.empty:
        return html.Div(f"No data available for {title}")

    return html.Div([
        html.H3(title),
        dcc.Graph(
            id=f'{tab}-graph',
            figure={
                'data': [
                    {'x': df.index, 'y': df[col], 'type': 'line', 'name': col}
                    for col in df.columns
                ],
                'layout': {
                    'title': f'{title} Over Time'
                }
            }
        )
    ])

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Run the Log Dashboard app.')
    parser.add_argument('--debug', action='store_true', help='Run in debug mode')
    parser.add_argument('--port', type=int, default=8050, help='Port to run the server on')
    args = parser.parse_args()

    if args.debug:
        app.run_server(debug=True, port=args.port)
    else:
        serve(server, host='0.0.0.0', port=args.port)