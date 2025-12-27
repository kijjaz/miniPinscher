import pandas as pd
import json

def audit_standards():
    print("Starting Data Extraction Audit...")
    
    # 1. Load Source Excel
    try:
        df_excel = pd.read_excel('ifra-51st-amendment-ifra-standards-overview.xlsx', header=2)
    except Exception as e:
        print(f"Error loading Excel: {e}")
        return

    # 2. Load Generated JSON
    try:
        with open('standards_optimized.json', 'r') as f:
            data_json = json.load(f)
            standards_json = data_json['metadata']
    except Exception as e:
        print(f"Error loading JSON: {e}")
        return

    issues = []
    processed_count = 0
    match_count = 0

    print(f"{'ID':<15} | {'Excel Raw':<20} | {'JSON Value':<10} | {'Status'}")
    print("-" * 60)

    for i, row in df_excel.iterrows():
        std_id = str(row.iloc[0]).strip()
        if not std_id.startswith('IFRA_STD'): continue
        
        processed_count += 1
        
        # Raw value from Excel (Col 22 - Category 4)
        raw_val = row.iloc[22]
        
        # Value from JSON
        json_entry = standards_json.get(std_id)
        if not json_entry:
            issues.append(f"{std_id}: Missing in JSON")
            continue
            
        json_val = json_entry.get('limit_cat4')

        # Logic to recreate "Expected" value
        expected_val = None
        is_spec_or_ban = False
        
        raw_str = str(raw_val).strip()
        
        if pd.isna(raw_val) or raw_str.lower() in ['nan', 'none', '']:
             # Empty in Excel -> Should be None in JSON (unless it's a prohibition, but strict limit is None)
             expected_val = None
        elif "specification" in raw_str.lower() or "no restriction" in raw_str.lower():
             # "No Restriction" or "Specification" -> None
             expected_val = None
        elif "prohibition" in raw_str.lower() or "restriction" in raw_str.lower():
             # Text like "Prohibition" -> Usually 0.0 or None depending on logic? 
             # Wait, usually specific limits have numbers. Prohibited implies 0? 
             # Let's check how the extractor handles it.
             # The current extractor does float() conversion.
             # If it fails float conversion, it sets None.
             pass
        else:
            # Try parsing number
            try:
                # Mirroring the fix: replace comma with dot
                clean_str = raw_str.replace(',', '.')
                expected_val = float(clean_str)
            except:
                # If it fails to be a number (e.g. text note), extraction returns None.
                # We want to flag if this "text note" actually contained a number we missed.
                pass

        # COMPARISON
        # 1. Exact Match (accounting for float precision)
        is_match = False
        if json_val is None and expected_val is None:
            is_match = True
        elif json_val is not None and expected_val is not None:
            if abs(json_val - expected_val) < 0.00001:
                is_match = True
        
        # 2. Flag Issues
        if not is_match:
            # If Excel has a number but JSON is None -> FAIL
            if expected_val is not None and json_val is None:
               issues.append(f"{std_id}: Missed Limit. Excel='{raw_val}' -> Exp={expected_val}, JSON=None")
               print(f"{std_id:<15} | {str(raw_val):<20} | {str(json_val):<10} | ❌ MISSED")
            
            # If Mismatch
            elif expected_val is not None and json_val is not None:
               issues.append(f"{std_id}: Value Mismatch. Excel='{raw_val}' -> Exp={expected_val}, JSON={json_val}")
               print(f"{std_id:<15} | {str(raw_val):<20} | {str(json_val):<10} | ❌ MISMATCH")
            
            # If Excel is text/weird but JSON is None -> WARN (Manual check?)
            elif expected_val is None and json_val is None:
                # Check if raw value looks like a number but failed parsing
                if any(c.isdigit() for c in raw_str) and not "specification" in raw_str.lower():
                     print(f"{std_id:<15} | {str(raw_val):<20} | {str(json_val):<10} | ⚠️ CHECK (Text?)")
                else:
                     match_count += 1 # It's likely correct (Spec/Text -> None)
            else:
                 # Excel None, JSON Number? Unlikely
                 issues.append(f"{std_id}: Phantom Limit. Excel='{raw_val}', JSON={json_val}")
                 print(f"{std_id:<15} | {str(raw_val):<20} | {str(json_val):<10} | ❓ PHANTOM")
        else:
            match_count += 1

    print("-" * 60)
    print(f"Processed: {processed_count}")
    print(f"Matches: {match_count}")
    print(f"Issues Found: {len(issues)}")
    
    if issues:
        print("\n--- DETAILED ISSUES ---")
        for i in issues:
            print(i)

if __name__ == "__main__":
    audit_standards()
