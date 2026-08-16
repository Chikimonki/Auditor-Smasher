import streamlit as st
import pandas as pd
import duckdb
import pyarrow.parquet as pq
import requests 
# Add this temporary code to check indentation
import sys
with open(__file__, 'r') as f:
    lines = f.readlines()
    for i, line in enumerate(lines, 1):
        if line.strip():
            spaces = len(line) - len(line.lstrip())
            if spaces % 4 != 0:
                print(f"Line {i}: Bad indentation ({spaces} spaces)")

USE_FLASK_BACKEND = st.sidebar.checkbox("Use Flask Backend", value=False)
BACKEND_URL = "http://localhost:5000" if USE_FLASK_BACKEND else None

@st.cache_data(ttl=3600)
def load_and_optimize_data(uploaded_file):
    """Load CSV with proper header handling for Sefton Council format."""
    import pandas as pd
    import tempfile
    import os
    
    # Save uploaded file to temp location for pandas
    with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp_file:
        tmp_file.write(uploaded_file.getvalue())
        tmp_path = tmp_file.name
    
    # CRITICAL FIX: Use skiprows=1 to skip the title line (Line 0)
    # Line 1 becomes our header, Line 2 onward is data
    df = pd.read_csv(tmp_path, skiprows=1, encoding='latin-1')
    
    # Clean up temp file
    os.unlink(tmp_path)
    
    # OPTIONAL: Standardize column names to lowercase with underscores
    column_mapping = {
        'SUPPLIER': 'supplier',
        'AMOUNT': 'amount',
        'TRANSACTION DATE': 'transaction_date',
        'COST CENTRE': 'cost_centre',
        'ACCOUNT': 'account',
        'DEPARTMENT': 'department',
        'SUMMARY OF EXPENDITURE': 'expenditure_summary'
    }
    
    # Rename columns that exist
    df = df.rename(columns={col: column_mapping[col] 
                           for col in df.columns 
                           if col in column_mapping})
    
    # Clean the amount column: remove commas, handle negatives, convert to numeric
    if 'amount' in df.columns:
        # Remove commas, preserve negative sign, convert to float
        df['amount'] = pd.to_numeric(
            df['amount'].astype(str).str.replace(',', ''),
            errors='coerce'
        )
        # COUNCIL DATA NOTE: Amounts are negative (payments). For spending analysis:
        # df['amount'] = df['amount'].abs()  # Uncomment to convert to positive
    
    # Clean supplier names
    if 'supplier' in df.columns:
        df['supplier'] = df['supplier'].astype(str).str.strip()
    
    return df

# For truly large files, use chunking:
def process_large_csv(uploaded_file, chunk_size=10000):
    """Process CSV in chunks to avoid memory issues"""
    chunks = pd.read_csv(uploaded_file, chunksize=chunk_size, engine='pyarrow')
    processed_chunks = []
    
    for chunk in chunks:
        # Process each chunk (filter, clean, etc.)
        chunk = chunk[chunk['supplier'].notna()]
        processed_chunks.append(chunk)
    
    return pd.concat(processed_chunks, ignore_index=True)

def find_supplier_column(df):
    """
    Find the most likely supplier column in a DataFrame.
    Returns the column name as a string.
    """
    # Common names for supplier columns in UK council data
    possible_names = [
        'supplier', 'payee', 'vendor', 'supplier_name', 
        'name', 'payee_name', 'organisation', 'organization',
        'contractor', 'company', 'beneficiary'
    ]
    for col in df.columns:
        col_lower = str(col).lower()
        for possible in possible_names:
            if possible in col_lower:
                print(f"✅ Found supplier column: '{col}'")
                return col
    # Fallback: return the first column
    print(f"⚠️ Could not identify supplier column, using '{df.columns[0]}'")
    return df.columns[0]

from core.data_loader import load_data
from integrations.companies_house import enrich_suppliers_dataframe
from auditors.supplier_network_auditor import SupplierNetworkAuditor

st.set_page_config(page_title="Auditor Smasher", layout="wide")
st.title("🔍 Auditor Smasher - Advanced Council Audit")

# ===== FILE UPLOAD & FAST LOADING =====
uploaded_files = st.file_uploader(
    "Upload one or MORE council CSV files for network analysis",
    type=["csv"],
    accept_multiple_files=True,
    help="Upload multiple council files to detect suppliers operating across regions"
)

# Initialize variables
all_dataframes = []
council_names = []
successful_councils = []
network_auditor = None

# In your app.py, after: uploaded_files = st.file_uploader(...)

if uploaded_files:
    # Take the first uploaded file
    file = uploaded_files[0]
    
    # Save it locally temporarily for inspection
    import tempfile
    import os
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp_file:
        tmp_file.write(file.getvalue())
        tmp_path = tmp_file.name
    
    st.write(f"📁 **Debug**: Saved temporary file to: `{tmp_path}`")
    
    # Now analyze it
    import pandas as pd
    
st.subheader("🏆 **Top Suppliers by Total Value**")

# ===== DEBUG: FLASK CALL CHECK =====
st.write("### 🎯 FLASK CALL CHECK")
st.write(f"**Checkbox checked:** {'✅ YES' if USE_FLASK_BACKEND else '❌ NO'}")
st.write(f"**Backend URL:** {BACKEND_URL}")
st.write(f"**Files uploaded:** {len(uploaded_files) if uploaded_files else 0}")

# Check if ALL conditions for Flask call are met
will_call_flask = uploaded_files and len(uploaded_files) > 0 and USE_FLASK_BACKEND and BACKEND_URL
st.write(f"**Will call Flask?** {'✅ YES' if will_call_flask else '❌ NO'}")

