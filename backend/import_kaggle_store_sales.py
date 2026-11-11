"""
Import script for Kaggle Store Sales - Time Series Forecasting dataset
Dataset: https://www.kaggle.com/competitions/store-sales-time-series-forecasting

Instructions:
1. Download the dataset from Kaggle (requires Kaggle account)
2. Extract all CSV files to a folder (e.g., data/store-sales/)
3. Run this script: python import_kaggle_store_sales.py --data-dir data/store-sales/
"""

import os
import pandas as pd
import argparse
from psycopg2.extras import execute_values
from database import get_connection

def import_store_sales_data(data_dir):
    """Import Kaggle Store Sales dataset into PostgreSQL"""

    print("Starting import of Kaggle Store Sales dataset...")
    print(f"Data directory: {data_dir}")

    # Load CSV files first so a missing file never leaves the database half-cleared
    print("\nLoading CSV files...")
    try:
        train_df = pd.read_csv(os.path.join(data_dir, "train.csv"))
        print(f"  train.csv: {len(train_df):,} rows")
    except FileNotFoundError:
        print("ERROR: train.csv not found. Please download the dataset from Kaggle.")
        return

    # Planned promotions (ADR-0002): Kaggle's test.csv lists the promotions for 2017-08-16..31
    try:
        test_df = pd.read_csv(os.path.join(data_dir, "test.csv"))
        print(f"  test.csv: {len(test_df):,} rows (planned promotions)")
    except FileNotFoundError:
        print("  WARNING: test.csv not found. No planned promotions will be seeded.")
        test_df = None

    with get_connection() as conn:
        _import(conn, data_dir, train_df, test_df)


