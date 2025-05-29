from dash import html

# Define the layout for the About page
layout = html.Div([
    html.H1("Welcome to the UNITY MRI Dashboard"),
    html.P([
        "This dashboard is designed to visualize MRI data across numerous sites,", html.Br(),
        "providing insights into derived volume estimates and QA MRI data analysis.", html.Br(),
        "The goal is to assist researchers and clinicians in identifying potential issues with the data and to provide a ", html.Br(),
        "comprehensive overview of the data quality across different sites."
    ]),
    
    html.H3("GitHub Repository"),
    html.P("""
        The source code for this app is available on GitHub
    """),
    html.A("GitHub Repository", href="https://github.com/UNITY-Physics/UNITY-Dashboard", target="_blank"),

    html.H3("UNITY Project Website"),
    html.P("""
        More information about the UNITY project can be found on the project website.
        
    """),

    html.A("UNITY Project Website", href="https://www.unity-mri.com/"),

    html.H3("Disclaimer"),
    html.P("""
        Loaded data is synthetic and does not represent real scanner data.
        No warranty is provided for the accuracy of the results.
        The data is generated for educational purposes only.
    """),

    html.H3("Notes:"),
    html.P([
        "- Functionality can be developed as desired.", html.Br(),
        "- If implementing on a real aggregated dataset, ensure that the data is anonymized.", html.Br(),
        "- Will also need to ensure that the data is compliant with the relevant data protection laws.", html.Br(),
        "- If users need to be authenticated, then the app will need to be hosted in a secure environment.", html.Br(),
        "- Could include a project page with summaries of complete data."
    ])

])

