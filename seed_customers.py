"""
seed_customers.py
Populates the IntelliSegment database with 16 realistic, diverse customer profiles
and transaction histories to create rich behavioral clusters for ML analysis.
"""

import sys
import os

# Ensure project root is in sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import database as db

SAMPLE_CUSTOMERS = [
    # High-Value Champions (High spend, multiple orders, recent activity)
    {
        "name": "Sophia Martinez",
        "email": "sophia.martinez@gmail.com",
        "phone": "+1-555-0192",
        "country": "United States",
        "transactions": [
            ("2026-10-10", 2200.00, "Electronics"),
            ("2026-10-02", 1450.00, "Services"),
            ("2026-09-25", 850.00, "Clothing"),
            ("2026-09-15", 350.00, "Groceries")
        ]
    },
    {
        "name": "Liam Chen",
        "email": "liam.chen@techasia.io",
        "phone": "+65-6821-4432",
        "country": "Singapore",
        "transactions": [
            ("2026-10-12", 3400.00, "Electronics"),
            ("2026-09-28", 1950.00, "Electronics"),
            ("2026-09-12", 850.00, "Services")
        ]
    },
    {
        "name": "Emma Watson",
        "email": "emma.watson@londonretail.co.uk",
        "phone": "+44-20-7946-0912",
        "country": "United Kingdom",
        "transactions": [
            ("2026-10-11", 1200.00, "Clothing"),
            ("2026-10-04", 980.00, "Services"),
            ("2026-09-22", 720.00, "Clothing"),
            ("2026-09-14", 640.00, "Electronics"),
            ("2026-09-01", 360.00, "Groceries")
        ]
    },

    # Moderate / Regular Customers (Consistent recurring orders, mid-tier spending)
    {
        "name": "Marcus Johnson",
        "email": "marcus.j@outlook.com",
        "phone": "+1-416-555-0188",
        "country": "Canada",
        "transactions": [
            ("2026-10-08", 340.00, "Groceries"),
            ("2026-09-24", 260.00, "Clothing"),
            ("2026-09-10", 180.00, "Groceries")
        ]
    },
    {
        "name": "Priya Sharma",
        "email": "priya.sharma92@yahoo.com",
        "phone": "+91-98200-11234",
        "country": "India",
        "transactions": [
            ("2026-10-09", 420.00, "Clothing"),
            ("2026-09-27", 290.00, "Groceries"),
            ("2026-09-18", 150.00, "Services"),
            ("2026-09-05", 120.00, "Clothing")
        ]
    },
    {
        "name": "Lucas Silva",
        "email": "lucas.silva@uol.com.br",
        "phone": "+55-11-98765-4321",
        "country": "Brazil",
        "transactions": [
            ("2026-10-05", 480.00, "Electronics"),
            ("2026-09-16", 160.00, "Clothing")
        ]
    },
    {
        "name": "Chloe Dubois",
        "email": "chloe.dubois@orange.fr",
        "phone": "+33-1-4268-5500",
        "country": "France",
        "transactions": [
            ("2026-10-07", 520.00, "Services"),
            ("2026-09-21", 210.00, "Groceries"),
            ("2026-09-08", 120.00, "Other")
        ]
    },
    {
        "name": "Daniel Kim",
        "email": "daniel.kim@seoultech.kr",
        "phone": "+82-2-555-0144",
        "country": "South Korea",
        "transactions": [
            ("2026-10-06", 650.00, "Electronics"),
            ("2026-09-20", 320.00, "Clothing"),
            ("2026-09-03", 180.00, "Services")
        ]
    },
    {
        "name": "Elena Rossi",
        "email": "elena.rossi@virgilio.it",
        "phone": "+39-06-6987-1234",
        "country": "Italy",
        "transactions": [
            ("2026-10-04", 380.00, "Groceries"),
            ("2026-09-15", 180.00, "Groceries")
        ]
    },

    # Standard / Growth Opportunities (Recent or moderate recency, single/double purchase)
    {
        "name": "Oliver Smith",
        "email": "oliver.smith@sydneybiz.com.au",
        "phone": "+61-2-9876-5432",
        "country": "Australia",
        "transactions": [
            ("2026-10-03", 210.00, "Clothing")
        ]
    },
    {
        "name": "Maya Patel",
        "email": "maya.patel@rediffmail.com",
        "phone": "+91-99400-88765",
        "country": "India",
        "transactions": [
            ("2026-10-01", 190.00, "Groceries"),
            ("2026-09-11", 130.00, "Clothing")
        ]
    },
    {
        "name": "Noah Williams",
        "email": "noah.williams@austinmail.com",
        "phone": "+1-512-555-0177",
        "country": "United States",
        "transactions": [
            ("2026-09-29", 180.00, "Services")
        ]
    },
    {
        "name": "Sarah Miller",
        "email": "sarah.miller@berlinmail.de",
        "phone": "+49-30-555-0199",
        "country": "Germany",
        "transactions": [
            ("2026-09-26", 290.00, "Electronics")
        ]
    },

    # At-Risk / Dormant Customers (High recency, inactive since August/early September)
    {
        "name": "Alexander Wright",
        "email": "alexander.wright@manchester.co.uk",
        "phone": "+44-161-496-0123",
        "country": "United Kingdom",
        "transactions": [
            ("2026-08-15", 95.00, "Groceries")
        ]
    },
    {
        "name": "Jessica Taylor",
        "email": "jessica.taylor@chicago.edu",
        "phone": "+1-312-555-0145",
        "country": "United States",
        "transactions": [
            ("2026-08-20", 60.00, "Clothing")
        ]
    },
    {
        "name": "David Brown",
        "email": "david.brown@vancouver.ca",
        "phone": "+1-604-555-0166",
        "country": "Canada",
        "transactions": [
            ("2026-08-28", 120.00, "Other")
        ]
    }
]

def seed_sample_records():
    """Insert the sample customers and their transactions into the SQLite database."""
    conn = db.get_db_connection()
    added_customers = 0
    added_transactions = 0

    for item in SAMPLE_CUSTOMERS:
        # Check if customer already exists by email
        existing = conn.execute('SELECT id FROM customers WHERE email = ?', (item["email"],)).fetchone()
        if existing:
            cust_id = existing["id"]
        else:
            success, cust_id = db.insert_customer(item["name"], item["email"], item["phone"], item["country"])
            if success:
                added_customers += 1
            else:
                continue

        # Add transactions for this customer
        for date_str, amount, cat in item["transactions"]:
            # Check if this exact transaction already exists
            dup = conn.execute(
                'SELECT id FROM transactions WHERE customer_id = ? AND transaction_date = ? AND amount = ?',
                (cust_id, date_str, amount)
            ).fetchone()
            if not dup:
                success, _ = db.insert_transaction(cust_id, date_str, amount, cat)
                if success:
                    added_transactions += 1

    conn.close()
    print(f"Seeding completed successfully! Added {added_customers} new customer(s) and {added_transactions} transaction(s).")

if __name__ == '__main__':
    seed_sample_records()
