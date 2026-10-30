import sqlite3
import os
from datetime import datetime

# Database path configuration (compatible with local development and Vercel serverless)
if os.environ.get('VERCEL') or os.environ.get('AWS_LAMBDA_FUNCTION_NAME'):
    # Vercel serverless functions have a read-only filesystem except for /tmp
    DB_PATH = '/tmp/app.db'
else:
    DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'app.db')

def get_db_connection():
    """Establish and return a connection to the SQLite database."""
    # Ensure parent directory exists before connecting
    parent_dir = os.path.dirname(DB_PATH)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    # This allows us to access columns by name (like dictionaries) instead of index
    conn.row_factory = sqlite3.Row 
    # Enable foreign key constraint enforcement in SQLite
    conn.execute('PRAGMA foreign_keys = ON')
    return conn

def init_db():
    """Initialize the database by creating necessary tables if they do not exist."""
    is_new_db = not os.path.exists(DB_PATH)
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create Customers Table
    # Stores core details about the customer with local current date and time
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            country TEXT,
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
        )
    ''')
    
    # Create Transactions Table
    # Stores individual purchases made by customers
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            transaction_date DATE NOT NULL,
            amount REAL NOT NULL,
            category TEXT,
            FOREIGN KEY (customer_id) REFERENCES customers (id) ON DELETE CASCADE
        )
    ''')
    
    conn.commit()
    
    # If freshly initialized on Vercel or in /tmp, automatically seed with initial dataset
    if is_new_db or os.environ.get('VERCEL'):
        cust_count = cursor.execute('SELECT COUNT(*) FROM customers').fetchone()[0] or 0
        if cust_count == 0:
            try:
                from seed_customers import seed_sample_records
                seed_sample_records()
            except Exception as e:
                print("Notice: Auto-seeding database failed:", e)
                
    conn.close()

def insert_customer(name, email, phone, country, created_at=None):
    """Insert a new customer into the database using parameterized queries with current local datetime."""
    conn = get_db_connection()
    cursor = conn.cursor()
    if not created_at:
        # Guarantee real current date and time in user's local timezone
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        # The '?' placeholders protect against SQL injection
        cursor.execute(
            'INSERT INTO customers (name, email, phone, country, created_at) VALUES (?, ?, ?, ?, ?)',
            (name, email, phone, country, created_at)
        )
        conn.commit()
        customer_id = cursor.lastrowid
        return True, customer_id
    except sqlite3.IntegrityError:
        # Catches the case where an email is not unique
        return False, "A customer with this email already exists."
    finally:
        conn.close()

def insert_transaction(customer_id, transaction_date, amount, category):
    """Insert a new transaction linked to a specific customer."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'INSERT INTO transactions (customer_id, transaction_date, amount, category) VALUES (?, ?, ?, ?)',
            (customer_id, transaction_date, amount, category)
        )
        conn.commit()
        return True, "Transaction added successfully."
    except sqlite3.IntegrityError:
        return False, "Invalid Customer ID. Transaction could not be linked."
    finally:
        conn.close()

# Run database initialization when this file is executed directly
if __name__ == '__main__':
    init_db()
    print("Database initialized successfully at:", DB_PATH)
