import random
from datetime import datetime, timedelta
from database import get_db_connection

def generate_sample_data():
    """Generate realistic sample retail sales data"""
    conn = get_db_connection()
    cur = conn.cursor()

    # Sample products
    products = [
        ('Laptop', 'Electronics', 899.99),
        ('Wireless Mouse', 'Electronics', 29.99),
        ('Office Chair', 'Furniture', 199.99),
        ('Desk Lamp', 'Furniture', 49.99),
        ('Coffee Maker', 'Appliances', 79.99),
        ('Water Bottle', 'Accessories', 19.99),
        ('Notebook Set', 'Stationery', 12.99),
        ('USB Cable', 'Electronics', 9.99),
        ('Backpack', 'Accessories', 59.99),
        ('Desk Organizer', 'Stationery', 24.99)
    ]

    print("Inserting products...")
    for product in products:
        cur.execute(
            "INSERT INTO products (product_name, category, unit_price) VALUES (%s, %s, %s) RETURNING product_id",
            product
        )

    conn.commit()

    # Get product IDs
    cur.execute("SELECT product_id, product_name, unit_price FROM products")
    product_records = cur.fetchall()

    # Generate 2 years of historical sales data
    print("Generating sales data...")
    start_date = datetime.now() - timedelta(days=730)  # 2 years ago
    end_date = datetime.now()

    sales_records = []
    current_date = start_date

    while current_date <= end_date:
        for product in product_records:
            # Base quantity with seasonal trends
            day_of_year = current_date.timetuple().tm_yday
            seasonal_factor = 1 + 0.3 * abs((day_of_year - 182.5) / 182.5)  # Peak at mid-year

            # Weekly pattern (lower on weekends)
            day_of_week = current_date.weekday()
            weekly_factor = 0.7 if day_of_week >= 5 else 1.0

            # More consistent base quantity for better predictability
            base_quantity = 30 + random.randint(-5, 5)
            quantity = int(base_quantity * seasonal_factor * weekly_factor)

            # Add small random noise
            quantity = max(1, quantity + random.randint(-2, 2))

            total_amount = quantity * float(product['unit_price'])

            sales_records.append((
                product['product_id'],
                current_date.date(),
                quantity,
                total_amount
            ))

        current_date += timedelta(days=1)

    # Batch insert sales data
    cur.executemany(
        "INSERT INTO sales_data (product_id, sale_date, quantity_sold, total_amount) VALUES (%s, %s, %s, %s)",
        sales_records
    )

    conn.commit()
    cur.close()
    conn.close()

    print(f"Successfully generated {len(sales_records)} sales records!")
    print(f"Date range: {start_date.date()} to {end_date.date()}")

if __name__ == '__main__':
    generate_sample_data()
