
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
from pathlib import Path

# =============================================================================
# CONFIGURATION
# =============================================================================

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_PATH = PROJECT_ROOT / 'data'
FIGURES_PATH = PROJECT_ROOT / 'figures'

# Créer le dossier figures si nécessaire
FIGURES_PATH.mkdir(exist_ok=True)

# =============================================================================
# DARK THEME CONFIGURATION
# =============================================================================

DARK_THEME = {
    'bg_color': '#1a1a2e',
    'card_bg': 'rgba(255, 255, 255, 0.05)',
    'text_color': '#ffffff',
    'accent_blue': '#00d4ff',
    'accent_purple': '#7b2cbf',
    'accent_green': '#00b894',
    'accent_orange': '#f39c12',
    'accent_red': '#e74c3c',
    'accent_pink': '#fd79a8',
    'grid_color': 'rgba(255, 255, 255, 0.1)'
}

# Custom dark template for plotly
dark_template = go.layout.Template()
dark_template.layout = go.Layout(
    paper_bgcolor=DARK_THEME['bg_color'],
    plot_bgcolor='rgba(255, 255, 255, 0.02)',
    font=dict(color=DARK_THEME['text_color'], family='Segoe UI, sans-serif'),
    title=dict(font=dict(size=20, color=DARK_THEME['accent_blue'])),
    xaxis=dict(
        gridcolor=DARK_THEME['grid_color'],
        linecolor=DARK_THEME['grid_color'],
        tickfont=dict(color='#a0a0a0')
    ),
    yaxis=dict(
        gridcolor=DARK_THEME['grid_color'],
        linecolor=DARK_THEME['grid_color'],
        tickfont=dict(color='#a0a0a0')
    ),
    colorway=[DARK_THEME['accent_blue'], DARK_THEME['accent_purple'], 
              DARK_THEME['accent_green'], DARK_THEME['accent_orange'],
              DARK_THEME['accent_red'], DARK_THEME['accent_pink']]
)

# HTML wrapper with dark styling and back button
def wrap_html_dark(fig, title, back_link="index.html"):
    """Wrap plotly figure in dark themed HTML with navigation"""
    html_content = f'''<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - Northwind BI</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            min-height: 100vh;
            color: #fff;
        }}
        .nav-bar {{
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            padding: 15px 30px;
            display: flex;
            align-items: center;
            gap: 20px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }}
        .back-btn {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 10px 20px;
            background: linear-gradient(135deg, #00d4ff, #0099cc);
            color: white;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 500;
            transition: all 0.3s ease;
        }}
        .back-btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(0, 212, 255, 0.4);
        }}
        .page-title {{
            font-size: 1.3rem;
            color: #00d4ff;
        }}
        .chart-container {{
            padding: 20px;
        }}
    </style>
</head>
<body>
    <nav class="nav-bar">
        <a href="{back_link}" class="back-btn">← Retour au Dashboard</a>
        <span class="page-title">{title}</span>
    </nav>
    <div class="chart-container">
        {fig.to_html(full_html=False, include_plotlyjs='cdn')}
    </div>
</body>
</html>'''
    return html_content

# =============================================================================
# CHARGEMENT DES DONNÉES
# =============================================================================

def load_data():
    """Charger les données depuis les fichiers CSV générés par l'ETL dual source"""
    data = {}
    
    files = [
        'Fact_Sales', 'Dim_Customers', 'Dim_Products', 'Dim_Employees', 'Dim_Time',
        'Sales_By_Month', 'Sales_By_Category', 'Sales_By_Country', 'Top_Products',
        'High_Freight_Orders', 'Late_Deliveries'
    ]
    
    for file in files:
        filepath = DATA_PATH / f'{file}.csv'
        if filepath.exists():
            data[file] = pd.read_csv(filepath)
            print(f"✅ {file} chargé: {len(data[file])} lignes")
        else:
            print(f"⚠️ {file} non trouvé")
            data[file] = pd.DataFrame()
    
    # Convertir les dates
    if not data['Fact_Sales'].empty and 'OrderDate' in data['Fact_Sales'].columns:
        data['Fact_Sales']['OrderDate'] = pd.to_datetime(data['Fact_Sales']['OrderDate'], errors='coerce')
    
    return data

# =============================================================================
# CALCUL DES KPIs
# =============================================================================