def _import(conn, data_dir, train_df, test_df):
    cur = conn.cursor()

    # Clear existing data (runs and evaluations reference products and are cleared by CASCADE)
    print("\nClearing existing data...")
    cur.execute('TRUNCATE forecast_run_samples, forecasts, forecast_runs, evaluation_service_level, '
                'evaluation_metrics, evaluation_runs, planned_promotions, sales_data, oil_prices, '
                'holidays, products RESTART IDENTITY CASCADE')
    print("Existing data cleared.")

    # Load oil prices
    try:
        oil_df = pd.read_csv(os.path.join(data_dir, "oil.csv"))
        print(f"  oil.csv: {len(oil_df):,} rows")
    except FileNotFoundError:
        print("  WARNING: oil.csv not found. Continuing without oil prices.")
        oil_df = None

    # Load holidays
    try:
        holidays_df = pd.read_csv(os.path.join(data_dir, "holidays_events.csv"))
        print(f"  holidays_events.csv: {len(holidays_df):,} rows")
    except FileNotFoundError:
        print("  WARNING: holidays_events.csv not found. Continuing without holidays.")
        holidays_df = None

    # Get unique product families (these will be our products)
    print("\nImporting products (product families)...")
    families = train_df['family'].unique()

    # Assign reasonable prices to product families (estimated retail prices)
    family_prices = {
        'AUTOMOTIVE': 45.99,
        'BABY CARE': 12.99,
        'BEAUTY': 18.99,
        'BEVERAGES': 3.99,
        'BOOKS': 14.99,
        'BREAD/BAKERY': 4.99,
        'CELEBRATION': 24.99,
        'CLEANING': 8.99,
        'DAIRY': 5.99,
        'DELI': 7.99,
        'EGGS': 3.99,
        'FROZEN FOODS': 6.99,
        'GROCERY I': 9.99,
        'GROCERY II': 11.99,
        'HARDWARE': 15.99,
        'HOME AND KITCHEN I': 22.99,
        'HOME AND KITCHEN II': 28.99,
        'HOME APPLIANCES': 89.99,
        'HOME CARE': 12.99,
        'LADIESWEAR': 34.99,
        'LAWN AND GARDEN': 19.99,
        'LINGERIE': 16.99,
        'LIQUOR,WINE,BEER': 18.99,
        'MAGAZINES': 5.99,
        'MEATS': 12.99,
        'PERSONAL CARE': 9.99,
        'PET SUPPLIES': 13.99,
        'PLAYERS AND ELECTRONICS': 129.99,
        'POULTRY': 8.99,
        'PREPARED FOODS': 7.99,
        'PRODUCE': 4.99,
        'SCHOOL AND OFFICE SUPPLIES': 11.99,
        'SEAFOOD': 14.99
    }

    product_id_map = {}
    price_map = {}
    for family in sorted(families):
        # Determine category
        category = 'Grocery'
        if 'CARE' in family or 'BEAUTY' in family or 'LINGERIE' in family:
            category = 'Personal Care'
        elif 'ELECTRONICS' in family or 'PLAYERS' in family or 'APPLIANCES' in family:
            category = 'Electronics'
        elif 'HOME' in family or 'KITCHEN' in family or 'HARDWARE' in family:
            category = 'Home & Kitchen'
        elif 'WEAR' in family or 'CLOTHING' in family:
            category = 'Apparel'
        elif 'AUTOMOTIVE' in family:
            category = 'Automotive'
        elif 'BOOKS' in family or 'MAGAZINES' in family:
            category = 'Books & Media'

        price = family_prices.get(family, 9.99)

        # Clean up family name for product name
        product_name = family.title().replace('And', 'and')

        cur.execute(
            "INSERT INTO products (product_name, category, unit_price) VALUES (%s, %s, %s) RETURNING product_id",
            (product_name, category, price)
        )
        product_id = cur.fetchone()['product_id']
        product_id_map[family] = product_id
        price_map[family] = price

    print(f"Imported {len(product_id_map)} products")

    # Import oil prices
    if oil_df is not None:
        print("\nImporting oil prices...")
        oil_records = [(row.date, float(row.dcoilwtico))
                       for row in oil_df.itertuples() if pd.notna(row.dcoilwtico)]

        if oil_records:
            execute_values(
                cur,
                "INSERT INTO oil_prices (date, dcoilwtico) VALUES %s ON CONFLICT (date) DO NOTHING",
                oil_records
            )
            print(f"Imported {len(oil_records)} oil price records")

    # Import holidays
    if holidays_df is not None:
        print("\nImporting holidays...")
        holiday_records = [
            (row['date'], row.get('type', ''), row.get('locale', ''), row.get('locale_name', ''),
             row.get('description', ''), bool(row.get('transferred', False)))
            for row in holidays_df.to_dict('records')
        ]

        if holiday_records:
            execute_values(
                cur,
                "INSERT INTO holidays (date, type, locale, locale_name, description, transferred) VALUES %s",
                holiday_records
            )
            print(f"Imported {len(holiday_records)} holiday records")

    # Import sales data
    print("\nImporting sales data...")
    print("This may take several minutes for large datasets...")

    # Aggregate sales by date and family (sum across all stores)
    print("  Aggregating sales by date and product family...")
    sales_agg = train_df.groupby(['date', 'family']).agg({
        'sales': 'sum',
        'onpromotion': 'sum'  # Sum promotion count across stores
    }).reset_index()

    # Prepare data for insertion. Quantities stay fractional for weighed families (ADR-0001).
    sales_agg['product_id'] = sales_agg['family'].map(product_id_map)
    sales_agg['quantity_sold'] = sales_agg['sales'].round(3)
    sales_agg['total_amount'] = (sales_agg['quantity_sold'] * sales_agg['family'].map(price_map)).round(2)
    sales_agg['on_promotion'] = sales_agg['onpromotion'].fillna(0).astype(int)
    sales_records = list(zip(
        sales_agg['product_id'].astype(int), sales_agg['date'], sales_agg['quantity_sold'].astype(float),
        sales_agg['total_amount'].astype(float), sales_agg['on_promotion']
    ))

    print(f"  Inserting {len(sales_records):,} sales records...")

    # Batch insert
    batch_size = 10000
    for i in range(0, len(sales_records), batch_size):
        batch = sales_records[i:i+batch_size]
        execute_values(
            cur,
            "INSERT INTO sales_data (product_id, sale_date, quantity_sold, total_amount, on_promotion) VALUES %s",
            batch
        )
        print(f"    Inserted {min(i+batch_size, len(sales_records)):,} / {len(sales_records):,} records")

    # Seed planned promotions from test.csv
    n_planned = 0
    if test_df is not None:
        planned = test_df.groupby(['date', 'family'])['onpromotion'].sum().reset_index()
        planned_records = [(product_id_map[r.family], r.date, int(r.onpromotion))
                           for r in planned.itertuples() if r.family in product_id_map]
        if planned_records:
            execute_values(
                cur,
                "INSERT INTO planned_promotions (product_id, date, on_promotion) VALUES %s",
                planned_records
            )
        n_planned = len(planned_records)
        print(f"  Seeded {n_planned:,} planned promotion rows")

    # Get date range
    cur.execute("SELECT MIN(sale_date) as min_date, MAX(sale_date) as max_date FROM sales_data")
    date_range = cur.fetchone()

    print("\n" + "="*60)
    print("Import completed successfully!")
    print("="*60)
    print(f"Products imported: {len(product_id_map)}")
    print(f"Sales records imported: {len(sales_records):,}")
    print(f"Date range: {date_range['min_date']} to {date_range['max_date']}")
    print(f"Duration: {(date_range['max_date'] - date_range['min_date']).days} days")
    print("\nYou can now use the forecaster with real Kaggle data!")

    cur.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Import Kaggle Store Sales dataset')
    parser.add_argument('--data-dir', type=str, default='data/store-sales',
                      help='Directory containing the extracted Kaggle CSV files')

    args = parser.parse_args()

    import_store_sales_data(args.data_dir)
