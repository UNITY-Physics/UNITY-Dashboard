from dash import html, dcc
from dash.dependencies import Input, Output
import plotly.express as px
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import os

# Example DataFrame for demonstration purposes
# qa_data = pd.read_csv('data/phantom_qa_data.csv')
qa_data = pd.read_csv('data/RWE_PSNR.csv') #/Users/Hajer/unity/QA/UNITY-Dashboard/src/data/RWE_PSNR.csv
#qa_data['Date'] = pd.to_datetime(qa_data['Session'].str.split(" ")[0], format='%Y-%m-%d')  # Assuming 'Session' contains date information
# Convert to datetime, replacing '_' with ':' in the time
 # Sort by Session for better time series visualization
 
qa_data['timestamp'] = pd.to_datetime(qa_data['Session'].str.replace('_', ':'))
qa_data = qa_data.sort_values(by=['Location', 'timestamp'])


# Create a new column with Year-Month
qa_data['Date'] = qa_data['timestamp'].dt.strftime('%-d %b %y')  #.dt.to_period("M").astype(str)
qa_data.dropna(subset=['Location'],inplace=True)

qa_data['Location'] = qa_data['Location']  # Replace spaces with underscores for consistency

sites = sorted([str(site) for site in qa_data['Location'].dropna().unique()])  # Get unique sites and sort them
# metrics = ['Scanner Frequency', 'Temperature', 'Timestamp', 'SNR', 'T2w contrast ratio', 'Geometric Distortion AP', 'Geometric Distortion SI', 'Geometric Distortion LR']  # Assuming these are the metrics
metrics = ['PSNR', 'MSE', 'NMI', 'SSIM', 'Temperature']  # 'SoftwareVersion',

# QA Page layout
layout = html.Div([
    html.Div([
    html.H3('QA Analysis'),
    dcc.Graph(id='qa-boxplot-graph'),
    html.B('Select a metric:'),
    dcc.Dropdown(id='metric-dropdown', options=[{'label': metric, 'value': metric} for metric in metrics], value=metrics[0]),
    ], className='data-box'),

    html.Div([
    html.B('Select a site:'),
    dcc.Dropdown(id='qa-site-dropdown', options=[{'label': site, 'value': site} for site in sites], value=sites[0]),
    dcc.Graph(id='qa-time-series-graph')
    ], className='data-box')

    # html.Div([
    # html.B('Software Versions Across Sites Over Time'),
    # dcc.Graph(id='qa-heatmap-graph')
    # ], className='data-box')

])

# Callback registration function
def register_callbacks(app):
    @app.callback(
        [Output('qa-time-series-graph', 'figure'),  # First graph output
         Output('qa-boxplot-graph', 'figure')],    # Second graph output
        [Input('qa-site-dropdown', 'value'),       # First input
         Input('metric-dropdown', 'value')]        # Second input
    )
    def update_charts(selected_site, selected_metric):
        # Filter data for the selected site
        filtered_data = qa_data[qa_data['Location'] == selected_site]
        filtered_data.to_csv(os.path.join('data', 'tmp_output.csv'), index=False)

        # Generate time series figure
        time_series_fig = px.line(
            filtered_data, 
            x='Date', 
            y=selected_metric,
            markers=True,
            title=f'{selected_metric} Over Time for {selected_site}')
        
        # Generate boxplot figure
        boxplot_fig = px.box(qa_data, x='Location', 
                            y=selected_metric,
                            color='Location',  # Add color based on the Site variable
                            # points='all',  # Overlay all individual data points
                            title=f'{selected_metric} Distribution by Site')

        # Add scatter plot for all individual points
        boxplot_fig.add_trace(go.Scatter(
            x=qa_data['Location'],
            y=qa_data[selected_metric],
            mode='markers',
            marker=dict(color='rgba(107,174,214,0.6)', size=6),
            name='Data Points',
            showlegend=False  # Hide legend for the scatter plot
        ))
        boxplot_fig.update_traces(marker_opacity=0.6, showlegend=False)

        return time_series_fig, boxplot_fig
    