def calculate_kpis(data):
    """Calculer les indicateurs clés incluant freight>500 et late deliveries"""
    fact_sales = data['Fact_Sales']
    
    if fact_sales.empty:
        return {}
    
    # Déterminer la colonne de montant (SalesAmount ou TotalAmount)
    amount_col = 'SalesAmount' if 'SalesAmount' in fact_sales.columns else 'TotalAmount'
    
    kpis = {
        'total_revenue': fact_sales[amount_col].sum() if amount_col in fact_sales.columns else 0,
        'total_orders': fact_sales['OrderID'].nunique(),
        'avg_order_value': fact_sales[amount_col].sum() / fact_sales['OrderID'].nunique() if amount_col in fact_sales.columns else 0,
        'total_quantity': fact_sales['Quantity'].sum() if 'Quantity' in fact_sales.columns else 0,
        'total_customers': fact_sales['CustomerID'].nunique() if 'CustomerID' in fact_sales.columns else 0,
        'total_products': fact_sales['ProductID'].nunique() if 'ProductID' in fact_sales.columns else 0,
    }
    
    # KPIs spécifiques au projet (requis)
    if 'IsHighFreight' in fact_sales.columns:
        kpis['high_freight_orders'] = fact_sales[fact_sales['IsHighFreight'] == True]['OrderID'].nunique()
    else:
        high_freight = data.get('High_Freight_Orders', pd.DataFrame())
        kpis['high_freight_orders'] = len(high_freight)
    
    if 'IsLateDelivery' in fact_sales.columns:
        kpis['late_deliveries'] = fact_sales[fact_sales['IsLateDelivery'] == True]['OrderID'].nunique()
    else:
        late_deliveries = data.get('Late_Deliveries', pd.DataFrame())
        kpis['late_deliveries'] = len(late_deliveries)
    
    # Source de données stats
    if 'DataSource' in fact_sales.columns:
        kpis['sql_server_records'] = len(fact_sales[fact_sales['DataSource'] == 'SQLServer'])
        kpis['access_records'] = len(fact_sales[fact_sales['DataSource'] == 'Access'])
    
    return kpis

# =============================================================================
# CRÉATION DES GRAPHIQUES
# =============================================================================

def create_kpi_cards(kpis):
    """Créer les cartes KPI incluant les KPIs requis (freight>500, late deliveries)"""
    fig = make_subplots(
        rows=2, cols=4,
        specs=[[{'type': 'indicator'}]*4, [{'type': 'indicator'}]*4]
    )
    
    indicators = [
        ('💰 Chiffre d\'affaires', kpis.get('total_revenue', 0), '$', ',.0f'),
        ('📋 Commandes', kpis.get('total_orders', 0), '', ','),
        ('💵 Panier moyen', kpis.get('avg_order_value', 0), '$', ',.2f'),
        ('👥 Clients actifs', kpis.get('total_customers', 0), '', ','),
        ('📦 Quantité vendue', kpis.get('total_quantity', 0), '', ','),
        ('🛒 Produits vendus', kpis.get('total_products', 0), '', ','),
        ('🚚 Freight > 500', kpis.get('high_freight_orders', 0), '', ','),
        ('⏰ Livraisons retard', kpis.get('late_deliveries', 0), '', ',')
    ]
    
    positions = [(1,1), (1,2), (1,3), (1,4), (2,1), (2,2), (2,3), (2,4)]
    
    colors = [DARK_THEME['accent_blue'], DARK_THEME['accent_blue'], 
              DARK_THEME['accent_green'], DARK_THEME['accent_purple'], 
              DARK_THEME['accent_blue'], DARK_THEME['accent_green'], 
              DARK_THEME['accent_red'], DARK_THEME['accent_orange']]
    
    for i, ((title, value, prefix, fmt), (row, col)) in enumerate(zip(indicators, positions)):
        fig.add_trace(
            go.Indicator(
                mode='number',
                value=value,
                title={'text': title, 'font': {'size': 14, 'color': '#a0a0a0'}},
                number={'prefix': prefix, 'valueformat': fmt, 'font': {'size': 28, 'color': colors[i]}}
            ),
            row=row, col=col
        )
    
    fig.update_layout(
        title_text='📊 Indicateurs Clés de Performance (KPIs)',
        height=400,
        paper_bgcolor=DARK_THEME['bg_color'],
        plot_bgcolor=DARK_THEME['bg_color'],
        font=dict(color=DARK_THEME['text_color'])
    )
    
    return fig

def create_sales_trend(data):
    """Créer le graphique d'évolution des ventes"""
    fact_sales = data['Fact_Sales']
    
    if fact_sales.empty:
        return go.Figure()
    
    # Déterminer la colonne de montant
    amount_col = 'SalesAmount' if 'SalesAmount' in fact_sales.columns else 'TotalAmount'
    
    monthly_sales = fact_sales.groupby(
        fact_sales['OrderDate'].dt.to_period('M')
    )[amount_col].sum().reset_index()
    monthly_sales['OrderDate'] = monthly_sales['OrderDate'].astype(str)
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=monthly_sales['OrderDate'],
        y=monthly_sales[amount_col],
        mode='lines+markers',
        fill='tozeroy',
        line=dict(color=DARK_THEME['accent_blue'], width=3),
        marker=dict(size=8, color=DARK_THEME['accent_blue']),
        fillcolor='rgba(0, 212, 255, 0.2)'
    ))
    
    fig.update_layout(
        title='📈 Évolution mensuelle du chiffre d\'affaires',
        xaxis_title='Période',
        yaxis_title='Ventes ($)',
        paper_bgcolor=DARK_THEME['bg_color'],
        plot_bgcolor='rgba(255, 255, 255, 0.02)',
        font=dict(color=DARK_THEME['text_color']),
        xaxis=dict(gridcolor=DARK_THEME['grid_color'], tickfont=dict(color='#a0a0a0')),
        yaxis=dict(gridcolor=DARK_THEME['grid_color'], tickfont=dict(color='#a0a0a0')),
        height=500
    )
    return fig

