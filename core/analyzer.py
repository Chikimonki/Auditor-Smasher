import streamlit as st
import pandas as pd
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .data_processor import load_data


try:
    from .data_loader import load_data
    from .anomaly_detector import AnomalyDetector
    print("✅ All imports successful")
except ImportError as e:
    st.error(f"Import error: {e}")
    st.stop()

# Page config
st.set_page_config(page_title="UK Spending Analyzer", layout="wide")

def analyze_spending(df, sort_by='highest'):
    """
    Analyze spending data with sorting options
    Returns: analyzed DataFrame and statistics
    """
    # Find amount column
    amount_cols = [col for col in df.columns if 'amount' in col.lower() or 'value' in col.lower()]
    if not amount_cols:
        st.error("No amount column found for analysis")
        return df, {}
    
    amount_col = amount_cols[0]
    
    # Ensure it's numeric (in case not converted earlier)
    try:
        if df[amount_col].dtype == 'object':
            # Remove currency symbols and commas
            df[amount_col] = df[amount_col].astype(str).str.replace('[£,$,\s]', '', regex=True)
            df[amount_col] = pd.to_numeric(df[amount_col], errors='coerce')
    except Exception as e:
        st.error(f"Could not convert {amount_col} to numeric: {e}")
        return df, {}
    
    # Sort based on user choice
    if sort_by == 'highest':
        df_sorted = df.sort_values(by=amount_col, ascending=False)
    elif sort_by == 'lowest':
        df_sorted = df.sort_values(by=amount_col, ascending=True)
    elif sort_by == 'supplier':
        supplier_cols = [col for col in df.columns if 'supplier' in col.lower() or 'name' in col.lower()]
        if supplier_cols:
            df_sorted = df.sort_values(by=supplier_cols[0])
        else:
            df_sorted = df
    elif sort_by == 'date':
        date_cols = [col for col in df.columns if 'date' in col.lower()]
        if date_cols:
            # Try to convert to datetime
            try:
                df[date_cols[0]] = pd.to_datetime(df[date_cols[0]], errors='coerce')
                df_sorted = df.sort_values(by=date_cols[0], ascending=False)
            except:
                df_sorted = df.sort_values(by=date_cols[0])
        else:
            df_sorted = df
    else:
        df_sorted = df
    
    # Add rankings
    df_sorted['rank'] = range(1, len(df_sorted) + 1)
    
    # Calculate summary stats
    total_spend = df_sorted[amount_col].sum()
    avg_spend = df_sorted[amount_col].mean()
    top_10_sum = df_sorted[amount_col].head(10).sum()
    
    return df_sorted, {
        'total_spend': total_spend,
        'avg_spend': avg_spend,
        'top_10_sum': top_10_sum,
        'amount_col': amount_col
    }

