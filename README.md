# 📊 Projet BI - Northwind Analytics (Dual Source ETL)

## Description du projet

Ce projet consiste en la conception et la réalisation d'une solution Business Intelligence complète basée sur la base de données Northwind avec **extraction de deux sources hétérogènes** :

1. **SQL Server** - Base de données Northwind (source primaire)
2. **Microsoft Access** - Base de données Northwind (source secondaire)

Le projet comprend :
- Un pipeline ETL (Extract, Transform, Load) en Python pour **sources multiples**
- La **fusion et réconciliation** des données entre les deux sources
- La création d'un **Data Warehouse** en schéma étoile
- Des analyses de données et visualisations
- Un tableau de bord analytique avec les indicateurs clés (KPIs)

## 🏗️ Architecture ETL

```
┌─────────────────────┐     ┌─────────────────────┐
│     SQL SERVER      │     │  MICROSOFT ACCESS   │
│     Northwind       │     │     Northwind       │
│   (Source primaire) │     │ (Source secondaire) │
└──────────┬──────────┘     └──────────┬──────────┘
           │                           │
           │        EXTRACTION         │
           ▼                           ▼
┌──────────────────────────────────────────────────┐
│              TRANSFORMATION & FUSION             │
│  • Gestion des incohérences entre sources        │
│  • Résolution des conflits (SQL Server priorité) │
│  • Nettoyage et standardisation                  │
│  • Création du schéma étoile                     │
└──────────────────────┬───────────────────────────┘
                       │
                       │        CHARGEMENT
                       ▼
┌──────────────────────────────────────────────────┐
│            DATA WAREHOUSE (DWH)                  │
│                                                  │
│  ┌──────────┐                  ┌──────────────┐  │
│  │ Dim_Time │                  │ Dim_Employee │  │
│  └────┬─────┘                  └──────┬───────┘  │
│       │                               │          │
│       └──────────────┬────────────────┘          │
│                      ▼                           │
│               ┌────────────┐                     │
│               │ Fact_Sales │                     │
│               └──────┬─────┘                     │
│                      │                           │
│               ┌──────┴───────┐                   │
│               ▼              ▼                   │
│        ┌────────────┐ ┌──────────────┐           │
│        │Dim_Product │ │ Dim_Customers│           │
│        └────────────┘ └──────────────┘           │
└──────────────────────────────────────────────────┘
```

## 🗂️ Structure du projet

```
BI Project/
├── 📁 data/                    # Données extraites et transformées
│   ├── *.csv                  # Fichiers source originaux
│   ├── Dim_*.csv              # Tables de dimensions (DWH)
│   ├── Fact_Sales.csv         # Table de faits (DWH)
│   ├── Sales_By_*.csv         # Vues analytiques pré-agrégées
│   └── DWH_Northwind.db       # Data Warehouse SQLite
├── 📁 scripts/                 # Scripts Python
│   ├── etl_northwind.py       # ETL principal (dual source)
│   ├── dashboard.py           # Génération du tableau de bord
│   └── config.py              # Configuration des connexions
├── 📁 notebooks/               # Notebooks Jupyter
│   └── analyse_northwind.ipynb
├── 📁 reports/                 # Rapports et logs
│   ├── etl_log.txt            # Log d'exécution ETL
│   └── rapport_projet_bi.md   # Rapport de projet
├── 📁 figures/                 # Graphiques exportés (HTML)
├── 📁 video/                   # Vidéo de présentation
└── README.md                   # Ce fichier
```

## 🛠️ Prérequis

### Logiciels requis
- Python 3.8 ou supérieur
- SQL Server avec la base Northwind installée
- Microsoft Access avec la base Northwind (.accdb ou .mdb)
- ODBC Driver 17 for SQL Server
- Microsoft Access Driver (*.mdb, *.accdb)

### Bibliothèques Python requises

```bash
pip install -r requirements.txt
```

Ou installez manuellement :
```bash
pip install pandas numpy pyodbc matplotlib seaborn plotly openpyxl jupyter
```

## ⚙️ Configuration

### 1. Configuration de SQL Server (Source 1)

Modifiez le fichier `scripts/config.py` avec vos paramètres :

```python
SQL_SERVER_CONFIG = {
    'server': 'localhost\\SQLEXPRESS',  # Votre serveur
    'database': 'Northwind',
    'driver': '{ODBC Driver 17 for SQL Server}',
    'trusted_connection': 'yes'
}
```

### 2. Configuration de Microsoft Access (Source 2)

```python
# Chemin vers la vraie base Northwind 2012
ACCESS_CONFIG = r"C:\Users\noufe\Downloads\Northwind 2012.accdb"
```

> **Note:** La base Northwind 2012 a un schéma différent de SQL Server.
> Le mapping est géré automatiquement (ID → CustomerID, Company → CompanyName, etc.)

### 3. Configuration du Data Warehouse

```python
DWH_CONFIG = {
    'type': 'sqlite',
    'database_path': DATA_PATH / 'DWH_Northwind.db'
}
```

> **Note**: Si les bases de données ne sont pas disponibles, le script utilise un mode de repli avec les fichiers CSV en simulant des variations entre les sources.

## 🚀 Exécution

### Étape 1 : Exécuter l'ETL (Extraction Dual Source)

```bash
cd scripts
python etl_northwind.py
```

Ce script va :
1. **EXTRAIRE** les données de SQL Server ET Microsoft Access
2. **TRANSFORMER** et fusionner les données :
   - Gérer les incohérences (employés manquants, prix différents)
   - Résoudre les conflits (SQL Server prioritaire)
   - Créer le schéma étoile (Dim + Fact)
3. **CHARGER** dans le Data Warehouse SQLite et fichiers CSV

### Étape 2 : Générer le tableau de bord

