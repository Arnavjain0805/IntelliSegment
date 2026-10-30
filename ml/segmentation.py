import pandas as pd
import numpy as np
import sys
import os

# Ensure the root project directory is in python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml.clustering import perform_clustering


def map_clusters_to_segments(clustered_df):
    """
    Dynamically maps raw ML cluster integers (0, 1, 2) to descriptive,
    human-friendly business segment names based on RFM averages.
    
    Returns:
        tuple: (enriched_df, segment_summary_list)
    """
    if clustered_df is None or clustered_df.empty:
        return None, []
        
    total_customers = len(clustered_df)
    
    # Calculate group averages for each cluster
    cluster_stats = clustered_df.groupby('Cluster').agg({
        'Monetary': ['mean', 'sum'],
        'Frequency': 'mean',
        'Recency': 'mean',
        'customer_id': 'count'
    })
    
    # Flatten multi-level column names
    cluster_stats.columns = ['Avg_Monetary', 'Total_Monetary', 'Avg_Frequency', 'Avg_Recency', 'Count']
    cluster_stats = cluster_stats.reset_index()
    
    # Sort clusters by Average Monetary value in descending order
    cluster_stats = cluster_stats.sort_values(by='Avg_Monetary', ascending=False).reset_index(drop=True)
    n_clusters = len(cluster_stats)
    
    # Define business segment definitions based on rank and relative values
    label_map = {}
    action_map = {}
    color_map = {}
    
    if n_clusters == 2:
        # Highest spending cluster
        label_map[cluster_stats.loc[0, 'Cluster']] = "High-Value Customers"
        action_map[cluster_stats.loc[0, 'Cluster']] = "VIP loyalty rewards, exclusive previews & personalized service."
        color_map[cluster_stats.loc[0, 'Cluster']] = "success"
        
        # Lower spending cluster
        label_map[cluster_stats.loc[1, 'Cluster']] = "Standard / Growth Opportunities"
        action_map[cluster_stats.loc[1, 'Cluster']] = "Upselling, targeted discounts & engagement emails."
        color_map[cluster_stats.loc[1, 'Cluster']] = "primary"
        
    elif n_clusters == 3:
        # Top cluster
        label_map[cluster_stats.loc[0, 'Cluster']] = "High-Value Champions"
        action_map[cluster_stats.loc[0, 'Cluster']] = "VIP rewards, dedicated support & early product access."
        color_map[cluster_stats.loc[0, 'Cluster']] = "success"
        
        # Middle cluster
        label_map[cluster_stats.loc[1, 'Cluster']] = "Moderate / Regular Customers"
        action_map[cluster_stats.loc[1, 'Cluster']] = "Cross-selling campaigns & product recommendations."
        color_map[cluster_stats.loc[1, 'Cluster']] = "info"
        
        # Lower cluster
        label_map[cluster_stats.loc[2, 'Cluster']] = "At-Risk / Low-Value Customers"
        action_map[cluster_stats.loc[2, 'Cluster']] = "Win-back promotions, re-engagement offers & surveys."
        color_map[cluster_stats.loc[2, 'Cluster']] = "warning"
        
    else:
        # Dynamic fallback for 4+ clusters
        for i, row in cluster_stats.iterrows():
            c_id = row['Cluster']
            if i == 0:
                label_map[c_id] = "High-Value Champions"
                action_map[c_id] = "VIP rewards & personalized executive outreach."
                color_map[c_id] = "success"
            elif i == n_clusters - 1:
                label_map[c_id] = "At-Risk / Low-Value"
                action_map[c_id] = "Win-back discounts & re-activation offers."
                color_map[c_id] = "warning"
            else:
                label_map[c_id] = f"Regular Segment Tier {i}"
                action_map[c_id] = "Nurture with relevant product recommendations."
                color_map[c_id] = "primary"

    # Map labels to the main customer dataframe
    clustered_df['Segment'] = clustered_df['Cluster'].map(label_map)
    clustered_df['Action'] = clustered_df['Cluster'].map(action_map)
    clustered_df['BadgeColor'] = clustered_df['Cluster'].map(color_map)
    
    # Build clean summary list for business dashboard & reporting
    summary = []
    for _, row in cluster_stats.iterrows():
        c_id = row['Cluster']
        count = int(row['Count'])
        pct = round((count / total_customers) * 100, 1)
        summary.append({
            'cluster_id': int(c_id),
            'segment_name': label_map[c_id],
            'customer_count': count,
            'percentage': pct,
            'avg_recency': round(float(row['Avg_Recency']), 1),
            'avg_frequency': round(float(row['Avg_Frequency']), 1),
            'avg_monetary': round(float(row['Avg_Monetary']), 2),
            'total_revenue': round(float(row['Total_Monetary']), 2),
            'recommended_action': action_map[c_id],
            'badge_color': color_map[c_id]
        })
        
    # Ensure customers are arranged in descending order of customer_id
    clustered_df = clustered_df.sort_values(by='customer_id', ascending=False).reset_index(drop=True)
    return clustered_df, summary


def get_segmentation_overview():
    """
    High-level orchestrator: runs clustering and returns customer details,
    segment summaries, silhouette score, and any status messages.
    """
    df, silhouette_score, message = perform_clustering()
    if df is None:
        return None, [], silhouette_score, message
        
    enriched_df, summary = map_clusters_to_segments(df)
    return enriched_df, summary, silhouette_score, message


if __name__ == '__main__':
    print("Executing Phase 7: Segmentation Logic & Business Mapping...\n")
    df, summary, score, msg = get_segmentation_overview()
    if df is not None:
        print(f"Status: {msg}")
        print(f"Silhouette Score: {score}")
        print("\n=== BUSINESS SEGMENT DISTRIBUTION ===")
        for s in summary:
            print(f"- {s['segment_name']} [{s['badge_color'].upper()}]:")
            print(f"  Count: {s['customer_count']} ({s['percentage']}%)")
            print(f"  Avg Recency: {s['avg_recency']} days | Avg Freq: {s['avg_frequency']} | Avg Spend: ${s['avg_monetary']:,.2f}")
            print(f"  Total Segment Revenue: ${s['total_revenue']:,.2f}")
            print(f"  Recommended Strategy: {s['recommended_action']}\n")
            
        print("=== CUSTOMER SEGMENT ASSIGNMENTS ===")
        print(df[['name', 'Recency', 'Frequency', 'Monetary', 'Segment']])
    else:
        print(f"Error: {msg}")