def create_category_chart(data):
    """Créer le graphique des ventes par catégorie"""
    sales_by_category = data['Sales_By_Category']
    
    if sales_by_category.empty:
        return go.Figure()
    
    # Déterminer les noms de colonnes (Category ou CategoryName)
    cat_col = 'Category' if 'Category' in sales_by_category.columns else 'CategoryName'
    
    fig = make_subplots(
        rows=1, cols=2,
        specs=[[{'type': 'pie'}, {'type': 'bar'}]],
        subplot_titles=('Répartition (%)', 'Montant ($)')
    )
    
    colors = [DARK_THEME['accent_blue'], DARK_THEME['accent_purple'], 
              DARK_THEME['accent_green'], DARK_THEME['accent_orange'],
              DARK_THEME['accent_red'], DARK_THEME['accent_pink'],
              '#00cec9', '#fdcb6e']
    
    # Pie chart
    fig.add_trace(
        go.Pie(
            labels=sales_by_category[cat_col],
            values=sales_by_category['TotalSales'],
            hole=0.4,
            textinfo='percent+label',
            textposition='outside',
            marker=dict(colors=colors),
            textfont=dict(color='#a0a0a0')
        ),
        row=1, col=1
    )
    
    # Bar chart
    sorted_data = sales_by_category.sort_values('TotalSales', ascending=True)
    fig.add_trace(
        go.Bar(
            x=sorted_data['TotalSales'],
            y=sorted_data[cat_col],
            orientation='h',
            marker=dict(
                color=sorted_data['TotalSales'],
                colorscale=[[0, DARK_THEME['accent_purple']], [1, DARK_THEME['accent_blue']]]
            ),
            text=[f'${x:,.0f}' for x in sorted_data['TotalSales']],
            textposition='outside',
            textfont=dict(color='#a0a0a0')
        ),
        row=1, col=2
    )
    
    fig.update_layout(
        title_text='📦 Ventes par catégorie de produits',
        height=500,
        showlegend=False,
        paper_bgcolor=DARK_THEME['bg_color'],
        plot_bgcolor='rgba(255, 255, 255, 0.02)',
        font=dict(color=DARK_THEME['text_color'])
    )
    fig.update_xaxes(gridcolor=DARK_THEME['grid_color'], tickfont=dict(color='#a0a0a0'))
    fig.update_yaxes(gridcolor=DARK_THEME['grid_color'], tickfont=dict(color='#a0a0a0'))
    
    return fig

def create_country_chart(data):
    """Créer le graphique des ventes par pays"""
    sales_by_country = data['Sales_By_Country']
    
    if sales_by_country.empty:
        return go.Figure()
    
    # Top 10 pays
    top_countries = sales_by_country.nlargest(10, 'TotalSales')
    
    fig = go.Figure(go.Bar(
        x=top_countries['Country'],
        y=top_countries['TotalSales'],
        marker=dict(
            color=top_countries['TotalSales'],
            colorscale=[[0, DARK_THEME['accent_purple']], [0.5, DARK_THEME['accent_blue']], [1, DARK_THEME['accent_green']]],
            showscale=True,
            colorbar=dict(title='Ventes ($)', tickfont=dict(color='#a0a0a0'))
        ),
        text=[f'${x:,.0f}' for x in top_countries['TotalSales']],
        textposition='outside',
        textfont=dict(color='#a0a0a0')
    ))
    
    fig.update_layout(
        title='🌍 Top 10 pays par chiffre d\'affaires',
        xaxis_title='Pays',
        yaxis_title='Ventes ($)',
        paper_bgcolor=DARK_THEME['bg_color'],
        plot_bgcolor='rgba(255, 255, 255, 0.02)',
        font=dict(color=DARK_THEME['text_color']),
        xaxis=dict(gridcolor=DARK_THEME['grid_color'], tickfont=dict(color='#a0a0a0'), tickangle=-45),
        yaxis=dict(gridcolor=DARK_THEME['grid_color'], tickfont=dict(color='#a0a0a0')),
        height=500
    )
    
    return fig

def create_world_map(data):
    """Créer la carte mondiale des ventes"""
    sales_by_country = data['Sales_By_Country']
    
    if sales_by_country.empty:
        return go.Figure()
    
    fig = go.Figure(go.Choropleth(
        locations=sales_by_country['Country'],
        locationmode='country names',
        z=sales_by_country['TotalSales'],
        colorscale=[[0, '#1a1a2e'], [0.5, DARK_THEME['accent_blue']], [1, DARK_THEME['accent_green']]],
        colorbar=dict(
            title=dict(text='Ventes ($)', font=dict(color='#a0a0a0')),
            tickfont=dict(color='#a0a0a0')
        ),
        marker_line_color='rgba(255,255,255,0.2)',
        marker_line_width=0.5
    ))
    
    fig.update_layout(
        title='🗺️ Carte mondiale des ventes',
        paper_bgcolor=DARK_THEME['bg_color'],
        plot_bgcolor=DARK_THEME['bg_color'],
        font=dict(color=DARK_THEME['text_color']),
        geo=dict(
            bgcolor=DARK_THEME['bg_color'],
            lakecolor=DARK_THEME['bg_color'],
            landcolor='rgba(255, 255, 255, 0.05)',
            showland=True,
            showcountries=True,
            countrycolor='rgba(255, 255, 255, 0.1)',
            showocean=True,
            oceancolor=DARK_THEME['bg_color']
        ),
        height=600
    )
    return fig

