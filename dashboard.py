import os
import pandas as pd
import dash
import subprocess
from dash import dcc, html
from dash.dependencies import Input, Output

# Define a function to read and describe the Parquet files
def read_parquet_file(file_path):
    if os.path.exists(file_path):
        df = pd.read_parquet(file_path)
        return df
    else:
        print(f"File not found: {file_path}")
        return pd.DataFrame()  # Return an empty DataFrame if file not found

# Initialize the Dash app
app = dash.Dash(__name__)

#Checking for usename so the file can get dynamic fetching
username = subprocess.check_output(['whoami']).decode().strip()

# Paths to the Parquet files
access_file_path = '/home/{username}/logeagle/access.parquet'
error_file_path = '/home/{username}/logeagle/error.parquet'

# Read the Parquet files using the function
access_df = read_parquet_file(access_file_path)
error_df = read_parquet_file(error_file_path)

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
        return html.Div([
            html.H3('Access Logs'),
            dcc.Graph(
                id='access-graph',
                figure={
                    'data': [
                        {'x': access_df.index, 'y': access_df[col], 'type': 'line', 'name': col}
                        for col in access_df.columns
                    ],
                    'layout': {
                        'title': 'Access Logs Over Time'
                    }
                }
            )
        ])
    elif tab == 'tab-2':
        return html.Div([
            html.H3('Error Logs'),
            dcc.Graph(
                id='error-graph',
                figure={
                    'data': [
                        {'x': error_df.index, 'y': error_df[col], 'type': 'line', 'name': col}
                        for col in error_df.columns
                    ],
                    'layout': {
                        'title': 'Error Logs Over Time'
                    }
                }
            )
        ])

# Run the app on localhost port 1234
if __name__ == '__main__':
    app.run_server(debug=True, port=1234)
