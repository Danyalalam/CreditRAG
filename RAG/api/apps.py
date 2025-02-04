import streamlit as st
import requests
import json

# Set your Django API base URL (adjust if necessary)
api_base = "http://localhost:8000/api"

st.title("CreditRAG Dispute System")

# --- 1. Upload Report & Auto-Populate Fields ---
st.markdown("### 1. Upload JSON Credit Report")
uploaded_file = st.file_uploader("Upload your credit report (JSON file)", type=["json"])
if uploaded_file is not None:
    files = {"file": uploaded_file}
    r = requests.post(f"{api_base}/upload-report/", files=files)
    if r.status_code == 200:
        response_data = r.json()
        st.success(response_data.get("message", "Report uploaded successfully."))
        # Automatically populate the fields using returned extraction data
        st.session_state["extracted_account_details"] = json.dumps(
            response_data.get("extracted_account_details", {}), indent=2
        )
        st.session_state["extracted_disputed_accounts"] = json.dumps(
            response_data.get("extracted_disputed_accounts", []), indent=2
        )
        st.session_state["default_account_category"] = response_data.get("default_account_category", "generic_dispute")
    else:
        st.error("Upload failed: " + r.json().get("error", "Unknown error"))

# --- 2. Categorize Accounts ---
st.markdown("### 2. Categorize Accounts")
with st.form("categorize_form"):
    st.write("Enter comma-separated values for each field:")
    account_status = st.text_input("Account Status(es)", value="delinquent, derogatory")
    payment_days = st.text_input("Payment Days", value="45,30")
    creditor_remark = st.text_input("Creditor Remark(s)", value="Late fee dispute, Incorrect reporting")
    submitted_categorize = st.form_submit_button("Categorize Accounts")
    
    if submitted_categorize:
        params = {
            "account_status": [s.strip() for s in account_status.split(",") if s.strip()],
            "payment_days": [s.strip() for s in payment_days.split(",") if s.strip()],
            "creditor_remark": [s.strip() for s in creditor_remark.split(",") if s.strip()]
        }
        r_categorize = requests.get(f"{api_base}/categorize-accounts/", params=params)
        if r_categorize.status_code == 200:
            st.json(r_categorize.json())
        else:
            st.error("Error: " + r_categorize.json().get("error", "Unknown error"))

# --- 3. Generate Dispute Letter ---
st.markdown("### 3. Generate Dispute Letter (Markdown)")
with st.form("generate_dispute_form"):
    st.write("Review or update the pre-populated JSON data below")
    account_details_text = st.text_area(
        "Account Details (JSON)",
        value=st.session_state.get(
            "extracted_account_details",
            '{"your_name": "John Doe", "your_address": "123 Main St", "city_state_zip": "", "credit_bureau_name": "Experian"}'
        ),
        height=150
    )
    account_category = st.text_input(
        "Account Category", 
        value=st.session_state.get("default_account_category", "delinquent_late_account")
    )
    disputed_accounts_text = st.text_area(
        "Disputed Accounts (JSON)",
        value=st.session_state.get("extracted_disputed_accounts", '[]'),
        height=150
    )
    submitted_letter = st.form_submit_button("Generate Markdown Letter")
    if submitted_letter:
        try:
            account_details = json.loads(account_details_text)
            disputed_accounts = json.loads(disputed_accounts_text)
        except Exception as e:
            st.error("Invalid JSON input: " + str(e))
        else:
            payload = {
                "account_details": account_details,
                "account_category": account_category,
                "disputed_accounts": disputed_accounts
            }
            r_md = requests.post(f"{api_base}/generate-dispute/", json=payload)
            if r_md.status_code == 200:
                markdown_letter = r_md.json().get("dispute_markdown", "")
                st.markdown(markdown_letter, unsafe_allow_html=True)
            else:
                st.error("Error: " + r_md.text)