def create_top_products_chart(data):
    """Créer le graphique des top produits"""
    top_products = data['Top_Products']
    
    if top_products.empty:
        return go.Figure()
    
    # Déterminer la colonne de montant
    amount_col = 'SalesAmount' if 'SalesAmount' in top_products.columns else 'TotalAmount'
    
    sorted_data = top_products.sort_values(amount_col, ascending=True)
    
    fig = go.Figure(go.Bar(
        x=sorted_data[amount_col],
        y=sorted_data['ProductName'],
        orientation='h',
        marker=dict(
            color=sorted_data[amount_col],
            colorscale=[[0, DARK_THEME['accent_purple']], [0.5, DARK_THEME['accent_green']], [1, DARK_THEME['accent_blue']]],
            showscale=True,
            colorbar=dict(title='Ventes ($)', tickfont=dict(color='#a0a0a0'))
        ),
        text=[f'${x:,.0f}' for x in sorted_data[amount_col]],
        textposition='outside',
        textfont=dict(color='#a0a0a0')
    ))
    
    fig.update_layout(
        title='🏆 Top 20 produits par chiffre d\'affaires',
        xaxis_title='Ventes ($)',
        yaxis_title='Produit',
        paper_bgcolor=DARK_THEME['bg_color'],
        plot_bgcolor='rgba(255, 255, 255, 0.02)',
        font=dict(color=DARK_THEME['text_color']),
        xaxis=dict(gridcolor=DARK_THEME['grid_color'], tickfont=dict(color='#a0a0a0')),
        yaxis=dict(gridcolor=DARK_THEME['grid_color'], tickfont=dict(color='#a0a0a0', size=10)),
        height=700
    )
    return fig


def create_high_freight_chart(data):
    """Créer le graphique des commandes avec freight > 500 (KPI requis)"""
    high_freight = data.get('High_Freight_Orders', pd.DataFrame())
    
    if high_freight.empty:
        return go.Figure()
    
    fig = go.Figure(go.Bar(
        x=high_freight.head(15)['OrderID'].astype(str),
        y=high_freight.head(15)['Freight'],
        marker=dict(
            color=high_freight.head(15)['Freight'],
            colorscale=[[0, DARK_THEME['accent_orange']], [1, DARK_THEME['accent_red']]],
            showscale=True,
            colorbar=dict(title='Freight ($)', tickfont=dict(color='#a0a0a0'))
        ),
        text=[f'${x:,.0f}' for x in high_freight.head(15)['Freight']],
        textposition='outside',
        textfont=dict(color='#a0a0a0')
    ))
    
    # Ajouter une ligne de référence à 500
    fig.add_hline(y=500, line_dash="dash", line_color=DARK_THEME['accent_red'], 
                  annotation_text="Seuil: 500$", annotation_font_color=DARK_THEME['accent_red'])
    
    fig.update_layout(
        title='🚚 Commandes avec Freight > 500$ (KPI Requis)',
        xaxis_title='N° Commande',
        yaxis_title='Frais de port ($)',
        paper_bgcolor=DARK_THEME['bg_color'],
        plot_bgcolor='rgba(255, 255, 255, 0.02)',
        font=dict(color=DARK_THEME['text_color']),
        xaxis=dict(gridcolor=DARK_THEME['grid_color'], tickfont=dict(color='#a0a0a0')),
        yaxis=dict(gridcolor=DARK_THEME['grid_color'], tickfont=dict(color='#a0a0a0')),
        height=450
    )
    return fig


