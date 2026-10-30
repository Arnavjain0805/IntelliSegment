import os
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, request, redirect, url_for, flash, abort
import database as db
import sqlite3

app = Flask(__name__)
# The secret key is loaded from environment or defaults safely for sessions
app.secret_key = os.environ.get('SECRET_KEY', 'intellisegment_secret_key')

# Initialize DB on startup
db.init_db()

import csv
import io
from flask import Response

import re
import datetime

EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')

def validate_customer_payload(name, email, phone, country):
    """Strict backend validation for customer inputs."""
    if not name or len(name.strip()) < 2:
        return False, "Customer Name must be at least 2 characters long."
    if len(name.strip()) > 60:
        return False, "Customer Name cannot exceed 60 characters."
    if not email or len(email.strip()) > 100 or not EMAIL_REGEX.match(email.strip()):
        return False, "Please enter a valid email address (e.g. name@example.com)."
    if phone and len(phone.strip()) > 25:
        return False, "Phone number cannot exceed 25 characters."
    if country and len(country.strip()) > 50:
        return False, "Country name cannot exceed 50 characters."
    return True, None

def validate_transaction_payload(date_str, amount_str, category):
    """Strict backend validation for transaction inputs."""
    if not date_str or not date_str.strip():
        return False, "Transaction date is required."
    try:
        t_date = datetime.datetime.strptime(date_str.strip(), '%Y-%m-%d').date()
        today = datetime.date.today()
        if t_date > today:
            return False, "Transaction date cannot be set in the future."
    except ValueError:
        return False, "Transaction date must be in YYYY-MM-DD format."
        
    if not amount_str or not amount_str.strip():
        return False, "Transaction amount is required."
    try:
        amount_float = float(amount_str.strip())
        if amount_float <= 0:
            return False, "Transaction amount must be greater than $0.00."
        if amount_float > 1000000:
            return False, "Transaction amount cannot exceed $1,000,000.00."
    except ValueError:
        return False, "Amount must be a valid positive dollar number."
        
    valid_categories = {"Electronics", "Clothing", "Groceries", "Services", "Other"}
    if category and category not in valid_categories:
        return False, f"Invalid category. Must be one of: {', '.join(sorted(valid_categories))}."
        
    return True, round(amount_float, 2)

@app.route('/')
def index():
    """Executive Dashboard with KPIs, visual analytics, and segment distributions."""
    conn = db.get_db_connection()
    
    # 1. Fetch Core Business KPIs
    total_customers = conn.execute('SELECT COUNT(*) FROM customers').fetchone()[0] or 0
    total_revenue = conn.execute('SELECT COALESCE(SUM(amount), 0) FROM transactions').fetchone()[0] or 0.0
    total_transactions = conn.execute('SELECT COUNT(*) FROM transactions').fetchone()[0] or 0
    avg_order_value = (total_revenue / total_transactions) if total_transactions > 0 else 0.0
    
    # Recent Transactions for preview
    recent_transactions = conn.execute('''
        SELECT t.id, t.transaction_date, t.amount, t.category, c.name as customer_name, c.id as customer_id
        FROM transactions t
        JOIN customers c ON t.customer_id = c.id
        ORDER BY t.transaction_date DESC, t.id DESC
        LIMIT 5
    ''').fetchall()
    
    conn.close()
    
    # 2. Fetch Machine Learning Segmentation & Graph Data
    import json
    from ml.segmentation import get_segmentation_overview
    df, summary, score, message = get_segmentation_overview()
    
    # Prepare serializable data for Chart.js
    chart_labels = [s['segment_name'] for s in summary] if summary else []
    chart_counts = [s['customer_count'] for s in summary] if summary else []
    chart_revenues = [s['total_revenue'] for s in summary] if summary else []
    
    color_palette = {
        'success': '#198754',
        'primary': '#0d6efd',
        'warning': '#ffc107',
        'info': '#0dcaf0',
        'danger': '#dc3545'
    }
    chart_colors = [color_palette.get(s['badge_color'], '#6c757d') for s in summary] if summary else []
    
    return render_template(
        'dashboard.html',
        total_customers=total_customers,
        total_revenue=total_revenue,
        total_transactions=total_transactions,
        avg_order_value=avg_order_value,
        recent_transactions=recent_transactions,
        summary=summary,
        silhouette_score=score,
        chart_labels=json.dumps(chart_labels),
        chart_counts=json.dumps(chart_counts),
        chart_revenues=json.dumps(chart_revenues),
        chart_colors=json.dumps(chart_colors)
    )

