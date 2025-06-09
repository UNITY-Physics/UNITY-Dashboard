import dash
from dash import dcc, html, dash_table, Input, Output
import plotly.express as px
import pandas as pd
import numpy as np

# Load the data
pm_df = pd.read_excel("data/dashboard_datasheet.xlsx")
pm_df.columns = pm_df.columns.str.strip()

# Ensure required columns exist
for col in ["Imaging QC Passed", "Demographics Present", "SES Present", "Cognitive Present", "Metadata Onboarded"]:
    if col not in pm_df.columns:
        pm_df[col] = np.nan

# Create Usable Study logic
usable_fields = [
    "Imaging data on FW", "Demographics Present", "SES Present",
    "Cognitive Present", "Metadata Onboarded", "DTA Status"
]
usability = pm_df[usable_fields].apply(
    lambda row: all(str(v).strip().lower() in ["yes", "complete", "fully executed"] for v in row),
    axis=1
)
pm_df["Usable Study"] = np.where(usability, "yes", "no")
pm_df["Imaging QC %"] = 100 * pm_df["Imaging QC Passed"] / pm_df["session n"]

# Define color coding
status_columns = usable_fields
def status_to_color(val):
    if pd.isna(val): return 'white'
    val = str(val).strip().lower()
    if val in ["complete", "fully executed", "complete; yes", "yes"]:
        return '#b6e8b0'
    elif val in ["onboarded", "partial"]: return '#fff5b1'
    elif val == "in progress": return '#f7c04a'
    elif val == "ready for signature": return '#fff5b1'
    elif val in ["outstanding queries", "no", "not started"]: return '#f8b8b5'
    return 'white'

style_data_conditional = []
for col in status_columns:
    for val in pm_df[col].dropna().unique():
        style_data_conditional.append({
            'if': {'filter_query': f'{{{col}}} = "{val}"', 'column_id': col},
            'backgroundColor': status_to_color(val),
            'color': 'black'
        })

layout = html.Div([
    html.Div(style={
        'backgroundColor': '#f0f4f8',
        'padding': '20px',
        'minHeight': '100vh'
    }, children=[
        dcc.Tabs(id='tabs', value='dashboard', children=[
            dcc.Tab(label='Dashboard', value='dashboard'),
            dcc.Tab(label='Data Completeness Heatmap', value='heatmap')
        ]),
        html.Div(id='tabs-content')
    ])
])

