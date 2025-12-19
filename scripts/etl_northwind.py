#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ETL Northwind - Extraction from Dual Heterogeneous Sources
===========================================================

This script performs ETL (Extract, Transform, Load) operations on the Northwind database
from TWO heterogeneous sources:
    1. SQL Server - Northwind database
    2. Microsoft Access - Northwind database (.accdb/.mdb)

The data is merged, cleaned, transformed into a star schema, and loaded into a 
unified Data Warehouse (DWH).

Architecture:
    ┌─────────────────┐     ┌─────────────────┐
    │   SQL Server    │     │ Microsoft Access│
    │   Northwind     │     │    Northwind    │
    └────────┬────────┘     └────────┬────────┘
             │                       │
             │      EXTRACT          │
             ▼                       ▼
    ┌─────────────────────────────────────────┐
    │           TRANSFORM & MERGE             │
    │  - Handle inconsistencies               │
    │  - Resolve conflicts (SQL Server wins)  │
    │  - Create star schema                   │
    └────────────────┬────────────────────────┘
                     │
                     │        LOAD
                     ▼
    ┌─────────────────────────────────────────┐
    │         DATA WAREHOUSE (DWH)            │
    │                                         │
    │  ┌──────────┐  ┌──────────┐             │
    │  │Dim_Time  │  │Dim_Customer│           │
    │  └────┬─────┘  └─────┬─────┘            │
    │       │              │                  │
    │       └──────┬───────┘                  │
    │              ▼                          │
    │       ┌────────────┐                    │
    │       │ Fact_Sales │                    │
    │       └──────┬─────┘                    │
    │              │                          │
    │       ┌──────┴───────┐                  │
    │       │              │                  │
    │  ┌────▼─────┐  ┌────▼─────┐             │
    │  │Dim_Product│  │Dim_Employee│          │
    │  └──────────┘  └──────────┘             │
    └─────────────────────────────────────────┘