def create_late_deliveries_chart(data):
    """Créer le graphique des livraisons en retard (KPI requis)"""
    late_deliveries = data.get('Late_Deliveries', pd.DataFrame())
    
    if late_deliveries.empty:
        return go.Figure()
    
    # Par pays si disponible
    if 'ShipCountry' in late_deliveries.columns:
        by_country = late_deliveries.groupby('ShipCountry').size().reset_index(name='Count')
        by_country = by_country.sort_values('Count', ascending=True)
        
        fig = go.Figure(go.Bar(
            x=by_country['Count'],
            y=by_country['ShipCountry'],
            orientation='h',
            marker=dict(
                color=by_country['Count'],
                colorscale=[[0, DARK_THEME['accent_orange']], [1, DARK_THEME['accent_red']]],
                showscale=True,
                colorbar=dict(title='Commandes', tickfont=dict(color='#a0a0a0'))
            ),
            text=by_country['Count'],
            textposition='outside',
            textfont=dict(color='#a0a0a0')
        ))
        
        fig.update_layout(
            title='⏰ Livraisons en retard par pays (KPI Requis)',
            xaxis_title='Nombre de commandes',
            yaxis_title='Pays'
        )
    else:
        fig = go.Figure()
        fig.add_trace(go.Indicator(
            mode='number',
            value=len(late_deliveries),
            title={'text': 'Livraisons en retard', 'font': {'color': '#a0a0a0'}},
            number={'font': {'size': 60, 'color': DARK_THEME['accent_orange']}}
        ))
    
    fig.update_layout(
        paper_bgcolor=DARK_THEME['bg_color'],
        plot_bgcolor='rgba(255, 255, 255, 0.02)',
        font=dict(color=DARK_THEME['text_color']),
        xaxis=dict(gridcolor=DARK_THEME['grid_color'], tickfont=dict(color='#a0a0a0')),
        yaxis=dict(gridcolor=DARK_THEME['grid_color'], tickfont=dict(color='#a0a0a0')),
        height=450
    )
    return fig


def create_data_source_chart(data):
    """Créer le graphique de répartition par source de données"""
    fact_sales = data['Fact_Sales']
    
    if fact_sales.empty or 'DataSource' not in fact_sales.columns:
        return go.Figure()
    
    source_counts = fact_sales['DataSource'].value_counts().reset_index()
    source_counts.columns = ['Source', 'Count']
    
    colors = [DARK_THEME['accent_blue'] if s == 'SQLServer' else DARK_THEME['accent_purple'] 
              for s in source_counts['Source']]
    
    fig = go.Figure(go.Pie(
        values=source_counts['Count'],
        labels=source_counts['Source'],
        hole=0.5,
        marker=dict(colors=colors),
        textinfo='percent+label',
        textposition='outside',
        textfont=dict(color='#a0a0a0', size=14),
        pull=[0.05 if s == 'Access' else 0 for s in source_counts['Source']]
    ))
    
    fig.update_layout(
        title='📊 Répartition des données par source (SQL Server vs Access)',
        paper_bgcolor=DARK_THEME['bg_color'],
        plot_bgcolor=DARK_THEME['bg_color'],
        font=dict(color=DARK_THEME['text_color']),
        height=500,
        annotations=[dict(
            text=f"Total<br>{source_counts['Count'].sum():,}",
            x=0.5, y=0.5,
            font_size=16,
            font_color=DARK_THEME['accent_blue'],
            showarrow=False
        )]
    )
    return fig


def create_complete_dashboard(data, kpis):
    """Créer le tableau de bord complet avec tous les KPIs requis"""
    fig = make_subplots(
        rows=4, cols=2,
        specs=[
            [{'type': 'indicator'}, {'type': 'indicator'}],
            [{'type': 'indicator'}, {'type': 'indicator'}],
            [{'type': 'bar', 'colspan': 2}, None],
            [{'type': 'pie'}, {'type': 'bar'}]
        ],
        subplot_titles=(
            '', '', '', '',
            'Évolution des ventes mensuelles',
            'Répartition par catégorie', 'Ventes par catégorie'
        ),
        row_heights=[0.15, 0.15, 0.35, 0.35]
    )
    
    # KPIs incluant les nouveaux (freight>500, late deliveries)
    kpi_list = [
        ('💰 CA Total', kpis.get('total_revenue', 0), '$', ',.0f', DARK_THEME['accent_blue']),
        ('📋 Commandes', kpis.get('total_orders', 0), '', ',', DARK_THEME['accent_green']),
        ('🚚 Freight>500', kpis.get('high_freight_orders', 0), '', ',', DARK_THEME['accent_red']),
        ('⏰ Retards', kpis.get('late_deliveries', 0), '', ',', DARK_THEME['accent_orange'])
    ]
    
    positions = [(1,1), (1,2), (2,1), (2,2)]
    
    for (title, value, prefix, fmt, color), (row, col) in zip(kpi_list, positions):
        fig.add_trace(
            go.Indicator(
                mode='number',
                value=value,
                title={'text': title, 'font': {'color': '#a0a0a0'}},
                number={'prefix': prefix, 'valueformat': fmt, 'font': {'color': color}}
            ),
            row=row, col=col
        )
    
    # Evolution mensuelle
    fact_sales = data['Fact_Sales']
    amount_col = 'SalesAmount' if 'SalesAmount' in fact_sales.columns else 'TotalAmount'
    
    if not fact_sales.empty:
        monthly = fact_sales.groupby(
            fact_sales['OrderDate'].dt.to_period('M')
        )[amount_col].sum().reset_index()
        monthly['OrderDate'] = monthly['OrderDate'].astype(str)
        
        fig.add_trace(
            go.Bar(x=monthly['OrderDate'], y=monthly[amount_col], 
                   marker_color=DARK_THEME['accent_blue']),
            row=3, col=1
        )
    
    # Catégories
    sales_cat = data['Sales_By_Category']
    cat_col = 'Category' if 'Category' in sales_cat.columns else 'CategoryName'
    
    colors = [DARK_THEME['accent_blue'], DARK_THEME['accent_purple'], 
              DARK_THEME['accent_green'], DARK_THEME['accent_orange'],
              DARK_THEME['accent_red'], DARK_THEME['accent_pink'],
              '#00cec9', '#fdcb6e']
    
    if not sales_cat.empty:
        fig.add_trace(
            go.Pie(labels=sales_cat[cat_col], values=sales_cat['TotalSales'],
                   hole=0.4, marker=dict(colors=colors)),
            row=4, col=1
        )
        
        sorted_cat = sales_cat.sort_values('TotalSales', ascending=True)
        fig.add_trace(
            go.Bar(x=sorted_cat['TotalSales'], y=sorted_cat[cat_col],
                   orientation='h', marker_color=DARK_THEME['accent_purple']),
            row=4, col=2
        )
    
    fig.update_layout(
        title_text='📊 TABLEAU DE BORD BI - NORTHWIND (ETL Dual Source)',
        height=1200,
        showlegend=False,
        paper_bgcolor=DARK_THEME['bg_color'],
        plot_bgcolor='rgba(255, 255, 255, 0.02)',
        font=dict(color=DARK_THEME['text_color'])
    )
    fig.update_xaxes(gridcolor=DARK_THEME['grid_color'], tickfont=dict(color='#a0a0a0'))
    fig.update_yaxes(gridcolor=DARK_THEME['grid_color'], tickfont=dict(color='#a0a0a0'))
    
    return fig

