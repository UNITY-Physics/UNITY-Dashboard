# pages/vis.py
import dash
from dash.dependencies import Input, Output
import plotly.express as px
import pandas as pd
from scipy.stats import pearsonr
import numpy as np
from dash import html, dcc
import statsmodels.api as sm
import plotly.graph_objects as go
from dash.exceptions import PreventUpdate
import os 

# Load the synthetic data
def load_data():
    return pd.read_csv(os.path.join(os.getcwd(), "src/data/participant_results_data.csv"))

df = load_data()
unique_sites = df['site'].unique()
categorical_vars = ['sex', 'group']
continuous_vars = ['age', 'GSED']
y_axis_options = [col for col in df.columns if col not in ['subjectID', 'sessionID', 'site', 'sex']]

# Create the layout for the stats page
layout = html.Div([
    html.H3("Descriptive Figures"),
    html.Div([
    html.Div(id='stats-output'),
    dcc.Graph(id='boxplot-graph'),
        html.B("Select a site:"),
        dcc.Dropdown(id='selected-site', options=[{"label": "All", "value": "All"}] + [{"label": site, "value": site} for site in unique_sites], value="All"),
        html.B("Select a categorical variable: x-axis"),
        dcc.Dropdown(id='selected-cat-var', options=[{"label": var, "value": var} for var in categorical_vars], value=categorical_vars[0]),
        html.B("Select a continuous variable: y-axis"),
        dcc.Dropdown(id='selected-cont-var', options=[{"label": var, "value": var} for var in continuous_vars], value=continuous_vars[0]),
        html.H1(""),  # Add a blank line
        html.B("Select additional grouping variable to compare:"),
        dcc.Dropdown(id='selected-group-var', options=[{"label": "None", "value": "none"}] + [{"label": var, "value": var} for var in categorical_vars], value="none"),
        dcc.Checklist(
            id='jitter-toggle',
            options=[{'label': 'Show Individual Data Points', 'value': 'jitter'}],
            value=[]  # By default, jitter is turned off
    ),
    ], className='data-box'),
    html.Div([  
    dcc.Graph(id='scatter-plot'),
        html.B("Select a continuous variable: y-axis"),
        dcc.Dropdown(id='selected-y-axis', options=[{"label": var, "value": var} for var in y_axis_options], value='TICV'),
        html.B("Select a model for the trendline:"),
        dcc.Dropdown(id='model-options', options=[{"label": "None", "value": "None"}, {"label": "Linear (OLS)", "value": "ols"}, {"label": "Non-linear relationships", "value": "lowess"}, {"label": "Trends: expanding", "value": "expanding"}], value="None"),
    ], className='data-box'),
    ])

# Callbacks registered in app.py that takes the app as an argument.
def register_callbacks(app):
    # callback for updating the boxplot
    @app.callback(
        Output('boxplot-graph', 'figure'),
        [Input('selected-site', 'value'),
        Input('selected-cat-var', 'value'),
        Input('selected-cont-var', 'value'),
        Input('selected-group-var', 'value'),
        Input('jitter-toggle', 'value')] 
    )

    def update_boxplot(selected_site, selected_cat_var, selected_cont_var, selected_group_var, jitter_value):
        filtered_df = df[df['site'] == selected_site] if selected_site != 'All' else df
        jitter = 'all' if 'jitter' in jitter_value else False

        if selected_group_var == "none":
            boxplot_fig = px.box(filtered_df, x=selected_cat_var, y=selected_cont_var, points=jitter, title=f'{selected_cont_var} by {selected_cat_var}')  # Adjust based on your needs
            return boxplot_fig
        else:
            boxplot_fig = px.box(filtered_df, x=selected_cat_var, y=selected_cont_var, points=jitter, color=selected_group_var, title=f'{selected_cont_var} by {selected_cat_var}')  # Adjust based on your needs
            return boxplot_fig
          
    # callback for updating the scatter plot
    @app.callback(
        Output('scatter-plot', 'figure'),
        [Input('selected-y-axis', 'value'),
        Input('model-options', 'value')]  # Assuming 'model-options' determines the trendline type
    )

    def update_scatter(selected_y_axis, model_options):
        trendline = model_options if model_options in ['ols', 'lowess', 'expanding'] else None
        scatter_fig = px.scatter(df, x='age', y=selected_y_axis, trendline=trendline, title=f'{selected_y_axis} vs. Age')
        return scatter_fig


