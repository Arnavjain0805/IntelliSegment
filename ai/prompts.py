"""
ai/prompts.py
System prompts, data science knowledge bases, and strict guardrails for the AI Business Assistant.
"""

SYSTEM_PROMPT = """
You are the IntelliSegment Business Intelligence Assistant, a specialized AI advisor integrated into the IntelliSegment Customer Segmentation System.

YOUR ROLE:
- Assist business owners, marketers, and analysts in understanding customer behavior, revenue streams, and segmentation metrics.
- Provide clear, actionable strategic advice based on RFM (Recency, Frequency, Monetary) data.
- Explain data science and machine learning concepts (such as Silhouette Score and Hierarchical Clustering) in simple, accessible business terms.

STRICT SAFEGUARDS & GUARDRAILS:
1. FACTUALITY ONLY: Never hallucinate or invent customer names, dollar amounts, transaction dates, or segment names that are not in the provided database context.
2. NO RAW SQL: Never generate, execute, or ask for raw SQL queries. All data access must pass through safe predefined backend data tools.
3. CONTEXT GROUNDING: If the user asks a question about customer data that is not in the provided records, reply politely: "According to current records, that data is not available."
4. PROFESSIONAL TONE: Be concise, structured, professional, and encouraging. Use bullet points and bold formatting for key metrics.
"""

# Ground truth explanations for ML concepts to guarantee zero hallucination
CONCEPT_EXPLANATIONS = {
    "silhouette_score": (
        "The **Silhouette Score** measures how well-separated and cohesive our customer clusters are. "
        "It ranges from **-1 to +1**:\n"
        "- **+0.5 to +1.0**: Strong clustering (customers within each segment are very similar and distinct from other groups).\n"
        "- **+0.25 to +0.5**: Reasonable / moderate clustering structure.\n"
        "- **Below +0.25**: Weak or overlapping clusters.\n"
        "- **Negative (< 0)**: Customers might be assigned to the wrong group.\n"
        "In our application, we use the Silhouette Score as the sole metric to evaluate clustering quality."
    ),
    "rfm": (
        "**RFM Analysis** is an industry-standard behavioral marketing model that evaluates customers across three dimensions:\n"
        "1. **Recency (R)**: Days since the customer's last purchase. (Lower is better — indicates an active buyer).\n"
        "2. **Frequency (F)**: Total number of transactions. (Higher is better — indicates brand loyalty).\n"
        "3. **Monetary (M)**: Total dollars spent. (Higher is better — indicates revenue value).\n"
        "RFM transforms raw purchase logs into standardized numerical features for machine learning."
    ),
    "hierarchical_clustering": (
        "**Hierarchical Agglomerative Clustering** is an unsupervised machine learning algorithm that groups customers "
        "by similarity. Unlike K-Means, which guesses starting points randomly, Hierarchical Clustering starts with every "
        "customer as their own individual cluster and iteratively pairs the most similar customers together in a tree-like "
        "structure (dendrogram) using **Ward's linkage** to minimize internal group variance."
    ),
    "feature_scaling": (
        "**Feature Scaling (StandardScaler)** normalizes RFM metrics so they have equal mathematical weight. "
        "For example, a customer's spending might be $10,000 while their purchase frequency is 2. Without scaling, "
        "the model would assume Monetary value is 5,000 times more important than Frequency. Scaling puts all features "
        "on a balanced bell-curve with a mean of 0 and variance of 1."
    )
}

def build_context_prompt(user_query, kpi_data, segment_data, customer_data=None, all_customers=None):
    """
    Constructs a structured prompt bundling real database context with the user's inquiry.
    """
    prompt = f"USER QUESTION: {user_query}\n\n"
    prompt += "=== FACTUAL DATABASE CONTEXT ===\n"
    prompt += f"- Total Customers: {kpi_data.get('total_customers', 0)}\n"
    prompt += f"- Total Revenue: ${kpi_data.get('total_revenue', 0.0):,.2f}\n"
    prompt += f"- Total Transactions: {kpi_data.get('total_transactions', 0)}\n"
    prompt += f"- Average Order Value: ${kpi_data.get('avg_order_value', 0.0):,.2f}\n"
    
    if segment_data.get('silhouette_score') is not None:
        prompt += f"- Clustering Silhouette Score: {segment_data.get('silhouette_score')}\n"
        
    segments = segment_data.get('segments', [])
    if segments:
        prompt += "\n=== ACTIVE BUSINESS SEGMENTS ===\n"
        for s in segments:
            prompt += (
                f"* {s['segment_name']}: {s['customer_count']} customer(s) ({s['percentage']}%), "
                f"Total Revenue: ${s['total_revenue']:,.2f}, Avg Spend: ${s['avg_monetary']:,.2f}, "
                f"Strategy: {s['recommended_action']}\n"
            )

    if all_customers:
        prompt += "\n=== CUSTOMER ROSTER & SPENDING ===\n"
        # Sort by monetary descending
        sorted_custs = sorted(all_customers, key=lambda x: x.get('Monetary', 0), reverse=True)
        for c in sorted_custs[:10]:
            churn = c.get('churn_risk', {})
            prompt += f"- {c['name']} (ID: {c['customer_id']}, {c['email']}): Spent ${c['Monetary']:,.2f}, Orders: {c['Frequency']}, Recency: {c['Recency']}d, Segment: {c['Segment']}, Churn Risk: {churn.get('level', 'N/A')} ({churn.get('score', 0)}%)\n"
            
    if customer_data:
        prompt += f"\n=== SPECIFIC CUSTOMER PROFILE ({customer_data['name']}) ===\n"
        prompt += f"- Customer ID: {customer_data['id']}\n"
        prompt += f"- Email: {customer_data['email']}\n"
        prompt += f"- Country: {customer_data.get('country') or 'N/A'}\n"
        prompt += f"- Segment: {customer_data['segment']}\n"
        prompt += f"- Total Spent: ${customer_data['total_spent']:,.2f}\n"
        prompt += f"- Orders: {customer_data['transaction_count']}\n"
        
        churn = customer_data.get('churn_risk')
        if churn:
            prompt += (
                f"- Churn Risk Assessment: {churn['level']} ({churn['score']}% probability)\n"
                f"  * Recency Factor: {churn['recency_status']}\n"
                f"  * Frequency Factor: {churn['frequency_status']}\n"
                f"  * Recommended Retention Action: {churn['recommended_action']}\n"
            )
            
        prompt += f"- Invoice Link: /customers/{customer_data['id']}/invoice\n"
        prompt += "- Recent Purchases:\n"
        for t in customer_data.get('transactions', [])[:5]:
            prompt += f"  * {t['transaction_date']} - ${t['amount']:,.2f} ({t['category']})\n"
            
    prompt += (
        "\nINSTRUCTIONS:\n"
        "- Answer the user's question using ONLY the facts above or the defined ML concepts.\n"
        "- If the user asks to generate, view, or check an invoice for a customer, provide the transaction summary and the link [View / Print Invoice](/customers/{id}/invoice).\n"
        "- If the user asks about churn or churn prediction, explain their churn risk score, factors, and retention advice.\n"
        "- Keep responses concise, professional, actionable, and formatted with markdown."
    )
    return prompt
