import pandas as pd

# === UPDATE THIS PATH ===
file_path = r"D:\Corruption_Tracker\Sefton Council\sefton-council-supplier-spent-june-2023.csv"
# =========================

print("🔍 DEBUGGING CSV STRUCTURE")
print("="*60)

# 1. Show the raw lines
with open(file_path, 'r', encoding='latin-1') as f:
    lines = [line.rstrip() for line in f.readlines()]

print("\n1. FIRST 8 RAW LINES:")
for i, line in enumerate(lines[:8]):
    print(f"   Line {i}: {repr(line)}")

print("\n" + "="*60)
print("2. TESTING DIFFERENT STRATEGIES")
print("="*60)

# 2. Show what's failing now (YOUR ORIGINAL STRATEGY)
print("\n=== Strategy 1: Default (what's failing now) ===")
try:
    df1 = pd.read_csv(file_path, encoding='latin-1')
    print(f"✓ Read successful")
    print(f"   Columns: {df1.columns.tolist()}")
    print(f"   Shape: {df1.shape}")
    if df1.shape[0] > 0:
        print(f"   First data row:\n   {df1.iloc[0].to_dict()}")
except Exception as e:
    print(f"✗ Error: {e}")

print("\n" + "="*60)

# 3. Smart search for the real header
print("\n=== Strategy 2: Finding the Real Header ===")
potential_headers = []
header_keywords = ['supplier', 'amount', 'value', 'cost', 'department', 'payment', 'date', 'total']

for i, line in enumerate(lines[:10]):  # Check first 10 lines
    line_lower = str(line).lower()
    # Count how many header keywords this line contains
    keyword_matches = [kw for kw in header_keywords if kw in line_lower]
    
    if len(keyword_matches) >= 2:  # If line contains at least 2 header keywords
        potential_headers.append((i, line, keyword_matches))

if potential_headers:
    print("✅ Potential header lines found:")
    for line_num, line_text, matches in potential_headers:
        print(f"   Line {line_num}: {repr(line_text)}")
        print(f"      Contains keywords: {matches}")
        
        # Test reading with this skiprows value
        try:
            df_test = pd.read_csv(file_path, skiprows=line_num, encoding='latin-1', nrows=2)
            print(f"      Test with skiprows={line_num}:")
            print(f"      → Columns: {df_test.columns.tolist()}")
            if len(df_test) > 0:
                print(f"      → First row preview: {dict(df_test.iloc[0])}")
            print()
        except Exception as e:
            print(f"      ✗ Test failed: {e}\n")
else:
    print("❌ No clear header line found in first 10 lines.")
    print("   Showing raw first 5 lines as DataFrame:")
    try:
        df_raw = pd.read_csv(file_path, header=None, encoding='latin-1', nrows=5)
        print(df_raw.to_string(index=False))
    except Exception as e:
        print(f"   Error: {e}")

print("\n" + "="*60)
print("3. RECOMMENDATION")
print("="*60)

if potential_headers:
    # Pick the best candidate (usually the first one)
    best_line = potential_headers[0][0]
    print(f"\n🎯 RECOMMENDED FIX:")
    print(f"   Use: pd.read_csv(file_path, skiprows={best_line}, encoding='latin-1')")
    print(f"\n   This skips the first {best_line} lines (0 through {best_line-1})")
    print(f"   and uses Line {best_line} as the column headers.")
else:
    print("\n❓ MANUAL INSPECTION NEEDED")
    print("   Run this to see more lines:")
    print("   for i, line in enumerate(lines[:15]): print(f'Line {i}: {repr(line)}')")