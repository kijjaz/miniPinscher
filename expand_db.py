import pandas as pd
import os

SOURCE_CSV = "20251217 Kijjaz - miniChihuahua 0.1.7 - RawMaterials.csv"
TARGET_EXCEL = "DB_User_Materials_Optimized.xlsx"

def normalize_cas_value(val):
    if pd.isna(val) or val == '':
        return None
    return str(val).strip()

def main():
    print(f"Reading source CSV: {SOURCE_CSV}")
    try:
        source_df = pd.read_csv(SOURCE_CSV)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    print(f"Reading target Excel: {TARGET_EXCEL}")
    try:
        target_df = pd.read_excel(TARGET_EXCEL)
        existing_skus = set(target_df['SKU'].dropna().astype(str).str.strip().tolist())
        print(f"Found {len(existing_skus)} existing SKUs.")
    except Exception as e:
        print(f"Error reading Excel: {e}")
        return

    new_rows = []
    
    for i, row in source_df.iterrows():
        sku = str(row['Product_ID']).strip()
        mat_name = str(row['Material_Name']).strip()
        
        # Skip if already exists
        if sku in existing_skus:
            continue
            
        cas_raw = row['CAS_Number']
        price = row['Price_US/g']
        
        # Parse CAS/Composition logic
        # format appears to be multiline or special char separated: "cas|fraction"
        # The head command output showed: "5910-89-4|0.01\n25265-71-8|0.99" (or similar)
        
        if pd.isna(cas_raw):
            continue
            
        cas_entry_str = str(cas_raw)
        
        # Split by newline first if present
        components = []
        if '\n' in cas_entry_str:
            parts = cas_entry_str.split('\n')
            components.extend(parts)
        else:
            components.append(cas_entry_str)
            
        for comp in components:
            comp = comp.strip()
            if not comp: continue
            
            if '|' in comp:
                # Format: CAS|Fraction
                try:
                    c_cas, c_frac = comp.split('|')
                    c_cas = c_cas.strip()
                    c_perc = float(c_frac) * 100.0
                except:
                    print(f"Could not parse component '{comp}' for SKU {sku}")
                    continue
            else:
                # Simple CAS, assume 100% if not specified, 
                # BUT wait, regular items usually don't have fraction. 
                # Let's check Is_Dilution col? 
                # Actually, looking at the head output:
                # Row 1: 5910-89-4 -> No pipe.
                c_cas = comp.strip()
                c_perc = 100.0
            
            # Use Material Name as Constituent Name for the row, 
            # unless we want to try to infer it (hard).
            # The current Excel schema expects: SKU, Material Name, Constituent, CAS, Percentage
            
            new_rows.append({
                'SKU': sku,
                'Material Name': mat_name,
                'Constituent': mat_name, # Fallback, engine resolves by CAS anyway
                'CAS': c_cas,
                'Percentage': c_perc
            })

    if not new_rows:
        print("No new SKUs found to add.")
        return

    print(f"Adding {len(new_rows)} rows for new materials.")
    new_df = pd.DataFrame(new_rows)
    
    # Append
    final_df = pd.concat([target_df, new_df], ignore_index=True)
    
    # Save
    print(f"Saving updated database to {TARGET_EXCEL}...")
    final_df.to_excel(TARGET_EXCEL, index=False)
    print("Done.")

if __name__ == "__main__":
    main()
