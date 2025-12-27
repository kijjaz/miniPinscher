import pandas as pd
import json
import re

def normalize_cas(cas):
    if not cas or pd.isna(cas): return None
    clean = str(cas).strip().lower()
    if clean in ['nan', 'not applicable.', 'n/a', 'none', 'null', 'e.g.:']:
        return None
    return clean

def extract_standards():
    print("Extracting Standards (Optimized)...")
    df = pd.read_excel('ifra-51st-amendment-ifra-standards-overview.xlsx', header=2)
    
    metadata = {}
    cas_mapping = {}
    
    for i, row in df.iterrows():
        std_id = str(row.iloc[0]).strip()
        if not std_id.startswith('IFRA_STD'): continue
        
        name = str(row.iloc[6]).strip()
        cas_str = str(row.iloc[7])
        res_type = str(row.iloc[11]).strip()
        
        try:
            cat4_limit = row.iloc[24]
        except:
            cat4_limit = 100.0
            
        try:
            val = float(row[23])
            if pd.isna(val): limit = None
            else: limit = val
        except:
            limit = None # Treat "Specification" or invalid as None (No limit)
            
        metadata[std_id] = {
            "name": name,
            "type": row[11],
            "limit_cat4": limit
        }
        
        # Consistent CAS splitting and normalization
        cas_list = [normalize_cas(c) for c in re.split(r'[\n,|;]', str(cas_str))]
        for cas in cas_list:
            if cas:
                if cas not in cas_mapping:
                    cas_mapping[cas] = []
                if std_id not in cas_mapping[cas]:
                    cas_mapping[cas].append(std_id)
    
    with open('standards_optimized.json', 'w') as f:
        json.dump({
            'metadata': metadata,
            'cas_mapping': cas_mapping
        }, f, indent=4)
    print(f"Extracted {len(metadata)} standards and {len(cas_mapping)} unique CAS mappings.")

def extract_ncs_data():
    print("Extracting NCS (Consolidated)...")
    df = pd.read_excel('ifra-51st-amendment-annex-on-contributions-from-other-sources.xlsx', sheet_name='Natural contributions', header=6)
    
    # Handle merged cells in Excel
    df.iloc[:, [5, 3]] = df.iloc[:, [5, 3]].ffill()
    
    ncs_data = {}
    for i, row in df.iterrows():
        ncs_name = str(row.iloc[5]).strip()
        principal_cas = normalize_cas(row.iloc[3])
        const_cas = normalize_cas(row.iloc[7])
        const_name = str(row.iloc[8]).strip()
        percentage = row.iloc[9]
        
        if not principal_cas or not const_cas: continue
        
        if principal_cas not in ncs_data:
            ncs_data[principal_cas] = {'name': ncs_name, 'constituents': {}}
            
        try: 
            # Clean up percentage (sometimes contains spaces or weird chars like "0..3")
            clean_perc = str(percentage).replace('..', '.').strip()
            val = float(clean_perc)
        except: 
            val = 0.0
        
        # Consolidation: Take MAX constituent if duplicate rows (Conservative approach)
        # Prevents summation of multiple "typical/maximum" scenarios in the Annex
        mapping = ncs_data[principal_cas]['constituents']
        mapping[const_cas] = max(mapping.get(const_cas, 0.0), val)
        
    return ncs_data

def extract_schiff():
    print("Extracting Schiff Bases (Consolidated)...")
    df = pd.read_excel('ifra-51st-amendment-annex-on-contributions-from-other-sources.xlsx', sheet_name='Schiff bases', header=3)
    schiff_data = {}
    for i, row in df.iterrows():
        aldehyde_cas = normalize_cas(row.iloc[1])
        schiff_cas_str = str(row.iloc[3])
        percentage = row.iloc[4]
        
        if not aldehyde_cas: continue
        
        schiff_cas_list = [normalize_cas(c) for c in schiff_cas_str.split(';')]
        try: val = float(percentage)
        except: val = 0.0
            
        for s_cas in schiff_cas_list:
            if not s_cas: continue
            if s_cas not in schiff_data:
                schiff_data[s_cas] = {'name': 'Schiff Base', 'constituents': {}}
            schiff_data[s_cas]['constituents'][aldehyde_cas] = schiff_data[s_cas]['constituents'].get(aldehyde_cas, 0.0) + val
            
    return schiff_data

