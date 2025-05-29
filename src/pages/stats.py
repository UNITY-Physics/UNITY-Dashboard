# pages/stats.py

from dash.dependencies import Input, Output, State
import pandas as pd
from dash import html, dcc, dash_table
import io 
import base64
import os

# Load the synthetic data
def load_data():
    return pd.read_csv(os.path.join(os.getcwd(),"src/data/participant_results_data.csv"))

df = load_data()
unique_sites = df['site'].unique()

from dash import dcc, html

def site_filter_sidebar(unique_sites):
    """Returns a sidebar component for site filtering specific to the data analysis page."""
    return html.Div([
        html.H4("Site Filter", style={'color': 'white', 'marginTop': '20px'}),
        dcc.Dropdown(
            id='selected-site',
            options=[{'label': "All", 'value': "All"}] + [{'label': site, 'value': site} for site in unique_sites],
            value="All",
            style={'color': 'black'}
        )
    ], style={'padding': '20px', 'background-color': '#001f3f'})


# Create the layout for the stats page
layout = html.Div([
    html.H3("Study Descriptive Statistics"),
    html.Label("Please choose a variable to display descriptive statistics:"),
    
    dcc.Dropdown(
        id='variable-dropdown',
        options=[{'label': var, 'value': var} for var in df.columns if var not in ['subjectID', 'sessionID', 'site', 'sex', 'group', 'Timestamp']],
        value='age'  # Default selection
    ),
    html.Br(),
    html.P(id='dropdown-output'),  # Placeholder for descriptive text

    html.Div(id='stats-output'),  # Placeholder for stats table

    # Button for triggering CSV download
    html.Button("Download CSV", id="download-button", n_clicks=0),
    
    # dcc.Download component to trigger the file download
    dcc.Download(id="download-data"),
])

# Callbacks registered in app.py that takes the app as an argument.
def register_callbacks(app):
    @app.callback(
    Output('stats-output', 'children'),
    Output('dropdown-output', 'children'),
    [Input('selected-site', 'value'), 
     Input('variable-dropdown', 'value')]
    )
    def update_output(selected_site, selected_variable):
        # Filter data based on selection
        filtered_data = df[df['site'] == selected_site] if selected_site != 'All' else df
        
        # Calculate descriptive statistics
        stats = filtered_data[selected_variable].describe().reset_index()
        stats.columns = ['Statistic', 'Value']
        
        # Generate table
        stats_table = dash_table.DataTable(
            data=stats.to_dict('records'),
            columns=[{'id': c, 'name': c} for c in stats.columns],
            style_cell={'textAlign': 'left'},
        )

        # Generate descriptive text
        descriptive_text = html.P(f"Descriptive statistics for the selected variable: {selected_variable} (site: {selected_site})")

        return stats_table, descriptive_text

    # @app.callback(
    #     Output('download-data', 'href'),
    #     [Input('selected-site', 'value'), 
    #     Input('variable-dropdown', 'value')]
    # )
    # def generate_csv(selected_site, selected_variable):
    #     # Filter data based on selection
    #     filtered_data = df[df['site'] == selected_site] if selected_site != 'All' else df
    #     stats = filtered_data[selected_variable].describe().reset_index()
    #     stats.columns = ['Statistic', 'Value']
        
    #     # Save to CSV
    #     output_df = pd.DataFrame(stats)
    #     csv_filename = f"{selected_variable}_data.csv"
    #     csv_file_path = os.path.join(app.server.static_folder, csv_filename)

    #     output_df.to_csv(csv_file_path, index=False)
        
    #     return f'/{csv_filename}'

    @app.callback(
    Output("download-data", "data"),
    [Input("download-button", "n_clicks")],
    [State('selected-site', 'value'), 
     State('variable-dropdown', 'value')]
    )
    def generate_csv(n_clicks, selected_site, selected_variable):
        if n_clicks > 0:
            # Filter data based on selection
            filtered_data = df[df['site'] == selected_site] if selected_site != 'All' else df
            stats = filtered_data[selected_variable].describe().reset_index()
            stats.columns = ['Statistic', 'Value']
            
            # Convert to CSV and encode as base64
            output_df = pd.DataFrame(stats)
            
            # Save the DataFrame to a CSV in memory using a buffer
            buffer = io.StringIO()
            output_df.to_csv(buffer, index=False)
            buffer.seek(0)
            
            # Convert the CSV content to base64 for downloading
            csv_content = buffer.getvalue()
            csv_base64 = base64.b64encode(csv_content.encode()).decode()

            return dict(content=buffer.getvalue(), filename=f"{selected_variable}_data.csv")
        
        return None  # No download if the button hasn't been clicked yet