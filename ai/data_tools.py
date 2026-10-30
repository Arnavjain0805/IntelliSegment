import sqlite3
import os
import sys

# Ensure root directory is accessible for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import database as db
from ml.segmentation import get_segmentation_overview

def get_company_kpis():
    """Extract real-time core KPIs from SQLite database safely."""
    conn = db.get_db_connection()
    total_customers = conn.execute('SELECT COUNT(*) FROM customers').fetchone()[0] or 0
    total_revenue = conn.execute('SELECT COALESCE(SUM(amount), 0) FROM transactions').fetchone()[0] or 0.0
    total_transactions = conn.execute('SELECT COUNT(*) FROM transactions').fetchone()[0] or 0
    avg_order_value = (total_revenue / total_transactions) if total_transactions > 0 else 0.0
    conn.close()
    
    return {
        "total_customers": total_customers,
        "total_revenue": round(float(total_revenue), 2),
        "total_transactions": total_transactions,
        "avg_order_value": round(float(avg_order_value), 2)
    }

def get_segments_context():
    """Extract current ML cluster segments, revenue share, and action plans."""
    df, summary, score, message = get_segmentation_overview()
    return {
        "silhouette_score": score,
        "status_message": message,
        "segments": summary if summary else []
    }

def get_customer_summary(identifier):
    """
    Safely look up customer by ID, name, or email using parameterized query.
    Returns customer details, segment, and recent purchases.
    """
    conn = db.get_db_connection()
    if isinstance(identifier, int) or (isinstance(identifier, str) and identifier.isdigit()):
        customer = conn.execute('SELECT * FROM customers WHERE id = ?', (int(identifier),)).fetchone()
    else:
        customer = conn.execute(
            'SELECT * FROM customers WHERE LOWER(name) LIKE ? OR LOWER(email) LIKE ? LIMIT 1',
            (f"%{str(identifier).lower()}%", f"%{str(identifier).lower()}%")
        ).fetchone()
    
    if not customer:
        conn.close()
        return None
        
    transactions = conn.execute(
        'SELECT transaction_date, amount, category FROM transactions WHERE customer_id = ? ORDER BY transaction_date DESC',
        (customer['id'],)
    ).fetchall()
    conn.close()
    
    trans_list = [dict(t) for t in transactions]
    total_spent = sum(t['amount'] for t in trans_list)
    
    # Check segment and RFM metrics from ML model
    df, summary, score, message = get_segmentation_overview()
    segment_name = "New / Unassigned"
    recency = 0
    frequency = len(trans_list)
    if df is not None and not df.empty:
        cust_row = df[df['customer_id'] == customer['id']]
        if not cust_row.empty:
            segment_name = cust_row.iloc[0]['Segment']
            recency = int(cust_row.iloc[0]['Recency'])
            frequency = int(cust_row.iloc[0]['Frequency'])
            
    churn_info = calculate_churn_risk(recency, frequency)
    
    return {
        "id": customer['id'],
        "name": customer['name'],
        "email": customer['email'],
        "country": customer['country'],
        "segment": segment_name,
        "total_spent": round(total_spent, 2),
        "transaction_count": len(trans_list),
        "recency": recency,
        "frequency": frequency,
        "churn_risk": churn_info,
        "transactions": trans_list
    }

def calculate_churn_risk(recency, frequency):
    """
    Computes a deterministic, factual churn probability score (0-100%)
    based on customer RFM behavior.
    """
    # Special handling for leads / customers with no purchase history
    if frequency == 0:
        return {
            "score": 50,
            "level": "New Lead",
            "badge_color": "secondary",
            "recency_days": 0,
            "frequency_orders": 0,
            "recency_status": "No transactions recorded yet",
            "frequency_status": "Prospect / New Lead",
            "recommended_action": "Send welcome email sequence with first-purchase incentive or discount code."
        }

    # 1. Base risk from recency (days since last purchase)
    if recency <= 7:
        base_risk = 15
        recency_status = "Very Active (Purchased within 7 days)"
    elif recency <= 30:
        base_risk = 35
        recency_status = "Moderately Active (Purchased within past month)"
    elif recency <= 60:
        base_risk = 60
        recency_status = "Cooling Down (No purchase for 30-60 days)"
    else:
        base_risk = 85
        recency_status = "Dormant / High Recency (Over 60 days inactive)"
        
    # 2. Adjustment for purchase frequency
    if frequency <= 1:
        freq_penalty = 15  # One-time buyers have higher risk of drop-off
        freq_status = "One-time buyer (No repeat order history)"
    elif frequency <= 3:
        freq_penalty = -5
        freq_status = "Emerging repeat customer"
    else:
        freq_penalty = -20 # Loyal repeat buyer
        freq_status = "Established loyal customer"
        
    risk_score = max(5, min(95, base_risk + freq_penalty))
    
    if risk_score < 35:
        level = "Low Risk"
        badge_color = "success"
        action = "Maintain loyalty through regular updates and VIP perks."
    elif risk_score <= 65:
        level = "Medium Risk"
        badge_color = "warning"
        action = "Send targeted re-engagement email with a 10% discount to prompt a repeat order."
    else:
        level = "High Risk"
        badge_color = "danger"
        action = "Urgent win-back campaign needed: Special voucher, direct personal check-in or survey."
        
    return {
        "score": risk_score,
        "level": level,
        "badge_color": badge_color,
        "recency_days": recency,
        "frequency_orders": frequency,
        "recency_status": recency_status,
        "frequency_status": freq_status,
        "recommended_action": action
    }

def get_all_customers_overview():
    """Returns high-level summary of all customers with their spending, segment, and churn risk."""
    df, summary, score, message = get_segmentation_overview()
    if df is not None and not df.empty:
        records = df[['customer_id', 'name', 'email', 'Recency', 'Frequency', 'Monetary', 'Segment']].to_dict(orient='records')
        for r in records:
            r['churn_risk'] = calculate_churn_risk(int(r['Recency']), int(r['Frequency']))
        return records
    return []