@app.route('/customers', methods=['GET'])
def customers():
    """Display a list of all customers, with optional search functionality, ordered by ID descending."""
    search_query = request.args.get('search', '').strip()
    conn = db.get_db_connection()
    
    if search_query:
        # Search by name or email using parameterized LIKE query, ordered by ID descending
        customers = conn.execute(
            'SELECT * FROM customers WHERE name LIKE ? OR email LIKE ? ORDER BY id DESC',
            (f'%{search_query}%', f'%{search_query}%')
        ).fetchall()
    else:
        # Fetch all customers ordered by ID descending (newest customer at the top)
        customers = conn.execute('SELECT * FROM customers ORDER BY id DESC').fetchall()
        
    conn.close()
    return render_template('customers.html', customers=customers, search_query=search_query)

@app.route('/customers/add', methods=['GET', 'POST'])
def add_customer():
    """Handle adding a new customer via form submission with dual-sided validation."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        country = request.form.get('country', '').strip()
        
        # Strict Backend Validation
        is_valid, err_msg = validate_customer_payload(name, email, phone, country)
        if not is_valid:
            flash(err_msg, 'danger')
            return render_template('add_customer.html', name=name, email=email, phone=phone, country=country)
            
        success, message_or_id = db.insert_customer(name, email, phone, country)
        if success:
            flash('Customer added successfully!', 'success')
            return redirect(url_for('customers'))
        else:
            flash(message_or_id, 'danger')
            return render_template('add_customer.html', name=name, email=email, phone=phone, country=country)
            
    return render_template('add_customer.html')

@app.route('/customers/<int:id>')
def customer_details(id):
    """View details, RFM metrics, churn risk, and transaction history for a specific customer."""
    from ai.data_tools import get_customer_summary
    conn = db.get_db_connection()
    customer = conn.execute('SELECT * FROM customers WHERE id = ?', (id,)).fetchone()
    
    if not customer:
        conn.close()
        abort(404)
    
    transactions = conn.execute(
        'SELECT * FROM transactions WHERE customer_id = ? ORDER BY transaction_date DESC', 
        (id,)
    ).fetchall()
    conn.close()
    
    summary = get_customer_summary(customer['id'])
    churn_risk = summary.get('churn_risk') if summary else None
    segment_name = summary.get('segment') if summary else 'Standard'
    total_spent = summary.get('total_spent', 0.0) if summary else 0.0
    
    return render_template(
        'customer_details.html',
        customer=customer,
        transactions=transactions,
        churn_risk=churn_risk,
        segment_name=segment_name,
        total_spent=total_spent
    )

@app.route('/customers/<int:id>/invoice')
def customer_invoice(id):
    """Generate printable HTML and PDF-ready invoice for a customer based on transactions."""
    import datetime
    from ai.data_tools import get_customer_summary
    
    conn = db.get_db_connection()
    customer = conn.execute('SELECT * FROM customers WHERE id = ?', (id,)).fetchone()
    if not customer:
        conn.close()
        abort(404)
        
    transactions = conn.execute(
        'SELECT * FROM transactions WHERE customer_id = ? ORDER BY transaction_date ASC, id ASC',
        (id,)
    ).fetchall()
    conn.close()
    
    trans_list = [dict(t) for t in transactions]
    total_amount = sum(t['amount'] for t in trans_list)
    summary_data = get_customer_summary(customer['id'])
    
    today = datetime.date.today().strftime('%B %d, %Y')
    invoice_number = f"INV-{id:04d}-{datetime.date.today().year}"
    
    return render_template(
        'customer_invoice.html',
        customer=customer,
        transactions=trans_list,
        total_amount=total_amount,
        today=today,
        invoice_number=invoice_number,
        summary=summary_data
    )

@app.route('/customers/<int:id>/edit', methods=['GET', 'POST'])
def edit_customer(id):
    """Edit an existing customer's information with validation."""
    conn = db.get_db_connection()
    customer = conn.execute('SELECT * FROM customers WHERE id = ?', (id,)).fetchone()
    
    if not customer:
        conn.close()
        abort(404)

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        country = request.form.get('country', '').strip()
        
        is_valid, err_msg = validate_customer_payload(name, email, phone, country)
        if not is_valid:
            flash(err_msg, 'danger')
            conn.close()
            return render_template('edit_customer.html', customer={'id': id, 'name': name, 'email': email, 'phone': phone, 'country': country})
            
        try:
            conn.execute(
                'UPDATE customers SET name = ?, email = ?, phone = ?, country = ? WHERE id = ?',
                (name, email, phone, country, id)
            )
            conn.commit()
            flash('Customer updated successfully!', 'success')
            conn.close()
            return redirect(url_for('customers'))
        except sqlite3.IntegrityError:
            flash('Email already exists for another customer.', 'danger')
            conn.close()
            return render_template('edit_customer.html', customer={'id': id, 'name': name, 'email': email, 'phone': phone, 'country': country})
            
    conn.close()
    return render_template('edit_customer.html', customer=customer)

