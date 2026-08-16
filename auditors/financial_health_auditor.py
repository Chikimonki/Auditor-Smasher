# auditors/financial_health_auditor.py
import pandas as pd
import numpy as np
from scipy import stats

class FinancialHealthAuditor:
    """Analyses financial health indicators for anomalies"""
    
    def __init__(self):
        self.zscore_threshold = 3.0
    
    def detect_outliers(self, df):
        """Detect statistical outliers in amounts"""
        if 'amount' not in df.columns:
            return df
        
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)
        
        z_scores = np.abs(stats.zscore(df['amount']))
        df['is_financial_outlier'] = z_scores > self.zscore_threshold
        df['z_score'] = z_scores
        
        return df
    
    def trend_analysis(self, df):
        """Analyse spending trends over time"""
        if 'date' not in df.columns or 'amount' not in df.columns:
            return {}
        
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)
        
        monthly = df.groupby(df['date'].dt.to_period('M'))['amount'].agg(['sum', 'count', 'mean'])
        
        return {
            'months': len(monthly),
            'total_spend': monthly['sum'].sum(),
            'avg_monthly': monthly['sum'].mean(),
            'max_month': monthly['sum'].max(),
            'trend': 'increasing' if monthly['sum'].iloc[-1] > monthly['sum'].iloc[0] else 'decreasing',
        }