def main_analysis_function(df: pd.DataFrame) -> dict:
    detector = AnomalyDetector(min_amount=1000, risk_threshold=5.0)
    df_with_anomalies = detector.detect_anomalies(df)
    amount_col = [c for c in df.columns if 'amount' in c.lower()][0]
    df[amount_col] = pd.to_numeric(df[amount_col].astype(str).str.replace('[£,$,\s]', '', regex=True), errors='coerce')
    total_spend = df[amount_col].sum()
    avg_spend = df[amount_col].mean()
    return {
        "total_spend": total_spend,
        "avg_transaction": avg_spend,
        "anomaly_df": df_with_anomalies,
        "message": "Analysis complete"
    }



    st.title("🇬🇧 UK Public Spending Analyzer")
    st.markdown("---")
    
    # Sidebar for analysis options
    with st.sidebar:
        st.header("⚙️ Analysis Options")
        
        st.subheader("Sorting")
        sort_option = st.selectbox(
            "Sort transactions by:",
            ['highest', 'lowest', 'supplier', 'date'],
            help="Sort by highest amount, lowest amount, supplier name, or date"
        )
        
        st.subheader("Anomaly Detection")
        run_anomaly = st.checkbox("Run anomaly detection", value=True)
        if run_anomaly:
            risk_threshold = st.slider("Risk threshold", 0.0, 10.0, 5.0)
            min_amount = st.number_input("Minimum amount (£)", 0, 1000000, 1000)
        
        st.subheader("Display Options")
        show_top = st.number_input("Show top N results", 10, 1000, 100)
        show_raw = st.checkbox("Show raw data", False)
    
    # Main file upload area
    st.subheader("📤 Upload Public Spending CSV")
    uploaded_file = st.file_uploader("Choose a CSV file", type=["csv"], label_visibility="collapsed")
    
    if uploaded_file is not None:
        # File info
        col1, col2 = st.columns(2)
        with col1:
            st.success(f"📁 **File:** {uploaded_file.name}")
        with col2:
            st.info(f"📊 **Size:** {uploaded_file.size / 1024:.1f} KB")
        
        # Load data
        with st.spinner("📥 Loading data..."):
            df = load_data(uploaded_file)
        
                # Basic info cards
        st.subheader("📈 Data Overview")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Rows", f"{len(df):,}")
        with col2:
            st.metric("Columns", len(df.columns))
        with col3:
            amount_cols = [col for col in df.columns if 'amount' in col.lower() or 'value' in col.lower()]
            if amount_cols:
                # Convert to numeric first
                amount_col = amount_cols[0]
                try:
                    # Remove £, $, commas and convert to float
                    df[amount_col] = df[amount_col].astype(str).str.replace('[£,$,\s]', '', regex=True)
                    df[amount_col] = pd.to_numeric(df[amount_col], errors='coerce')
                    
                    total = df[amount_col].sum()
                    st.metric("Total Value", f"£{total:,.0f}")
                except Exception as e:
                    st.metric("Total Value", "Error")
                    print(f"Amount conversion error: {e}")
            else:
                st.metric("Amount Column", "Not found")
        with col4:
            st.metric("Status", "✅ Loaded")
        
        # Show column names
        with st.expander("🔍 View All Columns"):
            for i, col in enumerate(df.columns):
                st.write(f"{i+1}. **{col}**")
        
        # Validate data
        is_valid, message = validate_data_structure(df)
        
        if not is_valid:
            st.error(f"❌ {message}")
            return
        
        st.success(f"✅ {message}")
        
        # ===== ANALYSIS BUTTON =====
        st.markdown("---")
        st.subheader("🔬 Data Analysis")
        
        if st.button("🚀 **Analyze Data**", type="primary", use_container_width=True):
            with st.spinner("Analyzing spending patterns..."):
                # 1. Sort the data
                df_sorted, stats = analyze_spending(df, sort_by=sort_option)
                
                # 2. Show summary
                st.subheader("💰 Spending Summary")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Spend", f"£{stats['total_spend']:,.0f}")
                with col2:
                    st.metric("Average Transaction", f"£{stats['avg_spend']:,.0f}")
                with col3:
                    percentage = (stats['top_10_sum'] / stats['total_spend'] * 100) if stats['total_spend'] > 0 else 0
                    st.metric("Top 10 Sum", f"£{stats['top_10_sum']:,.0f} ({percentage:.1f}%)")
                
                # 3. Show top transactions
                st.subheader(f"🏆 Top {show_top} Transactions ({sort_option.title()} First)")
                
                # Format the display
                display_cols = []
                for col in df_sorted.columns:
                    if col.lower() in ['supplier', 'amount', 'value', 'date', 'description', 'department', 'cost_centre']:
                        display_cols.append(col)
                if not display_cols and len(df_sorted.columns) > 0:
                    display_cols = df_sorted.columns[:5].tolist()
                
                display_df = df_sorted[['rank'] + display_cols].head(show_top)
                
                # Format currency columns
                for col in display_df.columns:
                    if 'amount' in col.lower() or 'value' in col.lower():
                        display_df[col] = display_df[col].apply(lambda x: f"£{x:,.2f}" if pd.notnull(x) else "")
                
                st.dataframe(display_df, use_container_width=True)
                
                # 4. Run anomaly detection if requested
                if run_anomaly:
                    st.subheader("🚨 Anomaly Detection Results")
                    with st.spinner("Detecting anomalies..."):
                        try:
                            detector = AnomalyDetector()

                            # Create a working copy
                            df_for_detector = df.copy()
                            
                            # COMPREHENSIVE COLUMN MAPPING
                            column_rename = {}
                            for col in df_for_detector.columns:
                                col_lower = col.lower()
                                if 'supplier' in col_lower:
                                    column_rename[col] = 'supplier_name'
                                elif 'amount' in col_lower:
                                    column_rename[col] = 'contract_value'
                                elif 'date' in col_lower:
                                    column_rename[col] = 'contract_date'
                                # Map 'summary_of_expenditure' to a description field if needed
                                elif 'summary' in col_lower or 'description' in col_lower:
                                    column_rename[col] = 'service_description'

                            if column_rename:
                                df_for_detector = df_for_detector.rename(columns=column_rename)
                                print(f"✅ Renamed columns: {column_rename}")
                            
                            # CRITICAL: Add missing 'procurement_method' column (your CSV doesn't have it)
                            if 'procurement_method' not in df_for_detector.columns:
                                print("⚠️  Adding dummy 'procurement_method' column (not in original CSV)")
                                df_for_detector['procurement_method'] = 'Not Specified'
                            
                            # Optional: Add other expected columns
                            if 'contracting_authority' not in df_for_detector.columns:
                                df_for_detector['contracting_authority'] = 'Sefton Council'
                            
                            print(f"🔍 Final columns for detector: {list(df_for_detector.columns)}")
                            
                            # Now run anomaly detection
                            df_anomalies = detector.detect_anomalies(df_for_detector)
                            st.write("🔍 **Anomaly Score Distribution:**")
                            score_counts = df_anomalies['anomaly_score'].value_counts().sort_index()
                            st.write(score_counts)

                            st.write("📋 **Sample of Scored Transactions:**")
                            # Show first 10 rows with any flags
                            if (df_anomalies['anomaly_score'] > 0).any():
                                st.dataframe(df_anomalies[df_anomalies['anomaly_score'] > 0].head(10))
                            else:
                                st.write("No transactions received an anomaly score.")
                            anomaly_count = (df_anomalies['anomaly_score'] > 0).sum()
                            
                            if anomaly_count > 0:
                                st.warning(f"Found {anomaly_count} potential anomalies")
                                
                                # Show top anomalies
                                top_anomalies = df_anomalies[df_anomalies['anomaly_score'] > 0].sort_values('anomaly_score', ascending=False)
                                
                                # Download button for anomalies
                                csv = top_anomalies.to_csv(index=False)
                                st.download_button(
                                    label="📥 Download Anomalies as CSV",
                                    data=csv,
                                    file_name="detected_anomalies.csv",
                                    mime="text/csv"
                                )
                                
                                # Display anomalies
                                st.dataframe(top_anomalies.head(20), use_container_width=True)
                            else:
                                st.success("✅ No anomalies detected")
                        except Exception as e:
                            st.error(f"Anomaly detection failed: {e}")
                
                # 5. Show raw data if requested
                if show_raw:
                    st.subheader("📋 Raw Data Preview")
                    st.dataframe(df_sorted.head(50), use_container_width=True)
        
        # Quick analysis options
        st.markdown("---")
        st.subheader("⚡ Quick Analysis")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("🔝 Top 10 Highest", use_container_width=True):
                df_sorted, _ = analyze_spending(df, sort_by='highest')
                st.dataframe(df_sorted[['supplier', 'amount']].head(10) if 'supplier' in df_sorted.columns else df_sorted.head(10))
        
        with col2:
            if st.button("📅 By Date", use_container_width=True):
                date_cols = [col for col in df.columns if 'date' in col.lower()]
                if date_cols:
                    df_sorted = df.sort_values(by=date_cols[0], ascending=False)
                    st.dataframe(df_sorted.head(10))
                else:
                    st.warning("No date column found")
        
        with col3:
            if st.button("🏢 By Supplier", use_container_width=True):
                df_sorted, _ = analyze_spending(df, sort_by='supplier')
                st.dataframe(df_sorted.head(10))

if __name__ == "__main__":
    main()