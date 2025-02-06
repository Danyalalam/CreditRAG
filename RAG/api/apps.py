import streamlit as st
import requests
import json
from PyPDF2 import PdfReader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import OpenAIEmbeddings
from pinecone import Pinecone, ServerlessSpec
import os
from dotenv import load_dotenv
import uuid

# Load environment variables
load_dotenv()

# Initialize Pinecone with new API style
pc = Pinecone(api_key=os.getenv('PINECONE_API_KEY'))
index_name = "credit"  # Changed to match your index name

# Ensure index exists or create it
if index_name not in pc.list_indexes().names():
    pc.create_index(
        name=index_name,
        dimension=1536,  # OpenAI embeddings dimension
        metric='cosine',
        spec=ServerlessSpec(
            cloud='aws',
            region='us-east-1'  # Updated to match your region
        )
    )

# Get the index reference
index = pc.Index(index_name)

# Set your Django API base URL (adjust if necessary)
api_base = "http://localhost:8000/api"

st.title("CreditRAG Dispute System")

# --- 0. Upload Knowledge Base Files ---
st.markdown("### 0. Upload Knowledge Base")
knowledge_files = st.file_uploader(
    "Upload credit bureau rules and regulations (PDF files)", 
    type=["pdf"],
    accept_multiple_files=True
)

def process_pdf(pdf_file):
    """Process a PDF file and return chunks with metadata"""
    pdf_reader = PdfReader(pdf_file)
    text_chunks = []
    
    for page_num, page in enumerate(pdf_reader.pages, 1):
        text = page.extract_text()
        if text.strip():  # Only process non-empty pages
            text_chunks.append({
                'text': text,
                'metadata': {
                    'filename': pdf_file.name,
                    'page_number': page_num
                }
            })
    return text_chunks

def chunk_text(text_chunks, chunk_size=500, chunk_overlap=50):
    """Split text into smaller chunks with overlap"""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len
    )
    
    processed_chunks = []
    for chunk in text_chunks:
        splits = text_splitter.split_text(chunk['text'])
        for split in splits:
            processed_chunks.append({
                'text': split,
                'metadata': chunk['metadata']
            })
    return processed_chunks

def upload_to_pinecone(chunks):
    """Upload chunks to Pinecone with metadata"""
    embeddings_model = OpenAIEmbeddings()
    
    batch_size = 100
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        ids = [str(uuid.uuid4()) for _ in batch]
        texts = [chunk['text'] for chunk in batch]
        metadata = [chunk['metadata'] for chunk in batch]
        
        # Create embeddings for the batch
        embeds = embeddings_model.embed_documents(texts)
        
        # Create records for Pinecone
        vectors_to_upsert = []
        for id, embed, meta in zip(ids, embeds, metadata):
            vectors_to_upsert.append({
                'id': id,
                'values': embed,
                'metadata': meta
            })
        
        # Upsert to Pinecone
        index.upsert(vectors=vectors_to_upsert)
    
    return len(chunks)

if knowledge_files:
    with st.spinner('Processing knowledge base files...'):
        total_chunks = 0
        for file in knowledge_files:
            try:
                # Process each PDF
                text_chunks = process_pdf(file)
                # Split into smaller chunks with overlap
                processed_chunks = chunk_text(text_chunks)
                # Upload to Pinecone
                chunks_uploaded = upload_to_pinecone(processed_chunks)
                total_chunks += chunks_uploaded
                st.success(f'Successfully processed {file.name} and uploaded chunks to knowledge base.')
            except Exception as e:
                st.error(f'Error processing {file.name}: {str(e)}')
                continue
            
        st.success(f'Total files processed: {len(knowledge_files)}, Total chunks uploaded: {total_chunks}')

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
        st.session_state["default_account_category"] = response_data.get("default_account_category", "generic_dispute")
    else:
        st.error("Upload failed: " + r.json().get("error", "Unknown error"))

# --- 2. Categorize Accounts ---
st.markdown("### 2. Categorize Accounts")
with st.form("categorize_form"):
    st.write("Enter comma-separated values for each field based on the following defaults using our rules:")
    st.markdown("""
    **Defaults:**
    - **Account Status(es):** current, charge-off, inquiry, past_due, public record  
    - **Payment Days:** 0, 0, 0, 30_days_late, 0  
    - **Creditor Remark(s):** none, collection reported, none, none, none  
    """)
    account_status = st.text_input(
        "Account Status(es)", 
        value="current, charge-off, inquiry, past_due, public record"
    )
    payment_days = st.text_input(
        "Payment Days", 
        value="0, 0, 0, 30, 0"
    )
    creditor_remark = st.text_input(
        "Creditor Remark(s)", 
        value="none, collection reported, none, none, none"
    )
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
    # Removed the Disputed Accounts field since it's no longer needed.
    submitted_letter = st.form_submit_button("Generate Markdown Letter")
    if submitted_letter:
        try:
            account_details = json.loads(account_details_text)
        except Exception as e:
            st.error("Invalid JSON input: " + str(e))
        else:
            payload = {
                "account_details": account_details,
                "account_category": account_category
            }
            r_md = requests.post(f"{api_base}/generate-dispute/", json=payload)
            if r_md.status_code == 200:
                markdown_letter = r_md.json().get("dispute_markdown", "")
                st.markdown(markdown_letter, unsafe_allow_html=True)
            else:
                st.error("Error: " + r_md.text)