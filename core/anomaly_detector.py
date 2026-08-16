import pandas as pd

class AnomalyDetector:
    def __init__(self, min_amount=1000, risk_threshold=5.0):
        self.min_amount = min_amount
        self.risk_threshold = risk_threshold
        
        self.single_source_keywords = [
            "direct award", "negotiated", "single source", "single-source",
            "without competition", "non-competitive"
        ]
        
        self.politically_connected_suppliers = [
            "party associated ltd", "minister relative co", "mp connections uk"
        ]

    # === MAIN DETECTION METHOD ===
    def detect_anomalies(self, df):
        """
        Apply all anomaly detection rules to the dataframe
        """
        # 1. Create working copy
        df_analyzed = df.copy()
        
        # 2. Handle empty data
        if df_analyzed.empty:
            df_analyzed['anomaly_score'] = 0
            df_analyzed['anomaly_flags'] = ""
            df_analyzed['risk_level'] = "low"
            return df_analyzed
        
        # 3. Map columns (so your CSV columns match expected names)
        column_map = {}
        for col in df_analyzed.columns:
            col_lower = col.lower()
            if 'supplier' in col_lower:
                column_map['supplier_name'] = col
            elif 'amount' in col_lower:
                column_map['contract_value'] = col
            elif 'date' in col_lower:
                column_map['contract_date'] = col
        
        self.column_map = column_map
        
        # 4. Initialize tracking columns
        df_analyzed['anomaly_score'] = 0
        df_analyzed['anomaly_flags'] = ""
        df_analyzed['risk_level'] = "low"
        
        # 5. Apply detection rules
        df_analyzed = self._detect_high_value(df_analyzed)
        df_analyzed = self._detect_single_source(df_analyzed)
        df_analyzed = self._detect_politically_connected(df_analyzed)
        
        # 6. Calculate final risk
        df_analyzed['risk_level'] = df_analyzed['anomaly_score'].apply(
            lambda x: "high" if x >= self.risk_threshold else "medium" if x >= 2 else "low"
        )
        
        return df_analyzed

    # === HELPER DETECTION METHODS ===
    def _detect_high_value(self, df):
        """Flag transactions above minimum amount"""
        if 'contract_value' in self.column_map:
            col = self.column_map['contract_value']
            # Convert to numeric if needed
            if df[col].dtype == 'object':
                df[col] = pd.to_numeric(df[col].astype(str).str.replace('[£,$,\s]', '', regex=True), errors='coerce')
            
            high_mask = df[col] >= self.min_amount
            df.loc[high_mask, 'anomaly_score'] += 1
            df.loc[high_mask, 'anomaly_flags'] += f"High value (>£{self.min_amount}); "
        
        return df

    def _detect_single_source(self, df):
        """Check for non-competitive procurement terms"""
        # Check if we have a procurement method column
        if 'procurement_method' not in self.column_map:
            return df  # Skip this check if column doesn't exist
        
        col = self.column_map['procurement_method']
        if col in df.columns:
            for keyword in self.single_source_keywords:
                mask = df[col].astype(str).str.contains(keyword, case=False, na=False)
                if mask.any():
                    df.loc[mask, 'anomaly_score'] += 1
                    df.loc[mask, 'anomaly_flags'] += f"Single-source ({keyword}); "
        
        return df

    def _detect_politically_connected(self, df):
        """Flag potentially politically connected suppliers"""
        if 'supplier_name' in self.column_map:
            col = self.column_map['supplier_name']
            for supplier in self.politically_connected_suppliers:
                mask = df[col].astype(str).str.contains(supplier, case=False, na=False)
                if mask.any():
                    df.loc[mask, 'anomaly_score'] += 2  # Higher score for political connections
                    df.loc[mask, 'anomaly_flags'] += "Politically connected supplier; "
        
        return df

    def _detect_spend_concentration(self, df):
        """Flag suppliers who receive a very high percentage of total spend."""
        if 'supplier_name' in self.column_map and 'contract_value' in self.column_map:
            supplier_col = self.column_map['supplier_name']
            amount_col = self.column_map['contract_value']
            
            # Calculate total spend per supplier
            supplier_totals = df.groupby(supplier_col)[amount_col].sum().sort_values(ascending=False)
            total_spend_all = supplier_totals.sum()
            
            if total_spend_all > 0:
                # Flag suppliers making up more than 5% of total spend
                major_supplier_mask = df[supplier_col].isin(
                    supplier_totals[supplier_totals / total_spend_all > 0.05].index
                )
                df.loc[major_supplier_mask, 'anomaly_score'] += 1
                df.loc[major_supplier_mask, 'anomaly_flags'] += "Major supplier (>5% total spend); "
        
        return df