import tempfile
import os
import duckdb
import pandas as pd
from flask import Flask, request, jsonify
from flask_cors import CORS

# ===== 1. CREATE THE FLASK APP =====
app = Flask(__name__)
CORS(app)  # Enable CORS for Streamlit frontend

# ===== 2. HEALTH CHECK ENDPOINT =====
@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'service': 'auditor-backend',
        'timestamp': pd.Timestamp.now().isoformat()
    })

# ===== 3. MAIN API ENDPOINT =====
@app.route('/api/top-suppliers', methods=['POST'])
def top_suppliers():
    app.logger.info('TOP SUPPLIERS ENDPOINT HIT')
    
    # Check if files were uploaded
    if 'files' not in request.files:
        app.logger.warning('No files uploaded in request')
        return jsonify({'error': 'No files uploaded'}), 400

    files = request.files.getlist('files')
    app.logger.info(f'Processing {len(files)} file(s)')
    
    all_results = []
    
    for file in files:
        if file.filename == '':
            continue
            
        # Create temp file for DuckDB to read
        temp_path = os.path.join(tempfile.gettempdir(), file.filename)
        file.save(temp_path)
        app.logger.debug(f'Processing file: {file.filename}')
        
        try:
            # Connect to DuckDB
            conn = duckdb.connect()
            
            # ===== DEBUG: LOG CSV COLUMNS =====
            try:
                columns_info = conn.execute(f"DESCRIBE SELECT * FROM read_csv_auto('{temp_path}')").df()
                app.logger.info(f"Columns in '{file.filename}': {list(columns_info['column_name'])}")
            except Exception as desc_error:
                app.logger.error(f"Could not describe table: {desc_error}")
                # Skip this file or raise error
                continue
            
            # ===== MAIN PROCESSING QUERY =====
            # Flexible query that tries multiple column names
            result = conn.execute(f"""
                WITH data AS (
                    SELECT *,
                        -- Try multiple supplier column names
                        COALESCE(
                            NULLIF(TRY_CAST(supplier AS VARCHAR), ''),
                            NULLIF(TRY_CAST("Supplier" AS VARCHAR), ''),
                            NULLIF(TRY_CAST(supplier_name AS VARCHAR), ''),
                            NULLIF(TRY_CAST("Supplier Name" AS VARCHAR), ''),
                            'Unknown'
                        ) as supplier_clean,
                        -- Try multiple amount column names
                        COALESCE(
                            TRY_CAST(amount AS DECIMAL(10,2)),
                            TRY_CAST("Amount" AS DECIMAL(10,2)),
                            TRY_CAST(actual_value AS DECIMAL(10,2)),
                            TRY_CAST("Actual Value" AS DECIMAL(10,2)),
                            TRY_CAST(value AS DECIMAL(10,2)),
                            TRY_CAST("Value" AS DECIMAL(10,2)),
                            0
                        ) as amount_clean
                    FROM read_csv_auto('{temp_path}', HEADER=TRUE, ENCODING='LATIN1')
                )
                SELECT 
                    supplier_clean as supplier,
                    SUM(amount_clean) as total_spent,
                    COUNT(*) as transaction_count,
                    AVG(amount_clean) as avg_transaction
                FROM data
                WHERE supplier_clean != 'Unknown' 
                  AND amount_clean > 0
                GROUP BY supplier_clean
                ORDER BY total_spent DESC
                LIMIT 20
            """).df()
            
            all_results.append(result)
            
        except Exception as e:
            app.logger.error(f'Database error with {file.filename}: {str(e)}', exc_info=True)
            # Don't return error immediately - try to process other files
            continue
        finally:
            # Always clean up temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)
    
    # ===== 4. COMBINE AND RETURN RESULTS =====
    if all_results:
        combined = pd.concat(all_results, ignore_index=True)
        
        # If multiple files, re-aggregate
        if len(all_results) > 1:
            combined = combined.groupby('supplier').agg({
                'total_spent': 'sum',
                'transaction_count': 'sum',
                'avg_transaction': 'mean'
            }).reset_index().sort_values('total_spent', ascending=False)
        
        return combined.to_json(orient='records')
    
    return jsonify([])

# ===== 5. ROOT ENDPOINT =====
@app.route('/')
def home():
    return jsonify({
        'status': 'running',
        'service': 'auditor-backend',
        'endpoints': {
            'health': '/health (GET)',
            'top_suppliers': '/api/top-suppliers (POST)'
        }
    })

# ===== 6. RUN THE APP =====
if __name__ == '__main__':
    app.run(debug=True, port=5000, host='0.0.0.0')