```bash
python dashboard.py
```

### Étape 3 : Explorer l'analyse (optionnel)

```bash
jupyter notebook ../notebooks/analyse_northwind.ipynb
```

## 📊 Indicateurs clés (KPIs)

Le tableau de bord présente les indicateurs suivants (valeurs actuelles) :

| Indicateur | Description | Valeur |
|------------|-------------|--------|
| **Chiffre d'affaires** | Total des ventes (SalesAmount) | **$1,333,929.86** |
| Nombre de commandes | Commandes uniques | 870 |
| Panier moyen | CA / Nombre de commandes | $1,533.25 |
| Clients actifs | Nombre de clients ayant commandé | 104 |
| Top produits | Les 20 produits les plus vendus | Voir dashboard |
| Répartition géographique | Ventes par pays | 21 pays |
| **Frais de port > 500** | Commandes avec freight > 500 | **13 commandes** |
| **Livraisons en retard** | Commandes livrées après RequiredDate | **37 commandes** |

## 🔄 Fusion des données (Statistiques réelles)

| Table | SQL Server | Access 2012 | Total Fusionné |
|-------|-----------|-------------|----------------|
| Customers | 91 | 29 uniques | **120** |
| Products | 77 | 19 uniques | **96** |
| Employees | 9 | 9 | **9** |
| Orders | 830 | 48 uniques | **878** |
| Order Details | 2155 | 58 | **2213** |

Le script ETL gère automatiquement les différences entre SQL Server et Access :

| Incohérence | Stratégie de résolution |
|-------------|------------------------|
| Employés manquants | Union des deux sources, SQL Server prioritaire |
| Prix différents | SQL Server (plus récent) prend la priorité |
| Clients manquants | Union avec déduplication par CustomerID |
| Commandes manquantes | Union avec déduplication par OrderID |
| Produits discontinués | État SQL Server (plus à jour) conservé |

## 📁 Fichiers de sortie

### Dans `/data` - Data Warehouse
- `DWH_Northwind.db` - **Base SQLite du Data Warehouse**
- `Fact_Sales.csv` - Table de faits des ventes
- `Dim_Customers.csv` - Dimension clients
- `Dim_Products.csv` - Dimension produits
- `Dim_Employees.csv` - Dimension employés
- `Dim_Time.csv` - Dimension temporelle

### Dans `/data` - Vues analytiques
- `Sales_By_Month.csv` - Agrégation mensuelle
- `Sales_By_Category.csv` - Ventes par catégorie
- `Sales_By_Country.csv` - Ventes par pays
- `Top_Products.csv` - Top 20 produits
- `High_Freight_Orders.csv` - Commandes freight > 500
- `Late_Deliveries.csv` - Livraisons en retard

### Dans `/figures` - Dashboard interactif (thème dark)
- `index.html` - **Page de navigation principale**
- `dashboard_complet.html` - Tableau de bord complet
- `kpis.html` - Cartes KPI
- `sales_trend.html` - Évolution des ventes
- `categories.html` - Analyse par catégorie
- `countries.html` - Top pays
- `world_map.html` - Carte mondiale
- `top_products.html` - Top 20 produits
- `high_freight.html` - Commandes freight > 500$
- `late_deliveries.html` - Livraisons en retard
- `data_sources.html` - Répartition SQL Server vs Access

## 🔧 Architecture technique

### Choix des bibliothèques

| Bibliothèque | Utilisation | Justification |
|--------------|-------------|---------------|
| `pandas` | Manipulation de données | Standard pour l'analyse de données |
| `pyodbc` | Connexion SQL Server & Access | Driver officiel Microsoft |
| `sqlite3` | Data Warehouse local | Léger, portable, SQL standard |
| `plotly` | Visualisations interactives | Graphiques web modernes |
| `matplotlib/seaborn` | Visualisations statiques | Export en images |

### Modèle de données (Schéma Étoile)

```
                    ┌──────────────┐
                    │   Dim_Time   │
                    │ • TimeKey    │
                    │ • Date       │
                    │ • Year       │
                    │ • Month      │
                    │ • Quarter    │
                    └──────┬───────┘
                           │
┌──────────────┐    ┌──────┴───────┐    ┌───────────────┐
│ Dim_Customer │    │  Fact_Sales  │    │  Dim_Employee │
│ • CustomerKey│◄───┤ • SalesKey   ├───►│ • EmployeeKey │
│ • CustomerID │    │ • OrderID    │    │ • EmployeeID  │
│ • CompanyName│    │ • ProductID  │    │ • FullName    │
│ • Country    │    │ • CustomerID │    │ • Title       │
│ • DataSource │    │ • EmployeeID │    │ • DataSource  │
└──────────────┘    │ • SalesAmount│    └───────────────┘
                    │ • Quantity   │
                    │ • Discount   │
                    │ • Freight    │
                    │ • IsHighFreight│
                    │ • IsLateDelivery│
                    └──────┬───────┘
                           │
                    ┌──────┴───────┐
                    │ Dim_Product  │
                    │ • ProductKey │
                    │ • ProductID  │
                    │ • ProductName│
                    │ • CategoryName│
                    │ • UnitPrice  │
                    │ • DataSource │
                    └──────────────┘
```

## 📝 Notes importantes

- Les données sont extraites de **deux sources hétérogènes** (SQL Server + Access)
- En cas d'absence des bases de données, le script utilise les CSV avec simulation des variations
- Le champ `DataSource` dans les dimensions indique l'origine de chaque enregistrement
- Les montants sont calculés : `Prix × Quantité × (1 - Remise)`
- Le Data Warehouse SQLite permet des requêtes SQL directes

## 👤 Auteur

BOUMEDIENE noufel  
Projet BI - Décembre 2025

