import psycopg2
from psycopg2.extras import RealDictCursor
from config import Config

def get_db_connection():
    """Create and return a database connection"""
    conn = psycopg2.connect(Config.DATABASE_URL, cursor_factory=RealDictCursor)
    return conn

def init_db():
    """Initialize the database with schema"""
    conn = get_db_connection()
    cur = conn.cursor()

    with open('../database/schema.sql', 'r') as f:
        cur.execute(f.read())

    conn.commit()
    cur.close()
    conn.close()
    print("Database initialized successfully!")

if __name__ == '__main__':
    init_db()