if will_call_flask:
    st.write("🔍 **Status:** Attempting Flask API call...")
else:
    st.write("🔍 **Status:** Using local processing")

st.write("---")  # Separator line

try:
    # Only try Flask backend if enabled and we have files
    if uploaded_files and len(uploaded_files) > 0 and USE_FLASK_BACKEND and BACKEND_URL:
        # Prepare files for API call
        files_dict = [('files', (file.name, file.getvalue(), 'text/csv')) for file in uploaded_files]

        st.write("🔍 **DEBUG REQUEST**")
        st.write(f"- URL: {BACKEND_URL}/api/top-suppliers")
        st.write(f"- File count: {len(files_dict)}")
        st.write(f"- First filename: {files_dict[0][1][0] if files_dict else 'None'}")

        try:
            response = requests.post(
                f'{BACKEND_URL}/api/top-suppliers',
                files=files_dict,
                timeout=15
            )
            st.write(f"🔍 **DEBUG RESPONSE STATUS**: {response.status_code}")
            
            # Check response
            if response.status_code == 200:
                # DEBUG: Let's see exactly what the backend returns
                st.write("🔍 **DEBUG RESPONSE RAW TEXT:**", response.text[:500])
                
                try:
                    import json
                    response_data = json.loads(response.text)
                    st.write("🔍 **DEBUG PARSED JSON TYPE:**", type(response_data))
                    
                    if isinstance(response_data, list):
                        st.write(f"✅ Backend returned a list with {len(response_data)} items.")
                        if response_data:
                            st.write("🔍 **First item in list:**", response_data[0])
                            top_suppliers_df = pd.DataFrame(response_data)
                            st.write("✅ Successfully converted list to DataFrame.")
                            
                            if not top_suppliers_df.empty:
                                st.dataframe(
                                    top_suppliers_df.style.format({
                                        'total_spent': '£{:,.2f}',
                                        'avg_transaction': '£{:,.2f}'
                                    }),
                                    use_container_width=True
                                )
                                chart_data = top_suppliers_df.head(10).set_index('supplier')['total_spent']
                                st.bar_chart(chart_data)
                            else:
                                st.info("DataFrame created but is empty.")
                                raise Exception("Empty DataFrame from backend")
                        else:
                            st.warning("Backend returned an empty list.")
                            raise Exception("Empty list from backend")
                            
                    elif isinstance(response_data, dict):
                        st.write("🔍 **Backend returned a dict. Keys:**", list(response_data.keys()))
                        if 'error' in response_data:
                            st.error(f"Backend error: {response_data['error']}")
                            raise Exception(f"Backend error: {response_data['error']}")
                        else:
                            top_suppliers_df = pd.DataFrame([response_data])
                            st.dataframe(top_suppliers_df)
                    else:
                        st.error(f"Unexpected response type: {type(response_data)}")
                        raise Exception(f"Unexpected response type: {type(response_data)}")
                        
                except json.JSONDecodeError as e:
                    st.error(f"🔴 Failed to decode JSON from backend. Raw text: {response.text[:200]}")
                    st.error(f"JSON Error: {e}")
                    raise Exception(f"Invalid JSON from backend: {e}")
                    
            elif response.status_code == 500:
                st.error(f"Backend error (500): {response.text}")
                try:
                    error_data = response.json()
                    st.write(f"Error details: {error_data}")
                except:
                    st.write(f"Raw error: {response.text}")
                raise Exception("Backend 500 error")
            else:
                st.warning(f"Backend returned status {response.status_code}")
                raise Exception(f"Backend error {response.status_code}")
                
        except requests.exceptions.RequestException as req_err:
            st.error(f"🔍 **NETWORK ERROR**: {req_err}")
            raise Exception(f"Failed to call backend: {req_err}")
        
    else:
        # Flask backend not enabled or no files
        if not USE_FLASK_BACKEND:
            st.info("Using local processing (Flask backend disabled)")
        raise Exception("Flask backend not configured")
        
except Exception as e:
    # Fallback to local processing
    st.warning(f"⚠️ Using fallback mode: {str(e)}")
    
    # Check if we have data for local processing
    if 'df_combined' in locals() and not df_combined.empty:
        st.write("🔍 DEBUG: Attempting local processing...")
        st.write(f"df_combined columns: {list(df_combined.columns)}")
        
        amount_col = 'actual_value' if 'actual_value' in df_combined.columns else None
        if not amount_col:
            amount_cols = [col for col in df_combined.columns 
                          if any(word in col.lower() for word in ['amount', 'value', 'total', 'payment'])]
            amount_col = amount_cols[0] if amount_cols else None
        
        if 'supplier' in df_combined.columns and amount_col:
            df_combined['amount_numeric'] = pd.to_numeric(
                df_combined[amount_col].astype(str)
                .str.replace('£', '')
                .str.replace(',', ''),
                errors='coerce'
            )
            
            top_suppliers_local = df_combined.groupby('supplier').agg({
                'amount_numeric': ['sum', 'count', 'mean']
            }).round(2)
            
            top_suppliers_local.columns = ['total_spent', 'transaction_count', 'avg_transaction']
            top_suppliers_local = top_suppliers_local.reset_index()
            top_suppliers_local = top_suppliers_local.sort_values('total_spent', ascending=False).head(15)
            
            if not top_suppliers_local.empty:
                st.dataframe(top_suppliers_local)
                chart_data = top_suppliers_local.head(10).set_index('supplier')['total_spent']
                st.bar_chart(chart_data)
            else:
                st.info("No supplier data available in local processing")
        else:
            st.error(f"Missing columns for local processing. Supplier: {'supplier' in df_combined.columns}, Amount: {amount_col}")
    else:
        st.error("Local data not available for fallback processing")