@app.route('/customers/<int:id>/delete', methods=['POST'])
def delete_customer(id):
    """Delete a customer (and cascade their transactions)."""
    conn = db.get_db_connection()
    conn.execute('DELETE FROM customers WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash('Customer deleted successfully!', 'success')
    return redirect(url_for('customers'))

@app.route('/customers/<int:id>/transactions/add', methods=['GET', 'POST'])
def add_transaction(id):
    """Add a new transaction for a specific customer with strict validation."""
    conn = db.get_db_connection()
    customer = conn.execute('SELECT * FROM customers WHERE id = ?', (id,)).fetchone()
    
    if not customer:
        conn.close()
        abort(404)
        
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    if request.method == 'POST':
        transaction_date = request.form.get('transaction_date', '').strip()
        amount = request.form.get('amount', '').strip()
        category = request.form.get('category', '').strip()
        
        is_valid, result = validate_transaction_payload(transaction_date, amount, category)
        if not is_valid:
            flash(result, 'danger')
            conn.close()
            return render_template('add_transaction.html', customer=customer, today=today_str, transaction_date=transaction_date, amount=amount, category=category)
            
        amount_float = result
        success, message = db.insert_transaction(id, transaction_date, amount_float, category)
        conn.close()
        
        if success:
            flash('Transaction added successfully!', 'success')
            return redirect(url_for('customer_details', id=id))
        else:
            flash(message, 'danger')
            return render_template('add_transaction.html', customer=customer, today=today_str, transaction_date=transaction_date, amount=amount, category=category)
            
    conn.close()
    return render_template('add_transaction.html', customer=customer, today=today_str)

@app.route('/transactions/<int:id>/delete', methods=['POST'])
def delete_transaction(id):
    """Delete a transaction by ID."""
    conn = db.get_db_connection()
    transaction = conn.execute('SELECT customer_id FROM transactions WHERE id = ?', (id,)).fetchone()
    if transaction:
        customer_id = transaction['customer_id']
        conn.execute('DELETE FROM transactions WHERE id = ?', (id,))
        conn.commit()
        flash('Transaction deleted.', 'success')
    else:
        flash('Transaction not found.', 'danger')
        customer_id = None
    conn.close()
    
    if customer_id:
        return redirect(url_for('customer_details', id=customer_id))
    return redirect(url_for('customers'))

@app.route('/segmentation')
def segmentation():
    """Display customer segmentation results, business labels, and distributions in descending ID order."""
    from ml.segmentation import get_segmentation_overview
    df, summary, score, message = get_segmentation_overview()
    
    customers_list = []
    if df is not None and not df.empty:
        # Sort customers strictly by customer_id descending
        df = df.sort_values(by='customer_id', ascending=False)
        customers_list = df.to_dict(orient='records')
        
    return render_template(
        'segmentation.html',
        customers=customers_list,
        summary=summary,
        silhouette_score=score,
        status_message=message
    )

@app.route('/customers/export')
def export_customers_csv():
    """Export all customers and their lifetime metrics to CSV in descending ID order."""
    conn = db.get_db_connection()
    customers = conn.execute('SELECT * FROM customers ORDER BY id DESC').fetchall()
    conn.close()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Customer ID', 'Name', 'Email', 'Phone', 'Country', 'Registered At'])
    for c in customers:
        writer.writerow([c['id'], c['name'], c['email'], c['phone'] or '', c['country'] or '', c['created_at']])
        
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=customers_export.csv"}
    )

