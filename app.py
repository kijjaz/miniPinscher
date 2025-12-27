import streamlit as st
import pandas as pd
import io
from engine import IFRAEngine

# Page Config
st.set_page_config(
    page_title="miniPinscher | IFRA 51st Compliance",
    page_icon="🐕",
    layout="wide"
)

# Initialize Engine
@st.cache_resource
def get_engine():
    return IFRAEngine()

engine = get_engine()

# --- CSS STYLING ---
st.markdown("""
<style>
    .report-card {
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 20px;
        border-left: 5px solid #ff4b4b;
        background-color: #1e1e1e;
        color: #ffffff;
    }
    .pass-card {
        border-left: 5px solid #28a745;
    }
    [data-testid="stMetric"] {
        background-color: #262730;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #464b5d;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# --- HEADER ---
st.title("🐕 miniPinscher | IFRA Compliance Engine")
st.caption("v2.3 | Powered by Aromatic Data Intelligence | 51st Amendment (Category 4)")


# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Application Settings")
    dosage = st.slider("Finished Product Dosage (%)", 0.1, 100.0, 20.0, step=0.1, help="The concentration of the concentrate in your final product (e.g., 20% for EDP).")
    
    st.divider()
    st.info("💡 **Tip**: Enter your formula in grams or parts. The engine automatically scales everything based on the dosage above.")
    
    if st.button("Reset Session"):
        st.session_state.clear()
        st.rerun()

# --- INPUT SECTION ---
tabs = st.tabs(["📄 Batch Upload (CSV)", "⌨️ Quick Entry (Manual)"])

formula = []

with tabs[0]:
    uploaded_file = st.file_uploader("Upload your Formula (CSV or Excel)", type=["csv", "xlsx"])
    if uploaded_file:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            
            # Show complete formula
            cols = df.columns.tolist()
            st.write("Full Formula Preview:")
            st.dataframe(df, width='stretch')
            
            name_col = st.selectbox("Material Name Column", cols, index=0 if 'name' in [c.lower() for c in cols] else 0)
            amount_col = st.selectbox("Amount Column", cols, index=1 if 'amount' in [c.lower() for c in cols] else (1 if len(cols) > 1 else 0))
            cas_col = st.selectbox("CAS Column (Optional)", ["None"] + cols, index=0)
            
            for _, row in df.iterrows():
                entry = {'name': row[name_col], 'amount': row[amount_col]}
                if cas_col != "None":
                    entry['cas'] = row[cas_col]
                formula.append(entry)
                
        except Exception as e:
            st.error(f"Error reading file: {e}")

with tabs[1]:
    # --- Example Loader ---
    EXAMPLE_VAL = (
        "Bergamot FCF oil Sicilian from PerfumersWorld, 15.0\n"
        "Lemon essential oil from PerfumersWorld, 5.0\n"
        "Rose Otto Fleuressence from PerfumersWorld, 3.0\n"
        "Jasmine Petal F-TEC from PerfumersWorld, 2.0\n"
        "Hedione from PerfumersWorld, 20.0\n"
        "Iso E Super from PerfumersWorld, 25.0\n"
        "Vertofix Couer from PerfumersWorld, 15.0\n"
        "Ethylene Brassylate from PerfumersWorld, 10.0\n"
        "Musk Ketone from PerfumersWorld, 4.8\n"
        "Alpha Damascone from PerfumersWorld, 0.1\n"
        "Butylated hydroxytoluene (bht) antioxidant from PerfumersWorld, 0.1"
    )
    
    if st.button("🧪 Load Complex Example (F-TEC & Furocoumarins)"):
        st.session_state['manual_input'] = EXAMPLE_VAL
        st.rerun()

    manual_input = st.text_area(
        "Paste Formula (Name, Amount)", 
        value=st.session_state.get('manual_input', ""),
        placeholder="Phenyl Ethyl Alcohol, 120\nHydroxycitronellal, 50.5\nLemon Oil, 10",
        height=300
    )
    
    if manual_input:
        st.session_state['manual_input'] = manual_input
        lines = manual_input.strip().split('\n')
        for line in lines:
            parts = line.split(',')
            if len(parts) >= 2:
                formula.append({'name': parts[0].strip(), 'amount': float(parts[1].strip())})

# --- CALCULATION & REPORTING ---
if formula and st.button("🚀 Calculate Compliance", type="primary"):
    with st.spinner("Analyzing Formula..."):
        data = engine.calculate_compliance(formula, finished_dosage=dosage)
        
        # High Level Status
        col1, col2, col3 = st.columns(3)
        
        status_color = "red" if not data['is_compliant'] else "green"
        status_text = "!!! FAIL !!!" if not data['is_compliant'] else "✓ PASS"
        
        with col1:
            st.metric("Overall Status", status_text, delta=None, delta_color="inverse" if not data['is_compliant'] else "normal")
        with col2:
            st.metric("Critical Component", data['critical_component'] or "N/A")
        with col3:
            st.metric("Max Safe Dosage", f"{round(data['max_safe_dosage'], 4)}%")

        # Warnings for missing materials
        if data['unresolved_materials']:
            st.warning(f"⚠️ **Missing Items**: The following materials were not found in the database and were ignored: {', '.join(data['unresolved_materials'])}")

        # Exceedance Message
        if not data['is_compliant']:
            st.error(f"🚨 **Safety Breach**: This formula at {dosage}% dosage exceeds IFRA limits. Recommended concentrate level: **{round(data['max_safe_dosage'], 4)}%**")
        else:
            st.success(f"✅ **Compliant**: This formula is safe for Category 4 at {dosage}% dosage.")

        # Detailed Table
        st.subheader("Detailed Breakdown")
        results_df = pd.DataFrame(data['results'])
        
        # Format table
        results_df = results_df[['pass', 'standard_name', 'concentration', 'limit', 'ratio', 'exceedance_perc', 'sources']]
        results_df.columns = ['Status', 'Standard Name', 'Conc (%)', 'Limit', 'Ratio', 'Exceed %', 'Source']
        
        def highlight_fail(s):
            if not s['Status']:
                return ['background-color: #9c2b2b; color: white; font-weight: bold'] * len(s)
            return [''] * len(s)

        # Convert Limit to string to avoid Arrow serialization errors with mixed types
        results_df['Limit'] = results_df['Limit'].astype(str)

        st.dataframe(
            results_df.style.apply(highlight_fail, axis=1).format({
                'Status': lambda x: "✗" if not x else "✓",
                'Conc (%)': "{:.4f}",
                'Ratio': "{:.2f}",
                'Exceed %': lambda x: f"{x}%" if x > 0 else "-"
            }),
            width='stretch',
            hide_index=True
        )
        
        # Phototoxicity Section
        st.divider()
        p_data = data['phototoxicity']
        p_status = "✅ PASS" if p_data['pass'] else "🚨 FAIL"
        st.write(f"**Phototoxicity Check**: {p_status} | **Sum of Ratios**: {p_data['sum_of_ratios']} (Limit: 1.0)")
        
        # Download Report
        buffer = io.StringIO()
        # Mocking the print to capture report
        import sys
        old_stdout = sys.stdout
        sys.stdout = buffer
        engine.generate_report(formula, finished_dosage=dosage)
        sys.stdout = old_stdout
        
        st.download_button(
            label="📄 Download Full Certificate (Text)",
            data=buffer.getvalue(),
            file_name="ifra_compliance_report.txt",
            mime="text/plain"
        )

elif not formula:
    st.info("👋 Welcome! Please upload a formula or enter one manually to begin.")
    
    # Feature Showcase
    with st.expander("✨ Features Overview"):
        st.markdown("""
        - **Recursive Resolution**: Resolves mixtures and Schiff bases automatically.
        - **Smart Exemption**: Bergamot FCF and distilled oils are handled with IFRA-compliant logic.
        - **Automatic Scaling**: No need to calculate percentages; just enter grams.
        - **Phototoxicity Focus**: Industry-standard Sum of Ratios calculation.
        """)