# =============================================================================
# INDEX/NAVIGATION PAGE
# =============================================================================

def create_index_html(kpis):
    """Créer la page de navigation index.html avec le thème dark"""
    
    # Get dynamic values from KPIs
    total_revenue = kpis.get('total_revenue', 0)
    sql_records = kpis.get('sql_server_records', 0)
    access_records = kpis.get('access_records', 0)
    total_records = sql_records + access_records
    
    html_content = f'''<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Northwind BI Dashboard - Dual Source ETL</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            min-height: 100vh;
            color: #fff;
        }}
        .header {{
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            padding: 20px 40px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }}
        .header h1 {{
            font-size: 2rem;
            font-weight: 600;
            background: linear-gradient(90deg, #00d4ff, #7b2cbf);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        .header p {{
            color: #a0a0a0;
            margin-top: 5px;
            font-size: 0.95rem;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 40px 20px;
        }}
        .section-title {{
            font-size: 1.4rem;
            margin-bottom: 20px;
            padding-left: 15px;
            border-left: 4px solid #00d4ff;
            color: #fff;
        }}
        .cards-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        .card {{
            background: rgba(255, 255, 255, 0.05);
            border-radius: 16px;
            padding: 25px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            transition: all 0.3s ease;
            cursor: pointer;
            text-decoration: none;
            color: inherit;
            display: block;
        }}
        .card:hover {{
            transform: translateY(-5px);
            background: rgba(255, 255, 255, 0.1);
            border-color: rgba(0, 212, 255, 0.5);
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
        }}
        .card-icon {{
            width: 50px;
            height: 50px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.5rem;
            margin-bottom: 15px;
        }}
        .card-icon.blue {{ background: linear-gradient(135deg, #00d4ff, #0099cc); }}
        .card-icon.purple {{ background: linear-gradient(135deg, #7b2cbf, #5a189a); }}
        .card-icon.green {{ background: linear-gradient(135deg, #00b894, #00a085); }}
        .card-icon.orange {{ background: linear-gradient(135deg, #f39c12, #e67e22); }}
        .card-icon.red {{ background: linear-gradient(135deg, #e74c3c, #c0392b); }}
        .card-icon.pink {{ background: linear-gradient(135deg, #fd79a8, #e84393); }}
        .card h3 {{
            font-size: 1.1rem;
            margin-bottom: 8px;
            font-weight: 600;
        }}
        .card p {{
            color: #a0a0a0;
            font-size: 0.9rem;
            line-height: 1.5;
        }}
        .card-badge {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 0.75rem;
            margin-top: 12px;
            background: rgba(0, 212, 255, 0.2);
            color: #00d4ff;
        }}
        .card-badge.kpi {{
            background: rgba(231, 76, 60, 0.2);
            color: #e74c3c;
        }}
        .full-dashboard {{
            background: linear-gradient(135deg, rgba(0, 212, 255, 0.1), rgba(123, 44, 191, 0.1));
            border: 2px solid rgba(0, 212, 255, 0.3);
        }}
        .full-dashboard:hover {{
            border-color: #00d4ff;
        }}
        .sources-info {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-top: 20px;
            padding: 25px;
            background: rgba(255, 255, 255, 0.03);
            border-radius: 16px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}
        .source-box {{
            text-align: center;
            padding: 20px;
        }}
        .source-box h4 {{
            font-size: 1rem;
            margin-bottom: 10px;
            color: #00d4ff;
        }}
        .source-box .value {{
            font-size: 2rem;
            font-weight: 700;
        }}
        .source-box .label {{
            color: #a0a0a0;
            font-size: 0.85rem;
        }}
        .footer {{
            text-align: center;
            padding: 30px;
            color: #666;
            font-size: 0.85rem;
        }}
        .footer a {{
            color: #00d4ff;
            text-decoration: none;
        }}
        @media (max-width: 768px) {{
            .header h1 {{ font-size: 1.5rem; }}
            .cards-grid {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
    <header class="header">
        <h1>📊 Northwind BI Dashboard</h1>
        <p>ETL Dual Source: SQL Server + Microsoft Access → Data Warehouse Unifié</p>
    </header>

    <div class="container">
        <h2 class="section-title">🎯 Vue Complète</h2>
        <div class="cards-grid">
            <a href="dashboard_complet.html" class="card full-dashboard">
                <div class="card-icon blue">📈</div>
                <h3>Dashboard Complet</h3>
                <p>Vue d'ensemble avec tous les graphiques et KPIs sur une seule page.</p>
                <span class="card-badge">Recommandé</span>
            </a>
        </div>

        <h2 class="section-title">📋 Indicateurs Clés (KPIs)</h2>
        <div class="cards-grid">
            <a href="kpis.html" class="card">
                <div class="card-icon green">💰</div>
                <h3>KPIs Principaux</h3>
                <p>Chiffre d'affaires, commandes, panier moyen, clients actifs.</p>
                <span class="card-badge">8 KPIs</span>
            </a>
            <a href="high_freight.html" class="card">
                <div class="card-icon orange">🚚</div>
                <h3>Freight > 500$</h3>
                <p>Commandes avec frais de livraison élevés.</p>
                <span class="card-badge kpi">KPI Requis</span>
            </a>
            <a href="late_deliveries.html" class="card">
                <div class="card-icon red">⏰</div>
                <h3>Livraisons en Retard</h3>
                <p>Commandes livrées après la date requise.</p>
                <span class="card-badge kpi">KPI Requis</span>
            </a>
        </div>

        <h2 class="section-title">📊 Analyses Détaillées</h2>
        <div class="cards-grid">
            <a href="sales_trend.html" class="card">
                <div class="card-icon blue">📈</div>
                <h3>Tendance des Ventes</h3>
                <p>Évolution du chiffre d'affaires par mois.</p>
            </a>
            <a href="categories.html" class="card">
                <div class="card-icon purple">🏷️</div>
                <h3>Ventes par Catégorie</h3>
                <p>Répartition des ventes par catégorie de produits.</p>
            </a>
            <a href="countries.html" class="card">
                <div class="card-icon green">🌍</div>
                <h3>Ventes par Pays</h3>
                <p>Top pays par chiffre d'affaires.</p>
            </a>
            <a href="world_map.html" class="card">
                <div class="card-icon blue">🗺️</div>
                <h3>Carte Mondiale</h3>
                <p>Visualisation cartographique des ventes.</p>
            </a>
            <a href="top_products.html" class="card">
                <div class="card-icon pink">⭐</div>
                <h3>Top Produits</h3>
                <p>Classement des 20 meilleurs produits.</p>
            </a>
        </div>

        <h2 class="section-title">🔄 Sources de Données</h2>
        <div class="cards-grid">
            <a href="data_sources.html" class="card">
                <div class="card-icon purple">🔗</div>
                <h3>Répartition des Sources</h3>
                <p>SQL Server vs Microsoft Access - contribution de chaque source.</p>
                <span class="card-badge">Dual Source ETL</span>
            </a>
        </div>

        <div class="sources-info">
            <div class="source-box">
                <h4>🗄️ SQL Server</h4>
                <div class="value">{sql_records:,}</div>
                <div class="label">Enregistrements</div>
            </div>
            <div class="source-box">
                <h4>📁 Microsoft Access</h4>
                <div class="value">{access_records:,}</div>
                <div class="label">Enregistrements</div>
            </div>
            <div class="source-box">
                <h4>📊 Total Fusionné</h4>
                <div class="value">{total_records:,}</div>
                <div class="label">Enregistrements</div>
            </div>
            <div class="source-box">
                <h4>💰 Chiffre d'Affaires</h4>
                <div class="value">${total_revenue/1000000:.2f}M</div>
                <div class="label">Revenue Total</div>
            </div>
        </div>
    </div>

</body>
</html>'''
    
    with open(FIGURES_PATH / 'index.html', 'w', encoding='utf-8') as f:
        f.write(html_content)

