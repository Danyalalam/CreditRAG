import streamlit as st
import uuid
from manager import PineconeManager
from config import PineconeConfig
import re

# Initialize Pinecone Manager
try:
    config = PineconeConfig()
    pinecone_manager = PineconeManager(config)
except Exception as e:
    st.error(f"Failed to initialize Pinecone Manager: {str(e)}")
    st.stop()

def sanitize_gmail(gmail: str) -> str:
    """
    Sanitizes a Gmail address to create a valid Pinecone namespace.
    Replaces '@' with '_at_' and '.' with '_dot_'.

    Args:
        gmail (str): The user's Gmail address.

    Returns:
        str: A sanitized string suitable for use as a Pinecone namespace.
    """
    sanitized = gmail.lower()
    sanitized = re.sub(r'@', '_at_', sanitized)
    sanitized = re.sub(r'\.', '_dot_', sanitized)
    return sanitized

st.title("Pinecone Manager Testing App")

user_gmail = st.text_input("Enter your Gmail address:", "helloworld45@gmail.com")

namespace = f"credit-reports-{sanitize_gmail(user_gmail)}"

# Initialize session state for vector IDs
if 'vector_ids' not in st.session_state:
    st.session_state.vector_ids = []

st.header(f"Namespace: {namespace}")

# Create Namespace
if st.button("Create Namespace"):
    try:
        pinecone_manager.create_namespace(namespace)
        # Retrieve the dummy vector's ID by querying with dummy values
        query_vector = [0.0] * pinecone_manager.dimension
        results = pinecone_manager.query_vectors(query_vector, namespace, top_k=1)
        dummy_vector_id = results['matches'][0]['id'] if results['matches'] else None
        if dummy_vector_id:
            st.session_state.vector_ids.append(dummy_vector_id)
            st.success(f"Namespace '{namespace}' created with dummy vector ID: {dummy_vector_id}")
        else:
            st.warning("Dummy vector not found. Namespace might not be created correctly.")
    except Exception as e:
        st.error(f"Error creating namespace: {str(e)}")

# List Namespaces
if st.button("List Namespaces"):
    try:
        namespaces = pinecone_manager.list_namespaces()
        st.write("Existing Namespaces:", namespaces)
    except Exception as e:
        st.error(f"Error listing namespaces: {str(e)}")

# Upsert Vectors
if st.button("Upsert Vectors"):
    try:
        vectors = [
            {
                'id': str(uuid.uuid4()),
                'values': [0.1] * pinecone_manager.dimension,
                'metadata': {'source': 'transunion'}
            },
            {
                'id': str(uuid.uuid4()),
                'values': [0.2] * pinecone_manager.dimension,
                'metadata': {'source': 'equifax'}
            }
        ]
        pinecone_manager.upsert_vectors(vectors, namespace)
        st.session_state.vector_ids.extend([v['id'] for v in vectors])
        st.success(f"Upserted {len(vectors)} vectors into namespace '{namespace}'.")
    except Exception as e:
        st.error(f"Error upserting vectors: {str(e)}")

# Query Vectors
if st.button("Query Vectors"):
    try:
        query_vector = [0.1] * pinecone_manager.dimension  # Ensure query vector matches index dimension
        results = pinecone_manager.query_vectors(query_vector, namespace, top_k=2)
        if results.get('matches'):
            st.write("Query Results:")
            for match in results['matches']:
                st.write(f"ID: {match['id']}, Score: {match['score']}, Metadata: {match['metadata']}")
        else:
            st.write("No matching vectors found.")
    except Exception as e:
        st.error(f"Error querying vectors: {str(e)}")

# Delete Vector
if st.button("Delete Vector"):
    try:
        if st.session_state.vector_ids:
            id_to_delete = st.session_state.vector_ids.pop(0)
            pinecone_manager.delete_vectors([id_to_delete], namespace)
            st.success(f"Deleted vector with ID: {id_to_delete}")
        else:
            st.warning("No vectors available to delete.")
    except Exception as e:
        st.error(f"Error deleting vector: {str(e)}")

# Delete Namespace
if st.button("Delete Namespace"):
    try:
        pinecone_manager.delete_namespace(namespace)
        st.session_state.vector_ids = []
        st.success(f"Deleted namespace '{namespace}'.")
    except Exception as e:
        st.error(f"Error deleting namespace: {str(e)}")