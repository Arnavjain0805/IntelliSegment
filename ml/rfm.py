import pandas as pd
import sqlite3
import os
import sys
from datetime import datetime

# Ensure project root is in sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import database as db

def get_rfm_data():
    """
    Connects to the database and calculates Recency, Frequency, and Monetary (RFM)
    metrics for each customer based on their transaction history.
    """
    if not os.path.exists(db.DB_PATH):
        return None
        
    conn = db.get_db_connection()
    
    # Query all transactions and join with customer info so we have names
    query = '''
        SELECT 
            t.customer_id, 
            t.transaction_date, 
            t.amount,
            c.name,
            c.email
        FROM transactions t
        JOIN customers c ON t.customer_id = c.id
    '''
    
    # Load the SQL data directly into a Pandas DataFrame
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    # If there are no transactions in the database, return an empty DataFrame
    if df.empty:
        return pd.DataFrame()
        
    # Ensure transaction_date is treated as a datetime object, not a string
    df['transaction_date'] = pd.to_datetime(df['transaction_date'])
    
    # To calculate 'Recency' (days since last purchase), we need a reference point for "Today".
    # For a realistic model, we use the date of the most recent transaction in the DB plus 1 day.
    current_date = df['transaction_date'].max() + pd.Timedelta(days=1)
    
    # Group the data by customer to aggregate their metrics
    rfm = df.groupby(['customer_id', 'name', 'email']).agg({
        'transaction_date': lambda x: (current_date - x.max()).days, # Recency: Days since their max (most recent) date
        'customer_id': 'count',                                      # Frequency: Total number of transactions
        'amount': 'sum'                                              # Monetary: Total money spent
    })
    
    # Rename columns to their proper ML feature names
    rfm.rename(columns={
        'transaction_date': 'Recency',
        'customer_id': 'Frequency',
        'amount': 'Monetary'
    }, inplace=True)
    
    # Reset the index so customer_id, name, and email become regular columns instead of index keys
    rfm.reset_index(inplace=True)
    
    return rfm

# If this file is run directly in terminal, test the calculation and print it out
if __name__ == '__main__':
    data = get_rfm_data()
    if data is not None and not data.empty:
        print("RFM Calculation Successful! Here is a preview of the data:")
        print(data.head())
    else:
        print("No transaction data available. Please add some transactions via the web app first.")