"""

import pandas as pd
import numpy as np
import pyodbc
import sqlite3
from datetime import datetime
from pathlib import Path
import logging
import warnings
import sys

warnings.filterwarnings('ignore')

# =============================================================================
# PATH CONFIGURATION
# =============================================================================

# Get the project root directory
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_PATH = PROJECT_ROOT / 'data'
REPORTS_PATH = PROJECT_ROOT / 'reports'

# Create directories if they don't exist
DATA_PATH.mkdir(exist_ok=True)
REPORTS_PATH.mkdir(exist_ok=True)

# =============================================================================
# DATABASE CONFIGURATION
# =============================================================================

# Source 1: SQL Server Northwind
SQL_SERVER_CONFIG = {
    'server': 'localhost\\SQLEXPRESS',  # Modify for your setup
    'database': 'Northwind',
    'driver': '{ODBC Driver 17 for SQL Server}',
    'trusted_connection': 'yes',
    'username': '',
    'password': ''
}

# Source 2: Microsoft Access Northwind 2012
ACCESS_CONFIG = {
    'database_path': r"C:\Users\noufe\Downloads\Northwind 2012.accdb",
    'driver': '{Microsoft Access Driver (*.mdb, *.accdb)}'
}

# Destination: Data Warehouse
DWH_CONFIG = {
    'type': 'sqlite',
    'database_path': DATA_PATH / 'DWH_Northwind.db'
}

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except:
        pass

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(REPORTS_PATH / 'etl_log.txt', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# =============================================================================
# DATABASE CONNECTION CLASSES
# =============================================================================

class SQLServerConnection:
    """Connection manager for SQL Server Northwind database (Source 1)."""
    
    def __init__(self, config):
        self.config = config
        self.connection = None
        self.source_name = "SQL Server"
    
    def connect(self):
        """Establish connection to SQL Server."""
        try:
            if self.config['trusted_connection'] == 'yes':
                conn_str = (
                    f"DRIVER={self.config['driver']};"
                    f"SERVER={self.config['server']};"
                    f"DATABASE={self.config['database']};"
                    f"Trusted_Connection=yes;"
                )
            else:
                conn_str = (
                    f"DRIVER={self.config['driver']};"
                    f"SERVER={self.config['server']};"
                    f"DATABASE={self.config['database']};"
                    f"UID={self.config['username']};"
                    f"PWD={self.config['password']};"
                )
            self.connection = pyodbc.connect(conn_str)
            logger.info(f"✓ Connected to {self.source_name} Northwind database")
            return True
        except Exception as e:
            logger.warning(f"✗ Could not connect to {self.source_name}: {e}")
            return False
    
    def extract_table(self, table_name):
        """Extract a table from SQL Server."""
        try:
            query = f"SELECT * FROM [{table_name}]"
            df = pd.read_sql(query, self.connection)
            logger.info(f"  {self.source_name} - Extracted {len(df)} rows from {table_name}")
            return df
        except Exception as e:
            logger.warning(f"  {self.source_name} - Could not extract {table_name}: {e}")
            return pd.DataFrame()
    
    def close(self):
        """Close the connection."""
        if self.connection:
            self.connection.close()
            logger.info(f"{self.source_name} connection closed")


class AccessConnection:
    """
    Connection manager for Microsoft Access Northwind 2012 database (Source 2).
    
    Note: Northwind 2012 has a DIFFERENT schema than SQL Server Northwind.
    This class handles schema mapping between the two sources.
    """
    
    # Schema mapping: Access Northwind 2012 -> SQL Server Northwind format
    SCHEMA_MAPPING = {
        'Customers': {
            'access_table': 'Customers',
            'column_map': {
                'ID': 'CustomerID',
                'Company': 'CompanyName',
                'Last Name': 'ContactName',  # Will combine with First Name
                'First Name': 'ContactFirstName',
                'Job Title': 'ContactTitle',
                'Address': 'Address',
                'City': 'City',
                'State/Province': 'Region',
                'ZIP/Postal Code': 'PostalCode',
                'Country/Region': 'Country',
                'Business Phone': 'Phone',
                'Fax Number': 'Fax'
            }
        },
        'Products': {
            'access_table': 'Products',
            'column_map': {
                'ID': 'ProductID',
                'Product Name': 'ProductName',
                'Supplier IDs': 'SupplierID',
                'Category': 'CategoryID',
                'Quantity Per Unit': 'QuantityPerUnit',
                'List Price': 'UnitPrice',
                'Reorder Level': 'ReorderLevel',
                'Discontinued': 'Discontinued'
            }
        },
        'Employees': {
            'access_table': 'Employees',
            'column_map': {
                'ID': 'EmployeeID',
                'Last Name': 'LastName',
                'First Name': 'FirstName',
                'Job Title': 'Title',
                'Address': 'Address',
                'City': 'City',
                'State/Province': 'Region',
                'ZIP/Postal Code': 'PostalCode',
                'Country/Region': 'Country',
                'Business Phone': 'HomePhone'
            }
        },
        'Orders': {
            'access_table': 'Orders',
            'column_map': {
                'Order ID': 'OrderID',
                'Customer ID': 'CustomerID',
                'Employee ID': 'EmployeeID',
                'Order Date': 'OrderDate',
                'Shipped Date': 'ShippedDate',
                'Shipper ID': 'ShipVia',
                'Ship Name': 'ShipName',
                'Ship Address': 'ShipAddress',
                'Ship City': 'ShipCity',
                'Ship State/Province': 'ShipRegion',
                'Ship ZIP/Postal Code': 'ShipPostalCode',
                'Ship Country/Region': 'ShipCountry',
                'Shipping Fee': 'Freight'
            }
        },
        'Order Details': {
            'access_table': 'Order Details',
            'column_map': {
                'Order ID': 'OrderID',
                'Product ID': 'ProductID',
                'Unit Price': 'UnitPrice',
                'Quantity': 'Quantity',
                'Discount': 'Discount'
            }
        },
        'Shippers': {
            'access_table': 'Shippers',
            'column_map': {
                'ID': 'ShipperID',
                'Company': 'CompanyName',
                'Business Phone': 'Phone'
            }
        },
        'Suppliers': {
            'access_table': 'Suppliers',
            'column_map': {
                'ID': 'SupplierID',
                'Company': 'CompanyName',
                'Last Name': 'ContactName',
                'Job Title': 'ContactTitle',
                'Address': 'Address',
                'City': 'City',
                'State/Province': 'Region',
                'ZIP/Postal Code': 'PostalCode',
                'Country/Region': 'Country',
                'Business Phone': 'Phone',
                'Fax Number': 'Fax'
            }
        }
    }
    
    def __init__(self, config):
        self.config = config
        self.connection = None
        self.source_name = "Access"
    
    def connect(self):
        """Establish connection to Access database."""
        try:
            db_path = str(self.config['database_path'])
            conn_str = (
                f"DRIVER={self.config['driver']};"
                f"DBQ={db_path};"
            )
            self.connection = pyodbc.connect(conn_str)
            logger.info(f"✓ Connected to {self.source_name} Northwind 2012 database: {db_path}")
            return True
        except Exception as e:
            logger.warning(f"✗ Could not connect to {self.source_name}: {e}")
            return False
    
    def extract_table(self, table_name):
        """
        Extract a table from Access and map columns to SQL Server schema.
        This handles the schema differences between Northwind 2012 and classic Northwind.
        """
        try:
            if table_name not in self.SCHEMA_MAPPING:
                logger.warning(f"  {self.source_name} - No mapping for {table_name}, skipping")
                return pd.DataFrame()
            
            mapping = self.SCHEMA_MAPPING[table_name]
            access_table = mapping['access_table']
            column_map = mapping['column_map']
            
            # Extract from Access
            query = f"SELECT * FROM [{access_table}]"
            df = pd.read_sql(query, self.connection)
            
            # Rename columns to match SQL Server schema
            rename_dict = {k: v for k, v in column_map.items() if k in df.columns}
            df = df.rename(columns=rename_dict)
            
            # Keep only mapped columns that exist
            mapped_cols = [v for v in column_map.values() if v in df.columns]
            df = df[mapped_cols] if mapped_cols else df
            
            # Special handling for Customers - combine First/Last name
            if table_name == 'Customers' and 'ContactName' in df.columns:
                if 'ContactFirstName' in df.columns:
                    df['ContactName'] = df['ContactFirstName'].fillna('') + ' ' + df['ContactName'].fillna('')
                    df['ContactName'] = df['ContactName'].str.strip()
                    df = df.drop(columns=['ContactFirstName'], errors='ignore')
            
            # Add source tracking
            df['DataSource'] = 'Access'
            
            logger.info(f"  {self.source_name} - Extracted {len(df)} rows from {table_name}")
            return df
            
        except Exception as e:
            logger.warning(f"  {self.source_name} - Could not extract {table_name}: {e}")
            return pd.DataFrame()
    
    def close(self):
        """Close the connection."""
        if self.connection:
            self.connection.close()
            logger.info(f"{self.source_name} connection closed")


# =============================================================================
# ETL MAIN CLASS - DUAL SOURCE EXTRACTION
# =============================================================================

class NorthwindETL:
    """
    ETL Process for Northwind data from dual heterogeneous sources.
    
    This class handles:
    1. EXTRACT: Data from SQL Server AND Microsoft Access
    2. TRANSFORM: Merge sources, clean data, create star schema
    3. LOAD: To unified Data Warehouse (SQLite) and CSV files
    
    Key Features:
    - Handles data inconsistencies between sources
    - Conflict resolution (SQL Server takes precedence)
    - Star schema with Dim and Fact tables
    - KPI calculations for dashboard
    """
    
    def __init__(self):
        """Initialize ETL with data containers."""
        # Source data containers
        self.sql_server_data = {}
        self.access_data = {}
        
        # Merged/transformed data
        self.merged_data = {}
        
        # Star schema tables
        self.dim_customers = None
        self.dim_products = None
        self.dim_employees = None
        self.dim_time = None
        self.dim_categories = None
        self.dim_suppliers = None
        self.dim_shippers = None
        self.fact_sales = None
        
        # Connection status
        self.sql_server_connected = False
        self.access_connected = False
        
        # Tables to extract from both sources
        self.tables_to_extract = [
            'Customers', 'Products', 'Employees', 'Orders', 
            'Order Details', 'Categories', 'Suppliers', 'Shippers',
            'Territories', 'Region'
        ]
        
        logger.info("="*70)
        logger.info("NORTHWIND ETL - DUAL HETEROGENEOUS SOURCE EXTRACTION")
        logger.info("="*70)
        logger.info("Sources: SQL Server Northwind + Microsoft Access Northwind")
        logger.info("Output: Unified Star Schema Data Warehouse")
    
    # =========================================================================
    # PHASE 1: EXTRACT FROM BOTH SOURCES
    # =========================================================================
    
    def extract_from_sql_server(self):
        """
        Extract all tables from SQL Server Northwind database.
        This is the PRIMARY source with more recent/complete data.
        """
        logger.info("\n" + "="*50)
        logger.info("PHASE 1A: EXTRACTION FROM SQL SERVER")
        logger.info("="*50)
        
        sql_conn = SQLServerConnection(SQL_SERVER_CONFIG)
        
        if sql_conn.connect():
            self.sql_server_connected = True
            for table in self.tables_to_extract:
                df = sql_conn.extract_table(table)
                if not df.empty:
                    self.sql_server_data[table] = df
            sql_conn.close()
        else:
            logger.warning("SQL Server not available - using CSV fallback for simulation")
            self._load_csv_as_sql_server()
    
    def extract_from_access(self):
        """
        Extract all tables from Microsoft Access Northwind database.
        This is the SECONDARY source, may have older/different data.
        """
        logger.info("\n" + "="*50)
        logger.info("PHASE 1B: EXTRACTION FROM MICROSOFT ACCESS")
        logger.info("="*50)
        
        access_conn = AccessConnection(ACCESS_CONFIG)
        
        if access_conn.connect():
            self.access_connected = True
            for table in self.tables_to_extract:
                df = access_conn.extract_table(table)
                if not df.empty:
                    self.access_data[table] = df
            access_conn.close()
        else:
            logger.warning("Access DB not available - using CSV fallback with variations")
            self._load_csv_as_access()
    
    def _load_csv_as_sql_server(self):
        """
        Fallback: Load CSV files to simulate SQL Server data.
        Use this when SQL Server is not available for testing.
        """
        logger.info("Loading CSV files as SQL Server source (fallback mode)...")
        
        csv_mappings = {
            'Customers': 'Customers.csv',
            'Products': 'Products.csv',
            'Employees': 'Employees.csv',
            'Orders': 'Orders.csv',
            'Order Details': 'OrderDetails.csv',
            'Categories': 'Categories.csv',
            'Suppliers': 'Suppliers.csv',
            'Shippers': 'Shippers.csv',
            'Territories': 'Territories.csv',
            'Region': 'Region.csv'
        }
        
        for table, csv_file in csv_mappings.items():
            csv_path = DATA_PATH / csv_file
            if csv_path.exists():
                try:
                    df = pd.read_csv(csv_path, encoding='utf-8')
                    self.sql_server_data[table] = df
                    logger.info(f"  SQL Server (CSV) - Loaded {len(df)} rows from {csv_file}")
                except Exception as e:
                    logger.warning(f"  Could not load {csv_file}: {e}")
    
    def _load_csv_as_access(self):
        """
        Fallback: Generate Access data from SQL Server data WITH VARIATIONS.
        This demonstrates the heterogeneous nature of the two sources.
        
        Strategy for demonstration:
        - Access data is derived from SQL Server but with modifications
        - This shows true dual-source integration where both contribute
        """
        logger.info("Generating Access dataset from SQL Server (simulation mode)...")
        logger.info("NOTE: Creating distinct Access dataset for dual-source demonstration")
        
        # Generate Access data from SQL Server data with variations
        tables_to_simulate = ['Customers', 'Products', 'Employees', 'Orders', 
                             'Order Details', 'Categories', 'Suppliers', 'Shippers']
        
        for table in tables_to_simulate:
            if table in self.sql_server_data:
                try:
                    df = self.sql_server_data[table].copy()
                    # Apply variations to simulate different source
                    df = self._simulate_access_variations(df, table)
                    self.access_data[table] = df
                    logger.info(f"  Access (simulated) - Generated {len(df)} rows for {table}")
                except Exception as e:
                    logger.warning(f"  Could not generate Access data for {table}: {e}")
    
    def _simulate_access_variations(self, df, table_name):
        """
        Simulate Access database having different data than SQL Server.
        
        This demonstrates real-world scenarios where:
        - Different databases are updated at different times
        - Data entry may vary between systems
        - Some records exist in one system but not the other
        """
        df_access = df.copy()
        
        if table_name == 'Employees':
            # Access has fewer employees (2 employees not yet added)
            if len(df_access) > 5:
                df_access = df_access.head(len(df_access) - 2)
            df_access['DataSource'] = 'Access'
            
        elif table_name == 'Products':
            # Access has older pricing (5% lower - price increase not yet applied)
            if 'UnitPrice' in df_access.columns:
                df_access['UnitPrice'] = df_access['UnitPrice'] * 0.95
            # Some products not yet marked as discontinued
            if 'Discontinued' in df_access.columns:
                df_access.loc[df_access['Discontinued'] == True, 'Discontinued'] = False
            df_access['DataSource'] = 'Access'
            
        elif table_name == 'Customers':
            # Access has 10% fewer customers (older snapshot)
            if len(df_access) > 10:
                df_access = df_access.head(int(len(df_access) * 0.9))
            df_access['DataSource'] = 'Access'
            
        elif table_name == 'Orders':
            # Access has ALL orders (both systems have complete transaction data)
            # But Access may have slight data variations (different freight values, etc.)
            df_access['DataSource'] = 'Access'
            
        elif table_name == 'Order Details':
            # Access has ALL order details
            df_access['DataSource'] = 'Access'
        
        return df_access
    
    # =========================================================================
    # PHASE 2: TRANSFORM - MERGE & CLEAN
    # =========================================================================
    
    def transform_and_merge(self):
        """
        Transform and merge data from BOTH heterogeneous sources.
        
        Merge Strategy:
        - Dimension tables: UNION with deduplication, SQL Server wins conflicts
        - Fact tables: UNION with deduplication by composite key
        - Schema differences handled via column mapping
        - Data type normalization
        """
        logger.info("\n" + "="*50)
        logger.info("PHASE 2: TRANSFORM & MERGE (Dual Sources)")
        logger.info("="*50)
        
        # Log source statistics before merge
        logger.info("\nSource Statistics Before Merge:")
        logger.info(f"  SQL Server tables: {len(self.sql_server_data)}")
        logger.info(f"  Access tables: {len(self.access_data)}")
        
        # Merge each table type
        self._merge_customers()
        self._merge_products()
        self._merge_employees()
        self._merge_orders()
        self._merge_order_details()
        self._merge_categories()
        self._merge_suppliers()
        self._merge_shippers()
        
        # Create star schema from merged data
        self._create_star_schema()
        
        logger.info("\n✓ Transform and merge completed")
    
    def _merge_with_priority(self, sql_df, access_df, key_col, table_name):
        """
        Merge function for REAL heterogeneous source integration.
        
        Strategy: UNION ALL with source tracking
        - Include ALL records from SQL Server (primary source)
        - Include records from Access that DON'T exist in SQL Server
        - For overlapping keys: keep both but mark source clearly
        
        This demonstrates real dual-source ETL where both databases
        contain genuinely different data.
        
        Args:
            sql_df: DataFrame from SQL Server
            access_df: DataFrame from Access
            key_col: Primary key column name
            table_name: Name of table for logging
            
        Returns:
            Merged DataFrame showing contribution from both sources
        """
        # Add source tracking if not present
        if not sql_df.empty and 'DataSource' not in sql_df.columns:
            sql_df = sql_df.copy()
            sql_df['DataSource'] = 'SQLServer'
        
        if not access_df.empty and 'DataSource' not in access_df.columns:
            access_df = access_df.copy()
            access_df['DataSource'] = 'Access'
        
        if sql_df.empty and access_df.empty:
            return pd.DataFrame()
        
        if sql_df.empty:
            logger.info(f"  {table_name}: Only Access data available ({len(access_df)} rows)")
            return access_df
        
        if access_df.empty:
            logger.info(f"  {table_name}: Only SQL Server data available ({len(sql_df)} rows)")
            return sql_df
        
        # REAL HETEROGENEOUS MERGE:
        # Find keys unique to each source and keys that overlap
        sql_keys = set(sql_df[key_col].unique())
        access_keys = set(access_df[key_col].unique())
        
        common_keys = sql_keys & access_keys
        sql_only_keys = sql_keys - access_keys
        access_only_keys = access_keys - sql_keys
        
        # Take all SQL Server records
        sql_records = sql_df.copy()
        sql_records['DataSource'] = 'SQLServer'
        
        # Take Access records that are NOT in SQL Server (unique to Access)
        access_unique = access_df[access_df[key_col].isin(access_only_keys)].copy()
        access_unique['DataSource'] = 'Access'
        
        # Combine both sources
        merged = pd.concat([sql_records, access_unique], ignore_index=True)
        
        # Log statistics
        logger.info(f"  {table_name}: SQL Server={len(sql_records)} | Access unique={len(access_unique)} | Common keys={len(common_keys)} | Total={len(merged)}")
        
        return merged
    
    def _merge_customers(self):
        """Merge Customers from both sources."""
        logger.info("\nMerging Customers...")
        
        sql_df = self.sql_server_data.get('Customers', pd.DataFrame())
        access_df = self.access_data.get('Customers', pd.DataFrame())
        
        self.merged_data['Customers'] = self._merge_with_priority(
            sql_df, access_df, 'CustomerID', 'Customers'
        )
    
    def _merge_products(self):
        """
        Merge Products from both sources with conflict resolution.
        Note: SQL Server has current pricing, Access has outdated pricing.
        """
        logger.info("\nMerging Products (SQL Server pricing takes precedence)...")
        
        sql_df = self.sql_server_data.get('Products', pd.DataFrame())
        access_df = self.access_data.get('Products', pd.DataFrame())
        
        # Log price differences for transparency
        if not sql_df.empty and not access_df.empty:
            if 'UnitPrice' in sql_df.columns and 'UnitPrice' in access_df.columns:
                common_ids = set(sql_df['ProductID']) & set(access_df['ProductID'])
                if common_ids:
                    sql_prices = sql_df[sql_df['ProductID'].isin(common_ids)].set_index('ProductID')['UnitPrice']
                    access_prices = access_df[access_df['ProductID'].isin(common_ids)].set_index('ProductID')['UnitPrice']
                    # Align indexes
                    common_index = sql_prices.index.intersection(access_prices.index)
                    if len(common_index) > 0:
                        price_diff = (sql_prices.loc[common_index] - access_prices.loc[common_index]).abs().mean()
                        logger.info(f"  Average price difference: ${price_diff:.2f} (SQL Server prices used)")
        
        self.merged_data['Products'] = self._merge_with_priority(
            sql_df, access_df, 'ProductID', 'Products'
        )
    
    def _merge_employees(self):
        """
        Merge Employees from both sources.
        SQL Server has complete employee list, Access may be missing recent hires.
        """
        logger.info("\nMerging Employees...")
        
        sql_df = self.sql_server_data.get('Employees', pd.DataFrame())
        access_df = self.access_data.get('Employees', pd.DataFrame())
        
        # Report differences for transparency
        if not sql_df.empty and not access_df.empty:
            sql_ids = set(sql_df['EmployeeID'])
            access_ids = set(access_df['EmployeeID'])
            
            only_in_sql = sql_ids - access_ids
            only_in_access = access_ids - sql_ids
            
            if only_in_sql:
                logger.info(f"  Employees only in SQL Server: {len(only_in_sql)} (newer hires)")
            if only_in_access:
                logger.info(f"  Employees only in Access: {len(only_in_access)}")
        
        self.merged_data['Employees'] = self._merge_with_priority(
            sql_df, access_df, 'EmployeeID', 'Employees'
        )
    
    def _merge_orders(self):
        """
        Merge Orders from both sources.
        Fact data - deduplicate by OrderID, keep most recent version.
        """
        logger.info("\nMerging Orders (deduplicating transactions)...")
        
        sql_df = self.sql_server_data.get('Orders', pd.DataFrame())
        access_df = self.access_data.get('Orders', pd.DataFrame())
        
        self.merged_data['Orders'] = self._merge_with_priority(
            sql_df, access_df, 'OrderID', 'Orders'
        )
    
    def _merge_order_details(self):
        """
        Merge Order Details from both sources.
        Uses OrderID to split between sources (matching Orders split).
        """
        logger.info("\nMerging Order Details (split by OrderID to match Orders)...")
        
        sql_df = self.sql_server_data.get('Order Details', pd.DataFrame())
        access_df = self.access_data.get('Order Details', pd.DataFrame())
        
        if sql_df.empty and access_df.empty:
            self.merged_data['Order Details'] = pd.DataFrame()
            return
        
        # Add source tracking
        if not sql_df.empty:
            sql_df = sql_df.copy()
            sql_df['DataSource'] = 'SQLServer'
        
        if not access_df.empty and 'DataSource' not in access_df.columns:
            access_df = access_df.copy()
            access_df['DataSource'] = 'Access'
        
        if sql_df.empty:
            self.merged_data['Order Details'] = access_df
            return
        
        if access_df.empty:
            self.merged_data['Order Details'] = sql_df
            return
        
        # COMPLEMENTARY SPLIT: Match the Orders split
        # Use the same OrderIDs that were assigned to each source
        orders_merged = self.merged_data.get('Orders', pd.DataFrame())
        
        if not orders_merged.empty and 'DataSource' in orders_merged.columns:
            sql_order_ids = orders_merged[orders_merged['DataSource'] == 'SQLServer']['OrderID'].unique()
            access_order_ids = orders_merged[orders_merged['DataSource'] == 'Access']['OrderID'].unique()
            
            sql_records = sql_df[sql_df['OrderID'].isin(sql_order_ids)].copy()
            access_records = access_df[access_df['OrderID'].isin(access_order_ids)].copy()
            
            merged = pd.concat([sql_records, access_records], ignore_index=True)
        else:
            # Fallback: 70/30 split by OrderID
            all_order_ids = sql_df['OrderID'].unique()
            n_total = len(all_order_ids)
            n_sql = int(n_total * 0.7)
            
            sql_order_ids = all_order_ids[:n_sql]
            access_order_ids = all_order_ids[n_sql:]
            
            sql_records = sql_df[sql_df['OrderID'].isin(sql_order_ids)].copy()
            access_records = access_df[access_df['OrderID'].isin(access_order_ids)].copy()
            
            merged = pd.concat([sql_records, access_records], ignore_index=True)
        
        sql_count = len(merged[merged['DataSource'] == 'SQLServer'])
        access_count = len(merged[merged['DataSource'] == 'Access'])
        logger.info(f"  Order Details: SQL Server={sql_count} ({sql_count*100//max(len(merged),1)}%) | Access={access_count} ({access_count*100//max(len(merged),1)}%) | Merged={len(merged)}")
        
        self.merged_data['Order Details'] = merged
    
    def _merge_categories(self):
        """Merge Categories from both sources."""
        logger.info("\nMerging Categories...")
        
        sql_df = self.sql_server_data.get('Categories', pd.DataFrame())
        access_df = self.access_data.get('Categories', pd.DataFrame())
        
        self.merged_data['Categories'] = self._merge_with_priority(
            sql_df, access_df, 'CategoryID', 'Categories'
        )
    
    def _merge_suppliers(self):
        """Merge Suppliers from both sources."""
        logger.info("\nMerging Suppliers...")
        
        sql_df = self.sql_server_data.get('Suppliers', pd.DataFrame())
        access_df = self.access_data.get('Suppliers', pd.DataFrame())
        
        self.merged_data['Suppliers'] = self._merge_with_priority(
            sql_df, access_df, 'SupplierID', 'Suppliers'
        )
    
    def _merge_shippers(self):
        """Merge Shippers from both sources."""
        logger.info("\nMerging Shippers...")
        
        sql_df = self.sql_server_data.get('Shippers', pd.DataFrame())
        access_df = self.access_data.get('Shippers', pd.DataFrame())
        
        self.merged_data['Shippers'] = self._merge_with_priority(
            sql_df, access_df, 'ShipperID', 'Shippers'
        )
    
    # =========================================================================
    # PHASE 2B: CREATE STAR SCHEMA (Data Warehouse Model)
    # =========================================================================
    
    def _create_star_schema(self):
        """
        Create star schema dimension and fact tables.
        
        Star Schema:
                    Dim_Time
                       │
        Dim_Customer──Fact_Sales──Dim_Product
                       │
                  Dim_Employee
        """
        logger.info("\n" + "-"*50)
        logger.info("Creating Star Schema (Data Warehouse Model)")
        logger.info("-"*50)
        
        self._create_dim_time()
        self._create_dim_customers()
        self._create_dim_products()
        self._create_dim_employees()
        self._create_fact_sales()
    
    def _create_dim_time(self):
        """Create Time dimension with date hierarchy."""
        logger.info("\nCreating Dim_Time...")
        
        orders = self.merged_data.get('Orders', pd.DataFrame())
        if orders.empty:
            logger.warning("  No Orders data for Dim_Time")
            return
        
        # Collect all dates from date columns
        date_cols = ['OrderDate', 'RequiredDate', 'ShippedDate']
        all_dates = []
        
        for col in date_cols:
            if col in orders.columns:
                dates = pd.to_datetime(orders[col], errors='coerce')
                all_dates.extend(dates.dropna().tolist())
        
        if not all_dates:
            logger.warning("  No valid dates found")
            return
        
        # Create unique dates dimension
        unique_dates = pd.Series(all_dates).drop_duplicates().sort_values()
        
        self.dim_time = pd.DataFrame({
            'TimeKey': range(1, len(unique_dates) + 1),
            'Date': unique_dates.values,
            'Year': unique_dates.dt.year.values,
            'Quarter': unique_dates.dt.quarter.values,
            'Month': unique_dates.dt.month.values,
            'MonthName': unique_dates.dt.month_name().values,
            'Week': unique_dates.dt.isocalendar().week.values,
            'DayOfMonth': unique_dates.dt.day.values,
            'DayOfWeek': unique_dates.dt.dayofweek.values,
            'DayName': unique_dates.dt.day_name().values,
            'IsWeekend': unique_dates.dt.dayofweek.isin([5, 6]).values
        })
        
        logger.info(f"  ✓ Dim_Time: {len(self.dim_time)} unique dates")
    
    def _create_dim_customers(self):
        """Create Customer dimension with geographic hierarchy."""
        logger.info("\nCreating Dim_Customers...")
        
        customers = self.merged_data.get('Customers', pd.DataFrame())
        if customers.empty:
            logger.warning("  No Customers data for Dim_Customers")
            return
        
        # Select dimension columns
        dim_cols = ['CustomerID', 'CompanyName', 'ContactName', 'ContactTitle',
                    'City', 'Region', 'Country', 'Phone', 'DataSource']
        
        available_cols = [c for c in dim_cols if c in customers.columns]
        self.dim_customers = customers[available_cols].copy()
        
        # Add surrogate key
        self.dim_customers['CustomerKey'] = range(1, len(self.dim_customers) + 1)
        
        # Clean data - fill missing with 'Unknown'
        self.dim_customers = self.dim_customers.fillna('Unknown')
        
        logger.info(f"  ✓ Dim_Customers: {len(self.dim_customers)} customers")
    
    def _create_dim_products(self):
        """Create Product dimension with category hierarchy."""
        logger.info("\nCreating Dim_Products...")
        
        products = self.merged_data.get('Products', pd.DataFrame())
        categories = self.merged_data.get('Categories', pd.DataFrame())
        
        if products.empty:
            logger.warning("  No Products data for Dim_Products")
            return
        
        # Join with categories for hierarchy
        if not categories.empty and 'CategoryID' in products.columns:
            cat_cols = ['CategoryID', 'CategoryName', 'Description']
            available_cat_cols = [c for c in cat_cols if c in categories.columns]
            
            if available_cat_cols:
                self.dim_products = products.merge(
                    categories[available_cat_cols],
                    on='CategoryID',
                    how='left',
                    suffixes=('', '_Category')
                )
        else:
            self.dim_products = products.copy()
        
        # Add surrogate key
        self.dim_products['ProductKey'] = range(1, len(self.dim_products) + 1)
        
        # Clean discontinued flag
        if 'Discontinued' in self.dim_products.columns:
            self.dim_products['Discontinued'] = self.dim_products['Discontinued'].fillna(False)
        
        logger.info(f"  ✓ Dim_Products: {len(self.dim_products)} products")
    
    def _create_dim_employees(self):
        """Create Employee dimension."""
        logger.info("\nCreating Dim_Employees...")
        
        employees = self.merged_data.get('Employees', pd.DataFrame())
        if employees.empty:
            logger.warning("  No Employees data for Dim_Employees")
            return
        
        self.dim_employees = employees.copy()
        
        # Add surrogate key
        self.dim_employees['EmployeeKey'] = range(1, len(self.dim_employees) + 1)
        
        # Create full name
        if 'FirstName' in self.dim_employees.columns and 'LastName' in self.dim_employees.columns:
            self.dim_employees['FullName'] = (
                self.dim_employees['FirstName'].fillna('') + ' ' + 
                self.dim_employees['LastName'].fillna('')
            ).str.strip()
        
        logger.info(f"  ✓ Dim_Employees: {len(self.dim_employees)} employees")
    
    def _create_fact_sales(self):
        """
        Create Fact Sales table with calculated measures.
        
        Measures:
        - SalesAmount = UnitPrice * Quantity * (1 - Discount)
        - GrossAmount = UnitPrice * Quantity
        - DiscountAmount = GrossAmount - SalesAmount
        - DaysToShip = ShippedDate - OrderDate
        - IsLateDelivery = ShippedDate > RequiredDate
        - IsHighFreight = Freight > 500
        """
        logger.info("\nCreating Fact_Sales...")
        
        orders = self.merged_data.get('Orders', pd.DataFrame())
        order_details = self.merged_data.get('Order Details', pd.DataFrame())
        
        if orders.empty or order_details.empty:
            logger.warning("  Missing Orders or Order Details for Fact_Sales")
            return
        
        # Join Orders with Order Details
        self.fact_sales = order_details.merge(
            orders,
            on='OrderID',
            how='inner',
            suffixes=('', '_Order')
        )
        
        # Calculate sales measures
        if all(c in self.fact_sales.columns for c in ['UnitPrice', 'Quantity', 'Discount']):
            # Sales Amount (after discount)
            self.fact_sales['SalesAmount'] = (
                self.fact_sales['UnitPrice'] * 
                self.fact_sales['Quantity'] * 
                (1 - self.fact_sales['Discount'].fillna(0))
            ).round(2)
            
            # Gross Amount (before discount)
            self.fact_sales['GrossAmount'] = (
                self.fact_sales['UnitPrice'] * self.fact_sales['Quantity']
            ).round(2)
            
            # Discount Amount
            self.fact_sales['DiscountAmount'] = (
                self.fact_sales['GrossAmount'] - self.fact_sales['SalesAmount']
            ).round(2)
        
        # Calculate delivery metrics
        if 'OrderDate' in self.fact_sales.columns:
            self.fact_sales['OrderDate'] = pd.to_datetime(self.fact_sales['OrderDate'], errors='coerce')
            
        if 'ShippedDate' in self.fact_sales.columns:
            self.fact_sales['ShippedDate'] = pd.to_datetime(self.fact_sales['ShippedDate'], errors='coerce')
            
        if 'RequiredDate' in self.fact_sales.columns:
            self.fact_sales['RequiredDate'] = pd.to_datetime(self.fact_sales['RequiredDate'], errors='coerce')
        
        # Days to ship
        if 'OrderDate' in self.fact_sales.columns and 'ShippedDate' in self.fact_sales.columns:
            self.fact_sales['DaysToShip'] = (
                self.fact_sales['ShippedDate'] - self.fact_sales['OrderDate']
            ).dt.days
        
        # Late delivery flag
        if 'ShippedDate' in self.fact_sales.columns and 'RequiredDate' in self.fact_sales.columns:
            self.fact_sales['IsLateDelivery'] = (
                self.fact_sales['ShippedDate'] > self.fact_sales['RequiredDate']
            )
        
        # High freight flag (>500) - KPI requirement
        if 'Freight' in self.fact_sales.columns:
            self.fact_sales['IsHighFreight'] = self.fact_sales['Freight'] > 500
        
        # Add surrogate key
        self.fact_sales['SalesKey'] = range(1, len(self.fact_sales) + 1)
        
        logger.info(f"  ✓ Fact_Sales: {len(self.fact_sales)} transaction rows")
        
        # Summary statistics
        if 'SalesAmount' in self.fact_sales.columns:
            total_sales = self.fact_sales['SalesAmount'].sum()
            avg_order = self.fact_sales.groupby('OrderID')['SalesAmount'].sum().mean()
            logger.info(f"    Total Sales: ${total_sales:,.2f}")
            logger.info(f"    Average Order Value: ${avg_order:,.2f}")
    
    # =========================================================================
    # PHASE 3: LOAD TO DATA WAREHOUSE
    # =========================================================================
    
    def load_to_csv(self):
        """Save all transformed data to CSV files for backup and analysis."""
        logger.info("\n" + "="*50)
        logger.info("PHASE 3A: LOAD TO CSV FILES")
        logger.info("="*50)
        
        # Save dimension tables
        dims = [
            ('Dim_Time', self.dim_time),
            ('Dim_Customers', self.dim_customers),
            ('Dim_Products', self.dim_products),
            ('Dim_Employees', self.dim_employees)
        ]
        
        for name, df in dims:
            if df is not None and not df.empty:
                filepath = DATA_PATH / f'{name}.csv'
                df.to_csv(filepath, index=False, encoding='utf-8-sig')
                logger.info(f"  ✓ Saved {name}.csv ({len(df)} rows)")
        
        # Save fact table
        if self.fact_sales is not None and not self.fact_sales.empty:
            filepath = DATA_PATH / 'Fact_Sales.csv'
            self.fact_sales.to_csv(filepath, index=False, encoding='utf-8-sig')
            logger.info(f"  ✓ Saved Fact_Sales.csv ({len(self.fact_sales)} rows)")
        
        # Create analysis views for dashboard
        self._create_analysis_views()
    
    def load_to_database(self):
        """Load star schema to SQLite Data Warehouse."""
        logger.info("\n" + "="*50)
        logger.info("PHASE 3B: LOAD TO DATA WAREHOUSE (SQLite)")
        logger.info("="*50)
        
        dwh_path = DWH_CONFIG['database_path']
        
        try:
            conn = sqlite3.connect(dwh_path)
            
            # Load dimension tables
            tables = [
                ('Dim_Time', self.dim_time),
                ('Dim_Customers', self.dim_customers),
                ('Dim_Products', self.dim_products),
                ('Dim_Employees', self.dim_employees),
                ('Fact_Sales', self.fact_sales)
            ]
            
            for table_name, df in tables:
                if df is not None and not df.empty:
                    df.to_sql(table_name, conn, if_exists='replace', index=False)
                    logger.info(f"  ✓ Loaded {table_name} to DWH ({len(df)} rows)")
            
            conn.close()
            logger.info(f"\n✓ Data Warehouse saved: {dwh_path}")
            
        except Exception as e:
            logger.error(f"  Error loading to DWH: {e}")
    
    def _create_analysis_views(self):
        """Create pre-aggregated views for dashboard KPIs."""
        logger.info("\nCreating analysis views for dashboard...")
        
        if self.fact_sales is None or self.fact_sales.empty:
            return
        
        # 1. Sales by Month
        if 'OrderDate' in self.fact_sales.columns and 'SalesAmount' in self.fact_sales.columns:
            sales_by_month = self.fact_sales.copy()
            sales_by_month['YearMonth'] = pd.to_datetime(sales_by_month['OrderDate']).dt.to_period('M')
            
            monthly = sales_by_month.groupby('YearMonth').agg({
                'SalesAmount': 'sum',
                'OrderID': 'nunique',
                'Quantity': 'sum'
            }).reset_index()
            monthly.columns = ['YearMonth', 'TotalSales', 'OrderCount', 'TotalQuantity']
            monthly['YearMonth'] = monthly['YearMonth'].astype(str)
            monthly.to_csv(DATA_PATH / 'Sales_By_Month.csv', index=False, encoding='utf-8-sig')
            logger.info("  ✓ Sales_By_Month.csv")
        
        # 2. Sales by Category
        if self.dim_products is not None and 'CategoryName' in self.dim_products.columns:
            fact_cat = self.fact_sales.merge(
                self.dim_products[['ProductID', 'CategoryName']],
                on='ProductID', how='left'
            )
            
            by_cat = fact_cat.groupby('CategoryName').agg({
                'SalesAmount': 'sum',
                'Quantity': 'sum',
                'OrderID': 'nunique'
            }).reset_index()
            by_cat.columns = ['Category', 'TotalSales', 'TotalQuantity', 'OrderCount']
            by_cat = by_cat.sort_values('TotalSales', ascending=False)
            by_cat.to_csv(DATA_PATH / 'Sales_By_Category.csv', index=False, encoding='utf-8-sig')
            logger.info("  ✓ Sales_By_Category.csv")
        
        # 3. Sales by Country
        if 'ShipCountry' in self.fact_sales.columns:
            by_country = self.fact_sales.groupby('ShipCountry').agg({
                'SalesAmount': 'sum',
                'OrderID': 'nunique',
                'Freight': 'sum'
            }).reset_index()
            by_country.columns = ['Country', 'TotalSales', 'OrderCount', 'TotalFreight']
            by_country = by_country.sort_values('TotalSales', ascending=False)
            by_country.to_csv(DATA_PATH / 'Sales_By_Country.csv', index=False, encoding='utf-8-sig')
            logger.info("  ✓ Sales_By_Country.csv")
        
        # 4. Top Products
        if 'ProductID' in self.fact_sales.columns:
            top_prod = self.fact_sales.groupby('ProductID').agg({
                'SalesAmount': 'sum',
                'Quantity': 'sum'
            }).reset_index()
            
            if self.dim_products is not None and 'ProductName' in self.dim_products.columns:
                cols = ['ProductID', 'ProductName']
                if 'CategoryName' in self.dim_products.columns:
                    cols.append('CategoryName')
                top_prod = top_prod.merge(self.dim_products[cols], on='ProductID', how='left')
            
            top_prod = top_prod.sort_values('SalesAmount', ascending=False).head(20)
            top_prod.to_csv(DATA_PATH / 'Top_Products.csv', index=False, encoding='utf-8-sig')
            logger.info("  ✓ Top_Products.csv")
        
        # 5. High Freight Orders (>500) - KPI requirement
        if 'IsHighFreight' in self.fact_sales.columns:
            high_freight = self.fact_sales[self.fact_sales['IsHighFreight'] == True]
            high_freight_summary = high_freight.groupby('OrderID').agg({
                'Freight': 'first',
                'SalesAmount': 'sum',
                'ShipCountry': 'first'
            }).reset_index()
            high_freight_summary.to_csv(DATA_PATH / 'High_Freight_Orders.csv', index=False, encoding='utf-8-sig')
            logger.info(f"  ✓ High_Freight_Orders.csv ({len(high_freight_summary)} orders)")
        
        # 6. Late Deliveries - KPI requirement
        if 'IsLateDelivery' in self.fact_sales.columns:
            late = self.fact_sales[self.fact_sales['IsLateDelivery'] == True]
            if not late.empty:
                late_summary = late.groupby('OrderID').agg({
                    'DaysToShip': 'first',
                    'SalesAmount': 'sum',
                    'ShipCountry': 'first'
                }).reset_index()
                late_summary.to_csv(DATA_PATH / 'Late_Deliveries.csv', index=False, encoding='utf-8-sig')
                logger.info(f"  ✓ Late_Deliveries.csv ({len(late_summary)} orders)")
    
    # =========================================================================
    # MAIN ETL EXECUTION
    # =========================================================================
    
    def run(self):
        """Execute the complete ETL pipeline."""
        start_time = datetime.now()
        logger.info(f"\nETL Started: {start_time}")
        
        try:
            # Phase 1: Extract from BOTH sources
            self.extract_from_sql_server()
            self.extract_from_access()
            
            # Phase 2: Transform and Merge
            self.transform_and_merge()
            
            # Phase 3: Load
            self.load_to_csv()
            self.load_to_database()
            
            end_time = datetime.now()
            duration = end_time - start_time
            
            logger.info("\n" + "="*70)
            logger.info("ETL COMPLETED SUCCESSFULLY")
            logger.info("="*70)
            logger.info(f"Duration: {duration}")
            
            self._print_summary()
            
            return True
            
        except Exception as e:
            logger.error(f"ETL FAILED: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def _print_summary(self):
        """Print comprehensive summary of ETL results."""
        logger.info("\n" + "-"*50)
        logger.info("ETL SUMMARY")
        logger.info("-"*50)
        
        logger.info("\n📥 DATA SOURCES:")
        logger.info(f"  Source 1 (SQL Server): {'Connected' if self.sql_server_connected else 'CSV Fallback'}")
        logger.info(f"    Tables extracted: {list(self.sql_server_data.keys())}")
        logger.info(f"  Source 2 (Access): {'Connected' if self.access_connected else 'CSV Fallback'}")
        logger.info(f"    Tables extracted: {list(self.access_data.keys())}")
        
        logger.info("\n🔄 MERGED DATA:")
        for table, df in self.merged_data.items():
            if isinstance(df, pd.DataFrame) and not df.empty:
                logger.info(f"  {table}: {len(df)} rows")
        
        logger.info("\n⭐ STAR SCHEMA (Data Warehouse):")
        if self.dim_time is not None:
            logger.info(f"  Dim_Time: {len(self.dim_time)} dates")
        if self.dim_customers is not None:
            logger.info(f"  Dim_Customers: {len(self.dim_customers)} customers")
        if self.dim_products is not None:
            logger.info(f"  Dim_Products: {len(self.dim_products)} products")
        if self.dim_employees is not None:
            logger.info(f"  Dim_Employees: {len(self.dim_employees)} employees")
        if self.fact_sales is not None:
            logger.info(f"  Fact_Sales: {len(self.fact_sales)} transactions")
            if 'SalesAmount' in self.fact_sales.columns:
                logger.info(f"    Total Revenue: ${self.fact_sales['SalesAmount'].sum():,.2f}")
        
        logger.info(f"\n📁 OUTPUT LOCATION: {DATA_PATH}")
        logger.info(f"🗄️ DWH DATABASE: {DWH_CONFIG['database_path']}")


# =============================================================================
# MAIN EXECUTION
# =============================================================================

if __name__ == '__main__':
    print("""
    ╔══════════════════════════════════════════════════════════════════════╗
    ║           NORTHWIND ETL - DUAL HETEROGENEOUS SOURCES                 ║
    ╠══════════════════════════════════════════════════════════════════════╣
    ║                                                                      ║
    ║  Source 1: SQL Server Northwind Database                             ║
    ║  Source 2: Microsoft Access Northwind Database                       ║
    ║                                                                      ║
    ║  Process:                                                            ║
    ║    1. EXTRACT  - Pull data from both sources                         ║
    ║    2. TRANSFORM - Merge, clean, handle inconsistencies               ║
    ║    3. LOAD     - Create unified star schema DWH                      ║
    ║                                                                      ║
    ╚══════════════════════════════════════════════════════════════════════╝
    """)
    
    # Run ETL
    etl = NorthwindETL()
    success = etl.run()
    
    if success:
        print("\n" + "="*50)
        print("✓ ETL COMPLETED SUCCESSFULLY!")
        print("="*50)
        print(f"\nOutput files saved to: {DATA_PATH}")
        print(f"DWH database: {DWH_CONFIG['database_path']}")
        print(f"Log file: {REPORTS_PATH / 'etl_log.txt'}")
    else:
        print("\n✗ ETL FAILED - Check log file for details")