def register_callbacks(app):
    @app.callback(
        Output('tabs-content', 'children'),
        Input('tabs', 'value')
    )
    def render_content(tab):
        if tab == 'dashboard':
            usable_list = pm_df.loc[pm_df['Usable Study'] == 'yes', 'Study'].tolist()
            return html.Div([
                html.Div(style={
                    'backgroundColor': 'white',
                    'borderRadius': '10px',
                    'boxShadow': '0 2px 8px rgba(0, 0, 0, 0.1)',
                    'padding': '20px',
                    'marginBottom': '20px'
                }, children=[
                    html.H1("Project Progress Dashboard", style={"textAlign": "center"}),
                    html.Div(id='summary-kpis', style={
                        'display': 'flex',
                        'justifyContent': 'center',
                        'flexWrap': 'wrap',
                        'gap': '12px',
                        'rowGap': '20px',
                        'maxWidth': '1100px',
                        'margin': 'auto'
                    }),
                    html.Br(),
                    html.H4("Fully Usable Studies", style={"marginTop": "20px"}),
                    html.Ul([html.Li(study) for study in usable_list])
                ]),
                dcc.Dropdown(
                    id='study-filter',
                    options=[{"label": s, "value": s} for s in sorted(pm_df['Study'].dropna().unique())],
                    placeholder="Filter by Study", multi=True
                ),
                dash_table.DataTable(
                    id='project-table',
                    columns=[{"name": col, "id": col} for col in pm_df.columns if not col.startswith("Unnamed")],
                    data=pm_df.to_dict('records'),
                    page_size=10,
                    style_table={'overflowX': 'auto'},
                    style_cell={'textAlign': 'left', 'padding': '5px'},
                    style_data_conditional=style_data_conditional
                ),
                dcc.Graph(id='usable-bar')
            ])

        elif tab == 'heatmap':
            completeness_cols = ["Imaging data on FW", "Metadata Onboarded", "Demographics Present", "SES Present", "Cognitive Present"]
            heatmap_df = pm_df[['Study'] + completeness_cols].drop_duplicates()
            heatmap_data = heatmap_df.set_index('Study')[completeness_cols].applymap(
                lambda x: 'Present' if str(x).strip().lower() == 'yes' else 'Missing'
            )

            fig = px.imshow(
                heatmap_data.replace({'Present': 1, 'Missing': 0}),
                labels=dict(x="Data Types", y="Study"),
                x=heatmap_data.columns,
                y=heatmap_data.index,
                color_continuous_scale=[[0, 'rgba(255, 200, 200, 0.9)'], [1, 'rgba(180, 238, 180, 0.9)']],
                height=600,
                width=900
            )
            fig.update_coloraxes(showscale=False)

            return html.Div([
                html.Div(style={
                    'backgroundColor': 'white',
                    'borderRadius': '10px',
                    'boxShadow': '0 2px 8px rgba(0, 0, 0, 0.1)',
                    'padding': '20px',
                    'marginBottom': '20px',
                    'display': 'flex',
                    'justifyContent': 'center'
                }, children=[
                    html.Div([
                        html.H3("Data Completeness Heatmap", style={"textAlign": "center"}),
                        dcc.Graph(figure=fig)
                    ])
                ])
            ])

    @app.callback(
        Output('project-table', 'data'),
        Output('usable-bar', 'figure'),
        Output('summary-kpis', 'children'),
        Input('study-filter', 'value')
    )
    def update_dashboard(selected_studies):
        filtered_df = pm_df.copy()
        if selected_studies:
            filtered_df = filtered_df[filtered_df['Study'].isin(selected_studies)]

        fig = px.bar(
            filtered_df,
            x='Study',
            y='Imaging QC %',
            color='Organisation',
            title="% Imaging QC Passed by Study",
            labels={'Imaging QC %': '% QC Passed'},
            text='Imaging QC %'
        )
        fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside', marker_opacity=0.7)
        fig.update_layout(yaxis_range=[0, 100])

        avg_usable = round(filtered_df['Imaging QC %'].mean(), 1)
        total_subjects = int(filtered_df['subject n'].sum()) if 'subject n' in filtered_df else 0
        total_sessions = int(filtered_df['session n'].sum()) if 'session n' in filtered_df else 0
        usable_sessions = (filtered_df['Usable Study'] == 'yes').sum()

        def count_status(column, target_values):
            return filtered_df[column].dropna().str.lower().isin(target_values).sum()

        kpi_style = {
            'backgroundColor': 'white',
            'borderRadius': '8px',
            'boxShadow': '0 1px 5px rgba(0, 0, 0, 0.1)',
            'padding': '10px',
            'textAlign': 'center',
            'minWidth': '100px'
        }

        kpis = [
            html.Div([html.H4(f"{avg_usable}%"), html.P("Avg. Imaging QC Passed")], style=kpi_style),
            html.Div([html.H4(f"{total_subjects}"), html.P("Total Subjects")], style=kpi_style),
            html.Div([html.H4(f"{total_sessions}"), html.P("Total Sessions")], style=kpi_style),
            html.Div([html.H4(f"{usable_sessions}"), html.P("Fully Usable Studies")], style=kpi_style),
            html.Div([html.H4(f"{count_status('DTA Status', ['fully executed'])}"), html.P("DTA Signed")], style=kpi_style),
            html.Div([html.H4(f"{count_status('Imaging data on FW', ['yes'])}"), html.P("Imaging Uploaded")], style=kpi_style),
            html.Div([html.H4(f"{count_status('Metadata Onboarded', ['yes'])}"), html.P("Metadata Onboarded")], style=kpi_style),
            html.Div([html.H4(f"{count_status('Demographics Present', ['yes'])}"), html.P("With Demographics")], style=kpi_style),
            html.Div([html.H4(f"{count_status('SES Present', ['yes'])}"), html.P("With SES")], style=kpi_style),
            html.Div([html.H4(f"{count_status('Cognitive Present', ['yes'])}"), html.P("With Cognitive")], style=kpi_style)
        ]

        return filtered_df.to_dict('records'), fig, kpis
