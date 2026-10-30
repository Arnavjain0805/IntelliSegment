import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import silhouette_score
import sys
import os

# Ensure the root project directory is in python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml.rfm import get_rfm_data


def calculate_silhouette(scaled_features, cluster_labels):
    """
    Calculates the Silhouette Score using Scikit-Learn.
    
    The Silhouette Score measures how similar a customer is to their own cluster
    compared to other clusters.
    - Score ranges from -1 to +1:
      * +1 : Perfect separation (clusters are dense and well separated).
      *  0 : Overlapping clusters.
      * -1 : Incorrect clustering (points assigned to wrong cluster).
      
    Edge-Case Handling:
    - Silhouette score requires at least 2 clusters (n_clusters >= 2).
    - Silhouette score requires fewer clusters than samples (n_clusters < n_samples).
    """
    n_samples = len(scaled_features)
    unique_labels = set(cluster_labels)
    n_unique = len(unique_labels)
    
    # Edge case: Silhouette requires 1 < n_unique < n_samples
    if n_unique < 2:
        return None, "Silhouette Score requires at least 2 distinct clusters."
    if n_unique >= n_samples:
        return None, (
            f"Silhouette Score cannot be calculated when number of clusters ({n_unique}) "
            f"equals or exceeds customer count ({n_samples}). Add more customers to evaluate."
        )
        
    try:
        score = silhouette_score(scaled_features, cluster_labels)
        return round(float(score), 4), None
    except Exception as e:
        return None, f"Could not calculate silhouette score: {str(e)}"


def perform_clustering(n_clusters=3, auto_adjust=True):
    """
    Takes RFM data, validates edge cases (< 3 customers, missing data),
    scales features, applies Hierarchical Agglomerative Clustering,
    and evaluates clustering quality with the Silhouette Score.
    
    Parameters:
        n_clusters (int): Desired number of clusters (default is 3).
        auto_adjust (bool): If True, automatically adjusts n_clusters to (n_samples - 1)
                            if customers == 3 so silhouette score can be computed.
                            
    Returns:
        tuple: (df, silhouette_score, message)
    """
    # 1. Fetch raw RFM data
    df = get_rfm_data()
    
    # Edge Case 1: Missing or empty data
    if df is None or df.empty:
        return None, None, "No customer or transaction data available in database."
        
    n_samples = len(df)
    
    # Edge Case 2: Fewer than 3 customers
    if n_samples < 3:
        return None, None, (
            f"Insufficient customer data: Found {n_samples} customer(s). "
            "A minimum of 3 customers with transactions is required for clustering."
        )
        
    # Edge Case 3: Requested clusters vs sample count
    effective_clusters = n_clusters
    if n_samples <= n_clusters:
        if auto_adjust:
            # Adjust to (n_samples - 1) so at least one cluster has multiple members
            effective_clusters = max(2, n_samples - 1)
        else:
            effective_clusters = n_samples

    # 2. Extract numeric RFM features for ML
    features = df[['Recency', 'Frequency', 'Monetary']]
    
    # Handle any potential NaN or infinite values safely
    if features.isnull().any().any():
        return None, None, "Data contains missing values in RFM features."
        
    # 3. Feature Scaling (StandardScaler)
    scaler = StandardScaler()
    scaled_features = scaler.fit_transform(features)
    
    # 4. Hierarchical Agglomerative Clustering
    cluster_model = AgglomerativeClustering(n_clusters=effective_clusters, linkage='ward')
    cluster_labels = cluster_model.fit_predict(scaled_features)
    
    # Attach cluster assignments back to DataFrame
    df['Cluster'] = cluster_labels
    
    # 5. Evaluate with Silhouette Score
    score, eval_msg = calculate_silhouette(scaled_features, cluster_labels)
    
    status_msg = f"Clustered {n_samples} customers into {effective_clusters} segments."
    if eval_msg:
        status_msg += f" Note: {eval_msg}"
        
    return df, score, status_msg


if __name__ == '__main__':
    print("Running Clustering & Silhouette Score Evaluation...")
    df, score, message = perform_clustering()
    
    if df is not None:
        print("\n=== CLUSTERING RESULTS ===")
        print(message)
        print("\nCustomer Assignments:")
        print(df[['name', 'Recency', 'Frequency', 'Monetary', 'Cluster']])
        
        print("\n=== EVALUATION METRIC ===")
        if score is not None:
            print(f"Silhouette Score: {score}")
            if score > 0.5:
                print("Interpretation: Strong cluster structure (customers are well separated).")
            elif score >= 0.25:
                print("Interpretation: Moderate cluster structure (reasonable grouping).")
            else:
                print("Interpretation: Weak cluster structure (clusters may overlap).")
        else:
            print("Silhouette Score: N/A (See note above)")
    else:
        print(f"\nClustering Failed: {message}")
