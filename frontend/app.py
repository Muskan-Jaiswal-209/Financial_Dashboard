import streamlit as st
import pandas as pd
import requests
import io

import os

# Setup backend host configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

st.set_page_config(page_title="Financial Suite", page_icon="📈", layout="wide")

# CSS to override and force modern 'Inter' typography and layout
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    html, body, [class*="css"], .stApp {
        font-family: 'Inter', sans-serif;
        background-color: #FFFFFF !important;
        color: #0F172A !important;
    }
    .main-nav {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 1.2rem 2.2rem;
        background-color: #F8FAFC;
        border-bottom: 1px solid #E2E8F0;
        border-radius: 8px;
        margin-bottom: 1.8rem;
    }
    .stButton>button {
        background-color: #0F172A !important;
        color: #FFFFFF !important;
        font-weight: 500 !important;
        border-radius: 6px !important;
        border: 1px solid #0F172A !important;
    }
    .stButton>button:hover {
        background-color: #1E293B !important;
    }
    </style>
""", unsafe_allow_html=True)

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.role = ""

# --- LOGIN CONTAINER ---
if not st.session_state.logged_in:
    st.markdown("<div style='text-align: center; margin-top: 6rem;'>", unsafe_allow_html=True)
    st.title("🔒 Corporate Financial Portal")
    st.markdown("Use registered phone credentials to sign in to your workspace.")
    
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        with st.form("auth_form"):
            phone = st.text_input("🔑 Phone Number", placeholder="e.g., 9876543210")
            password = st.text_input("🔑 Password", type="password", placeholder="••••••••")
            submit = st.form_submit_button("Sign In Securely")
            
            if submit:
                try:
                    response = requests.post(f"{BACKEND_URL}/api/auth/login", json={"phone": phone, "password": password})
                    if response.status_code == 200:
                        data = response.json()
                        st.session_state.logged_in = True
                        st.session_state.username = data["username"]
                        st.session_state.role = data["role"]
                        st.rerun()
                    else:
                        st.error("Invalid phone number or password. Try standard credentials.")
                except Exception:
                    st.error("Backend Connection Error. Please verify backend is running on Port 8000.")
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# --- DYNAMIC GLOBAL NAVIGATION ---
st.markdown(f"""
    <div class="main-nav">
        <div style="font-size: 1.2rem; font-weight: 700; color: #0F172A;">📊 FIN-CORE SYNC</div>
        <div style="font-size: 0.9rem; color: #475569;">
            Active Session: <strong>{st.session_state.username} ({st.session_state.role})</strong>
        </div>
    </div>
""", unsafe_allow_html=True)

if st.button("← Logout / Disconnect"):
    st.session_state.logged_in = False
    st.rerun()

st.write("---")

# --- INTERFACE A: USER PORTAL ---
if st.session_state.role == "User Dashboard":
    st.subheader("📝 Daily Operations Form")
    
    # Process dynamic Excel file import
    uploaded_file = st.file_uploader("Drop operational sheets (Excel formats)", type=["xlsx", "xls"])
    
    initial_entries = [
        {"particulars": "Opening Balance (A)", "category": "Balance", "amount": 0.0},
        {"particulars": "Sales Volume (in MT)", "category": "Sales", "amount": 0.0},
        {"particulars": "Sales Avg Rate", "category": "Sales", "amount": 0.0},
        {"particulars": "Total Sales in Rs.", "category": "Sales", "amount": 0.0},
        {"particulars": "Total Expenses", "category": "Expenses", "amount": 0.0}
    ]
    df_form = pd.DataFrame(initial_entries)
    
    if uploaded_file is not None:
        files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        response = requests.post(f"{BACKEND_URL}/api/user/parse-excel", files=files)
        if response.status_code == 200:
            imported_entries = response.json()["entries"]
            if imported_entries:
                df_form = pd.DataFrame(imported_entries)
                st.success("Successfully parsed spreadsheet mapping template!")
        else:
            st.error("Failed parsing specific excel structure layout.")

    # Render Editable Interface Matrix Grid
    st.markdown("### 🎛️ Dynamic Data Matrix")
    edited_df = st.data_editor(
        df_form,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "particulars": st.column_config.TextColumn("Financial Line Item"),
            "category": st.column_config.SelectboxColumn("Group Category", options=["Balance", "Sales", "Receipts", "Expenses"]),
            "amount": st.column_config.NumberColumn("Amount (Rs.) / Value", format="%.2f")
        }
    )
    
    if st.button("📤 Sync Data to Master Hub"):
        payload = {
            "username": st.session_state.username,
            "entries": edited_df.to_dict(orient="records")
        }
        res = requests.post(f"{BACKEND_URL}/api/user/sync", json=payload)
        if res.status_code == 200:
            st.success("Branch reporting synchronization completed successfully!")
        else:
            st.error("Synchronization failed.")

# --- INTERFACE B: EXECUTIVE PORTAL ---
else:
    st.subheader("🛡️ Executive Consolidated Master Hub")
    
    try:
        response = requests.get(f"{BACKEND_URL}/api/master/summary")
        if response.status_code == 200:
            data = response.json()
            totals = data["totals"]
            entries = data["entries"]
            
            # Master Dashboard KPI Panels
            kpi1, kpi2, kpi3 = st.columns(3)
            kpi1.metric("Consolidated Volume (MT)", f"{totals['volume']:,.2f}")
            kpi2.metric("Gross Revenue Receipts", f"₹ {totals['sales']:,.2f}")
            kpi3.metric("Total Expenses Outflow", f"₹ {totals['expenses']:,.2f}")
            
            st.markdown("### 📋 Consolidation Output Grid (Sheet 2 Equivalent)")
            if entries:
                master_df = pd.DataFrame(entries)
                st.dataframe(master_df, use_container_width=True)
                
                # Dynamic Excel Downloader Engine
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    master_df.to_excel(writer, sheet_name='Master Dashboard Data', index=False)
                    
                st.download_button(
                    label="📥 Export Consolidated Report (.xlsx)",
                    data=buffer.getvalue(),
                    file_name="Master_Consolidation_Report.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.info("No branches have completed synchronization reports for this current operating period.")
        else:
            st.error("Failed to query consolidated records.")
    except Exception:
        st.error("Could not retrieve master database datasets. Verify Backend API availability.")