# =============================================================================
# EXPORT DES GRAPHIQUES
# =============================================================================

def save_figures(data, kpis):
    """Sauvegarder tous les graphiques en fichiers HTML avec thème dark"""
    
    print("\n📊 Génération des graphiques (thème dark)...")
    
    # KPIs (avec freight>500 et late deliveries)
    fig_kpis = create_kpi_cards(kpis)
    with open(FIGURES_PATH / 'kpis.html', 'w', encoding='utf-8') as f:
        f.write(wrap_html_dark(fig_kpis, '📊 Indicateurs Clés de Performance'))
    print("✅ kpis.html sauvegardé")
    
    # Evolution des ventes
    fig_trend = create_sales_trend(data)
    with open(FIGURES_PATH / 'sales_trend.html', 'w', encoding='utf-8') as f:
        f.write(wrap_html_dark(fig_trend, '📈 Évolution des Ventes'))
    print("✅ sales_trend.html sauvegardé")
    
    # Catégories
    fig_cat = create_category_chart(data)
    with open(FIGURES_PATH / 'categories.html', 'w', encoding='utf-8') as f:
        f.write(wrap_html_dark(fig_cat, '📦 Ventes par Catégorie'))
    print("✅ categories.html sauvegardé")
    
    # Pays
    fig_country = create_country_chart(data)
    with open(FIGURES_PATH / 'countries.html', 'w', encoding='utf-8') as f:
        f.write(wrap_html_dark(fig_country, '🌍 Top Pays'))
    print("✅ countries.html sauvegardé")
    
    # Carte mondiale
    fig_map = create_world_map(data)
    with open(FIGURES_PATH / 'world_map.html', 'w', encoding='utf-8') as f:
        f.write(wrap_html_dark(fig_map, '🗺️ Carte Mondiale'))
    print("✅ world_map.html sauvegardé")
    
    # Top produits
    fig_products = create_top_products_chart(data)
    with open(FIGURES_PATH / 'top_products.html', 'w', encoding='utf-8') as f:
        f.write(wrap_html_dark(fig_products, '🏆 Top Produits'))
    print("✅ top_products.html sauvegardé")
    
    # High Freight Orders (KPI requis)
    fig_freight = create_high_freight_chart(data)
    with open(FIGURES_PATH / 'high_freight.html', 'w', encoding='utf-8') as f:
        f.write(wrap_html_dark(fig_freight, '🚚 Freight > 500$'))
    print("✅ high_freight.html sauvegardé (KPI: Freight > 500)")
    
    # Late Deliveries (KPI requis)
    fig_late = create_late_deliveries_chart(data)
    with open(FIGURES_PATH / 'late_deliveries.html', 'w', encoding='utf-8') as f:
        f.write(wrap_html_dark(fig_late, '⏰ Livraisons en Retard'))
    print("✅ late_deliveries.html sauvegardé (KPI: Livraisons en retard)")
    
    # Data Source Distribution
    fig_source = create_data_source_chart(data)
    with open(FIGURES_PATH / 'data_sources.html', 'w', encoding='utf-8') as f:
        f.write(wrap_html_dark(fig_source, '🔄 Sources de Données'))
    print("✅ data_sources.html sauvegardé (SQL Server vs Access)")
    
    # Dashboard complet
    fig_dashboard = create_complete_dashboard(data, kpis)
    with open(FIGURES_PATH / 'dashboard_complet.html', 'w', encoding='utf-8') as f:
        f.write(wrap_html_dark(fig_dashboard, '📊 Dashboard Complet'))
    print("✅ dashboard_complet.html sauvegardé")
    
    # Index/Navigation page
    create_index_html(kpis)
    print("✅ index.html sauvegardé (Page de navigation)")
    
    print(f"\n📁 Tous les graphiques ont été sauvegardés dans {FIGURES_PATH}")