@app.route('/segmentation/export')
def export_segmentation_csv():
    """Export customer segmentation analysis and RFM breakdown to CSV in descending ID order."""
    from ml.segmentation import get_segmentation_overview
    df, summary, score, message = get_segmentation_overview()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Customer ID', 'Name', 'Email', 'Recency (Days)', 'Frequency (Orders)', 'Monetary ($)', 'Segment', 'Action Strategy'])
    
    if df is not None and not df.empty:
        # Sort customers strictly in descending order of customer_id
        df = df.sort_values(by='customer_id', ascending=False)
        for _, row in df.iterrows():
            writer.writerow([
                row['customer_id'],
                row['name'],
                row['email'],
                row['Recency'],
                row['Frequency'],
                f"{row['Monetary']:.2f}",
                row['Segment'],
                row['Action']
            ])
            
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=segmentation_clusters_export.csv"}
    )

@app.route('/assistant')
def assistant():
    """AI Business Assistant chatbot interface."""
    from ai.assistant import get_active_api_key
    provider, key = get_active_api_key()
    return render_template(
        'assistant.html',
        has_key=bool(key),
        provider=provider
    )

@app.route('/api/chat', methods=['POST'])
def api_chat():
    """API endpoint to receive chat messages and return genuine generative AI responses."""
    data = request.get_json() or {}
    user_message = data.get('message', '').strip()
    
    from ai.assistant import process_chat_message
    reply, model_name = process_chat_message(user_message)
    return {'reply': reply, 'model': model_name}

# --- Error Handlers ---
@app.errorhandler(400)
def bad_request_error(e):
    """Handle 400 Bad Request error."""
    return render_template(
        'error.html',
        error_code=400,
        error_title="Bad Request",
        error_message="The request could not be processed due to invalid or malformed data.",
        color_class="warning"
    ), 400

@app.errorhandler(404)
def not_found_error(e):
    """Handle 404 Not Found error."""
    return render_template(
        'error.html',
        error_code=404,
        error_title="Page or Resource Not Found",
        error_message="The customer record, page, or resource you are looking for does not exist or may have been moved.",
        color_class="danger"
    ), 404

@app.errorhandler(500)
def internal_server_error(e):
    """Handle 500 Internal Server Error."""
    return render_template(
        'error.html',
        error_code=500,
        error_title="Internal Server Error",
        error_message="An unexpected server error occurred while processing your request. Please try again later.",
        color_class="secondary"
    ), 500

if __name__ == '__main__':
    # Run the Flask app on default port 5000 in debug mode
    app.run(debug=True)
