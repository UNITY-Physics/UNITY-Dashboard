import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc
import pages.qa as qa_page
import pages.about as about_page
import pages.home as home_page
import pages.vis as vis_page
import pages.stats as stats_page
from pages.stats import site_filter_sidebar  # Assume unique_sites is defined or accessible globally
import pandas as pd
import os

# Load the synthetic data
def load_data():
    return pd.read_csv(os.path.join( "data/participant_results_data.csv"))

df = load_data()
unique_sites = df['site'].unique()

# Include Font Awesome for icons
external_stylesheets = [
    'https://codepen.io/chriddyp/pen/bWLwgP.css',  # Basic Dash CSS
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.1/css/all.min.css'  # Font Awesome
]

# Create the Dash app
app = dash.Dash(__name__, external_stylesheets=external_stylesheets, suppress_callback_exceptions=True)
# Declare the server for deployment
server = app.server

# Content area
content = html.Div(id="page-content", className="content")

# Sidebar with navigation links and icons
sidebar = html.Div([
    html.Div([
    html.H2('Main Menu', style={'color': 'white'}),
    html.Hr(),
    dcc.Link(html.Div([html.I(className="fas fa-home"), ' Overview']), href='/', style={'color': 'white', 'textDecoration': 'none', 'fontSize': '20px','padding': '10px','display': 'inline-block'}, className='nav-link'),
    html.Br(),
    dcc.Link(
    html.Div([
        html.I(className="fas fa-chart-line"), 
        ' Data Analysis'
    ]), 
    href='/data-analysis', 
    style={
        'color': 'white', 
        'textDecoration': 'none', 
        'fontSize': '20px',  # Adjust text size as needed
        'padding': '10px',  # Add some padding for better appearance
        'display': 'inline-block'  # Ensure proper alignment and spacing
    },
    className='nav-link'  # Use a class for additional styling and to target for highlighting
    ),
    html.Br(),

    dcc.Link(html.Div([html.I(className="fas fa-chart-pie"), ' Data Visualization']), href='/data-visualization', style={'color': 'white', 'textDecoration': 'none', 'fontSize': '20px','padding': '10px','display': 'inline-block'}, className='nav-link'),
    html.Br(),
    dcc.Link(html.Div([html.I(className="fas fa-check-square"), ' QA']), href='/qa', style={'color': 'white', 'textDecoration': 'none', 'fontSize': '20px','padding': '10px','display': 'inline-block'}, className='nav-link'),
    html.Br(),
    dcc.Link(html.Div([html.I(className="fas fa-info-circle"), ' About']), href='/about', style={'color': 'white', 'textDecoration': 'none', 'fontSize': '20px','padding': '10px','display': 'inline-block'}, className='nav-link'),
    ], className='side-box',),
],
    id="sidebar",
    className="sidebar",
    style={
        'padding': '20px',
        'width': '15%',
        'background-color': '#f1f2f6', #'#001f3f',  # Navy color
        'position': 'fixed',
        'height': '100%',
        'overflow': 'auto'
    })

# Main layout including the sidebar and content area
app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    sidebar,
    html.Div(id='page-content', style={'margin-left': '20%'}),
])

# Callback to update page content based on URL
@app.callback(Output('page-content', 'children'),
              [Input('url', 'pathname')])

def display_page(pathname):
    if pathname == '/qa':
        return qa_page.layout
    if pathname == '/about':
        return about_page.layout
    if pathname == '/data-visualization':
        return vis_page.layout
    if pathname == '/data-analysis':
        return [site_filter_sidebar(unique_sites), stats_page.layout]
    # Add conditions for other pages...
    else:
        return home_page.layout

# Register callbacks for each page
qa_page.register_callbacks(app)
vis_page.register_callbacks(app)
stats_page.register_callbacks(app)

# Run the app
if __name__ == '__main__':
    app.run_server(debug=True, port=8050)