# =============================================================================
# POINT D'ENTRÉE
# =============================================================================

if __name__ == "__main__":
    print("""
    ╔═══════════════════════════════════════════════════════════════╗
    ║         DASHBOARD BI - NORTHWIND Analytics                    ║
    ║              ETL Dual Source (SQL Server + Access)            ║
    ╚═══════════════════════════════════════════════════════════════╝
    """)
    
    # Charger les données
    print("📂 Chargement des données depuis l'ETL dual source...")
    data = load_data()
    
    # Calculer les KPIs
    print("\n📈 Calcul des KPIs (incluant Freight>500 et Livraisons en retard)...")
    kpis = calculate_kpis(data)
    
    if kpis:
        print(f"\n💰 CA Total: ${kpis['total_revenue']:,.2f}")
        print(f"📋 Commandes: {kpis['total_orders']:,}")
        print(f"💵 Panier moyen: ${kpis['avg_order_value']:,.2f}")
        print(f"👥 Clients: {kpis['total_customers']:,}")
        print(f"🚚 Commandes Freight > 500$: {kpis.get('high_freight_orders', 0):,}")
        print(f"⏰ Livraisons en retard: {kpis.get('late_deliveries', 0):,}")
    
    # Générer et sauvegarder les graphiques
    save_figures(data, kpis)
    
    print("\n✅ Dashboard généré avec succès!")
    print(f"📁 Ouvrez les fichiers HTML dans le dossier '{FIGURES_PATH}' pour visualiser")
    print("\nFichiers générés:")
    print("  - kpis.html (tous les KPIs)")
    print("  - high_freight.html (Freight > 500$)")
    print("  - late_deliveries.html (Livraisons en retard)")
    print("  - dashboard_complet.html (Vue complète)")
