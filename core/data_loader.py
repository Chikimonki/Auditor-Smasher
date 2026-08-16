import pandas as pd
import io
import chardet
import re

def load_data(uploaded_file):
    df = pd.read_csv(uploaded_file, encoding='windows-1252', on_bad_lines='skip')
    
    # NEW: Call the robust standardizer
    df, column_map = _standardize_and_map_columns(df)
    
    # Store the map in the dataframe's attributes for later use if needed
    df.attrs['column_map'] = column_map
    
    # ... continue with the rest of your load_data logic (like converting amounts) ...

    # === NEW: DIAGNOSTIC PRINT ===
    print("="*50)
    print(f"DEBUG: File '{uploaded_file.name}' loaded.")
    print(f"DEBUG: Raw columns: {list(df.columns)}")

    try:
        # 1. Read raw bytes and detect encoding
        uploaded_file.seek(0)
        raw_bytes = uploaded_file.read()
        
        # Try multiple encodings
        encodings_to_try = ['windows-1252', 'latin-1', 'ISO-8859-1', 'utf-8']
        content = None
        
        for encoding in encodings_to_try:
            try:
                content = raw_bytes.decode(encoding)
                print(f"✅ Decoded with {encoding}")
                break
            except:
                continue
        
        if 'amount' in df.columns:
            df['amount'] = df['amount'].abs()  # Make all values positive
            # Fallback with chardet
            result = chardet.detect(raw_bytes)
            encoding = result['encoding'] or 'windows-1252'
            content = raw_bytes.decode(encoding, errors='ignore')
            print(f"⚠️ Using chardet detection: {encoding}")
        
        # 2. Analyze file structure
        lines = content.splitlines()
        print(f"📄 File has {len(lines)} total lines")
        
        # Show first 10 lines for debugging
        print("\n=== FIRST 10 LINES ===")
        for i, line in enumerate(lines[:10]):
            print(f"Line {i}: {repr(line[:100])}")
        
        # 3. Find where data actually starts
        data_start = 0
        for i, line in enumerate(lines[:20]):
            # Skip empty lines and obvious metadata
            if not line.strip():
                continue
            if 'sefton council' in line.lower():
                print(f"📛 Skipping title at line {i}")
                continue
            
            # Look for a header row
            if ',' in line:
                parts = line.split(',')
                # Check if this looks like headers (not data)
                if len(parts) >= 3:
                    # Check for common column names
                    line_lower = line.lower()
                    header_keywords = ['supplier', 'amount', 'date', 'cost', 'department', 'payment']
                    if any(keyword in line_lower for keyword in header_keywords):
                        data_start = i
                        print(f"✅ Found header at line {i}")
                        print(f"   Header: {line}")
                        break
        
        print(f"📊 Starting data from line {data_start}")
        
        # 4. Read the CSV
        uploaded_file.seek(0)
        
        # Try multiple reading strategies
        strategies = []
        
        # Strategy 1: Skip rows
        try:
            uploaded_file.seek(0)
            df1 = pd.read_csv(uploaded_file, encoding='windows-1252', skiprows=data_start)
            strategies.append(('skiprows', df1))
            print(f"Strategy 1 (skiprows): {len(df1)} rows")
        except Exception as e:
            print(f"Strategy 1 failed: {e}")
        
        # Strategy 2: Read all and slice
        try:
            uploaded_file.seek(0)
            df2 = pd.read_csv(uploaded_file, encoding='windows-1252')
            if data_start > 0 and len(df2) > data_start:
                df2 = df2.iloc[data_start:].reset_index(drop=True)
                # Check if first row should be header
                first_row_str = str(df2.iloc[0, 0]).lower()
                if any(keyword in first_row_str for keyword in ['supplier', 'amount', 'date']):
                    df2.columns = df2.iloc[0]
                    df2 = df2[1:].reset_index(drop=True)
            strategies.append(('slice', df2))
            print(f"Strategy 2 (slice): {len(df2)} rows")
        except Exception as e:
            print(f"Strategy 2 failed: {e}")
        
        # Strategy 3: Manual parsing
        try:
            # Extract data lines
            data_lines = []
            for line in lines[data_start:]:
                if line.count(',') >= 2:  # At least 3 columns
                    data_lines.append(line)
            
            if len(data_lines) > 1:
                df3 = pd.read_csv(io.StringIO('\n'.join(data_lines)), encoding='windows-1252')
                strategies.append(('manual', df3))
                print(f"Strategy 3 (manual): {len(df3)} rows")
        except Exception as e:
            print(f"Strategy 3 failed: {e}")
        
        # 5. Choose the best result
        best_df = None
        best_rows = 0
        
        for name, df in strategies:
            if not df.empty and len(df) > best_rows:
                best_rows = len(df)
                best_df = df
                print(f"📈 Best so far: {name} with {len(df)} rows")
        
        if best_df is not None:
            df = best_df
        else:
            # Last resort: read with no header
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, encoding='windows-1252', header=None)
            print(f"⚠️ Using fallback: {len(df)} rows with no header")
        
        # 6. Clean up
        if not df.empty:
            # Clean column names
            df.columns = [str(col).strip() for col in df.columns]
            df.columns = df.columns.str.lower().str.replace(' ', '_').str.replace(r'[^\w\s]', '', regex=True)
            
            # Remove any rows that are clearly not data
            initial_rows = len(df)
            for col in df.columns[:2]:  # Check first two columns
                if col in df.columns:
                    # Remove rows where this column contains the title
                    mask = df[col].astype(str).str.contains('sefton council', case=False, na=False)
                    df = df[~mask]
            
            removed = initial_rows - len(df)
            if removed > 0:
                print(f"🗑️ Removed {removed} rows containing 'sefton council'")
            
            print(f"✅ FINAL: {len(df)} rows, {len(df.columns)} columns")
            print(f"   Columns: {list(df.columns)}")
            
            if len(df) > 0:
                print("\n📋 First 3 rows:")
                for i in range(min(3, len(df))):
                    row_preview = []
                    for col in df.columns[:4]:  # First 4 columns
                        val = str(df.iloc[i][col])[:30]
                        row_preview.append(f"{col}: {val}")
                    print(f"   Row {i}: {' | '.join(row_preview)}")
        
        return df
        
    except Exception as e:
        print(f"❌ CRITICAL ERROR in load_data: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()

def validate_data_structure(df):
    """
    Simple validation that always returns True for now
    """
    if df.empty:
        return False, "No data loaded. CSV may be empty or unreadable."
    
    print(f"🔍 Validating: {len(df)} rows, {len(df.columns)} columns")
    
    # Check for required columns with flexible matching
    required = {
        'supplier_name': ['supplier', 'payee', 'vendor', 'name'],
        'contract_value': ['amount', 'value', 'payment', 'cost', 'total'],
        'procurement_method': ['method', 'type', 'procurement', 'category']
    }
    
    found = {}
    for req_name, keywords in required.items():
        for col in df.columns:
            col_lower = col.lower()
            if any(keyword in col_lower for keyword in keywords):
                found[req_name] = col
                print(f"✅ Matched {req_name} -> '{col}'")
                break
    
    # If we found supplier and amount, that's enough to proceed
    if 'supplier_name' in found and 'contract_value' in found:
        return True, f"✅ Ready! {len(df)} transactions loaded."
    
    # Otherwise show what we have
    available = ", ".join(df.columns)
    return False, f"Need supplier and amount columns. Found: {available}"

def _standardize_and_map_columns(df):
    """
    Standardizes column names and returns a mapping to expected names.
    """
    # 1. First, clean all column names
    df.columns = df.columns.astype(str).str.strip().str.lower().str.replace(' ', '_').str.replace('-', '_')
    
    print(f"DEBUG: Standardized columns: {list(df.columns)}")
    
    # 2. Create a mapping dictionary for critical columns
    # This defines all possible names for the concepts we need.
    expected_mappings = {
        'supplier': ['supplier', 'payee', 'vendor', 'contractor', 'company', 'name', 'supplier_name'],
        'amount': ['amount', 'value', 'payment', 'net_amount', 'sum', 'total', 'cost', 'price'],
        'date': ['date', 'transaction_date', 'payment_date', 'invoice_date', 'period']
    }
    
    column_map = {}
    # For each expected column, find the best match
    for expected_col, possible_names in expected_mappings.items():
        for possible in possible_names:
            if possible in df.columns:
                column_map[expected_col] = possible
                print(f"DEBUG: Mapped '{expected_col}' -> '{possible}'")
                break  # Stop at first match
    
    # 3. Rename the dataframe columns for consistency
    df = df.rename(columns={v: k for k, v in column_map.items()})
    
    # 4. Ensure critical 'supplier' column exists, even if empty
    if 'supplier' not in df.columns:
        print("WARNING: Could not find a supplier column. Creating a placeholder.")
        df['supplier'] = 'Unknown'
        column_map['supplier'] = 'supplier' # Map to itself
    
    return df, column_map