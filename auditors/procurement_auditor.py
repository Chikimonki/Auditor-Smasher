# auditors/procurement_auditor.py
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans

class ProcurementAuditor:
    """Analyses procurement patterns for anomalies"""
    
    def __init__(self):
        self.single_source_threshold = 0.7  # 70% of spend with one supplier
        
    def detect_single_source(self, df, council_name):
        """Detect single-source dependency"""
        if 'supplier' not in df.columns or 'amount' not in df.columns:
            return []
        
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)
        
        supplier_totals = df.groupby('supplier')['amount'].sum()
        total_spend = supplier_totals.sum()
        
        if total_spend == 0:
            return []
        
        dominant_supplier = supplier_totals.idxmax()
        dominant_pct = supplier_totals.max() / total_spend
        
        findings = []
        if dominant_pct > self.single_source_threshold:
            findings.append({
                'council': council_name,
                'type': 'SINGLE_SOURCE_DEPENDENCY',
                'supplier': dominant_supplier,
                'concentration_pct': dominant_pct * 100,
                'total_spend': total_spend,
                'risk': 'HIGH' if dominant_pct > 0.85 else 'MEDIUM',
            })
        
        return findings
    
    def cluster_spending(self, df, n_clusters=3):
        """Cluster similar spending patterns"""
        if 'amount' not in df.columns:
            return df
        
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)
        
        X = df[['amount']].values
        if len(X) < n_clusters:
            return df
        
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        df['spend_cluster'] = kmeans.fit_predict(X)
        
        return df