def extract_user_materials():
    print("Extracting User Materials (PerfumersWorld)...")
    # Read as string to avoid date corruption where possible, though openpyxl might still warn
    df = pd.read_excel('DB_User_Materials_Optimized.xlsx')
    user_contributions = {}
    
    # Solvent CAS Mapping
    SOLVENTS = {
        "DPG": "25265-71-8",
        "BB": "120-51-4",
        "TEC": "77-93-0",
        "IPM": "110-27-0",
        "DEP": "84-66-2",
        "EtOH": "64-17-5",
        "ETOH": "64-17-5",
        "Triethyl Citrate": "77-93-0",
        "Benzyl Benzoate": "120-51-4",
        "Dipropylene Glycol": "25265-71-8",
        "Isopropyl Myristate": "110-27-0"
    }
    
    # Common Name to CAS Fallback (Recovering data lost due to Excel date corruption)
    NAME_TO_CAS = {
        "benzyl benzoate": "120-51-4",
        "benzyl salicylate": "118-58-1",
        "benzyl alcohol": "100-51-6",
        "linalool": "78-70-6",
        "limonene": "5989-27-5",
        "citral": "5392-40-5",
        "geraniol": "106-24-1",
        "citronellol": "106-22-9",
        "eugenol": "97-53-0",
        "isoeugenol": "97-54-1",
        "coumarin": "91-64-5",
        "hexyl cinnamic aldehyde": "101-86-0",
        "lilial": "80-54-6",
        "lyral": "31906-04-4",
        "hydroxycitronellal": "107-75-5",
        "methyl ionone": "1335-46-2",
        "amyl cinnamic aldehyde": "122-40-7",
        "anise alcohol": "105-13-5",
        "cinnamyl alcohol": "104-54-1",
        "cinnamal": "104-55-2",
        "farnesol": "4602-84-0",
        "oakmoss": "90028-68-5",
        "treemoss": "90028-67-4"
    }
    
    # First pass: Group by material entries
    grouped_raw = {}
    for i, row in df.iterrows():
        sku = str(row['SKU']).strip()
        mat_name = str(row['Material Name']).strip()
        const_name = str(row['Constituent']).strip().lower()
        const_cas = normalize_cas(row['CAS'])
        percentage = row['Percentage']
        
        # Fallback for corrupted CAS
        if not const_cas and const_name in NAME_TO_CAS:
            const_cas = NAME_TO_CAS[const_name]
            # print(f"DEBUG: Recovered CAS {const_cas} for {const_name}")
            
        if not const_cas: continue
        try: val = float(percentage)
        except: val = 0.0
        
        group_key = (sku, mat_name)
        if group_key not in grouped_raw:
            grouped_raw[group_key] = {}
        
        # Take MAX if duplicate entries for SAME material (Avoid summing 100% + 100% duplicates)
        grouped_raw[group_key][const_cas] = max(grouped_raw[group_key].get(const_cas, 0.0), val)

    # Second pass: Smart Solvent Injection and Key Mapping
    for (sku, mat_name), constituents in grouped_raw.items():
        # Detect Dilution (e.g., "10% in DPG")
        # Pattern: [Number]% in [Solvent]
        match = re.search(r'(\d+)\s*%\s*in\s*([a-zA-Z\s]+)', mat_name, re.IGNORECASE)
        if match:
            perc_val = int(match.group(1))
            solvent_key = match.group(2).strip()
            
            # Resolve solvent CAS
            solvent_cas = None
            for s_name, s_cas in SOLVENTS.items():
                if s_name.lower() in solvent_key.lower():
                    solvent_cas = s_cas
                    break
            
            if solvent_cas:
                # If name says "10% in DPG", it means 90% is DPG
                # We inject exactly the 90% portion.
                solvent_injection = 100.0 - perc_val
                
                # In basic chemicals like "Aldehyde C-10 10% in DPG", 
                # C-10 is already 10%, so 10+90 = 100.
                # In Naturals like "Benzoin 50% in BB", 
                # the 50% resinoid part only has ~2% resolved bits.
                # So we add 50% BB to whatever was already there.
                constituents[solvent_cas] = constituents.get(solvent_cas, 0.0) + solvent_injection
                # print(f"DEBUG: Injected {solvent_injection}% {solvent_key} into {mat_name}")

        keys = [sku, mat_name.lower()]
        for key in keys:
            if not key or key == 'nan': continue
            if key not in user_contributions:
                user_contributions[key] = {'name': mat_name, 'constituents': {}}
            
            for c_cas, val in constituents.items():
                user_contributions[key]['constituents'][c_cas] = user_contributions[key]['constituents'].get(c_cas, 0.0) + val
            
            # Sum Normalization Cap (Fixing PW data realism)
            # If total sum of constituents > 100, scale them down proportionally to fit 100%.
            c_sum = sum(user_contributions[key]['constituents'].values())
            if c_sum > 100.0:
                scale = 100.0 / c_sum
                for c_cas in user_contributions[key]['constituents']:
                    user_contributions[key]['constituents'][c_cas] *= scale
                # print(f"DEBUG: Normalized {key} from {c_sum}% to 100%")
                
    return user_contributions

if __name__ == "__main__":
    extract_standards()
    ncs = extract_ncs_data()
    schiff = extract_schiff()
    user = extract_user_materials()
    
    # Merge everything into contributions_optimized.json
    contributions = ncs.copy()
    
    # Helper to merge dicts (Avoid double-counting if material exists in multiple sources)
    def merge_cont(target, source):
        for key, data in source.items():
            if key not in target:
                target[key] = data
            else:
                # If material already exists (e.g., in IFRA Annex), 
                # merge constituents by taking the MAX percentage to stay conservative.
                # Avoid summation which leads to percentages > 100%.
                for c_cas, c_val in data['constituents'].items():
                    target[key]['constituents'][c_cas] = max(target[key]['constituents'].get(c_cas, 0.0), c_val)

    merge_cont(contributions, schiff)
    merge_cont(contributions, user)
                
    with open('contributions_optimized.json', 'w') as f:
        json.dump(contributions, f, indent=4)
    print(f"Total optimized contributions entries: {len(contributions)}")
