import json
import logging
import uuid
import re
from manager import PineconeManager
from config import PineconeConfig

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

def main(user_gmail: str):
    config = PineconeConfig()
    pinecone_manager = PineconeManager(config)

    namespace = f"credit-reports-{sanitize_gmail(user_gmail)}"  # Dynamic namespace based on sanitized Gmail

    # Create Namespace
    pinecone_manager.create_namespace(namespace)

    # List Namespaces
    namespaces = pinecone_manager.list_namespaces()
    print(f"Existing Namespaces: {namespaces}")

    # Upsert Vectors
    vectors = [
        {
            'id': str(uuid.uuid4()),
            'values': [0.1] * 1536,  # Ensure vectors match index dimension
            'metadata': {'source': 'transunion'}
        },
        {
            'id': str(uuid.uuid4()),
            'values': [0.2] * 1536,
            'metadata': {'source': 'equifax'}
        }
    ]
    pinecone_manager.upsert_vectors(vectors, namespace)

    # Query Vectors
    query_vector = [0.1] * 1536  # Ensure query vector matches index dimension
    results = pinecone_manager.query_vectors(query_vector, namespace, top_k=2)
    print("Query Results:", results)

    # Delete Vectors
    ids_to_delete = [vectors[0]['id']]
    pinecone_manager.delete_vectors(ids_to_delete, namespace)
    print(f"Deleted vectors with IDs: {ids_to_delete}")

    # Delete Namespace (Optional)
    # pinecone_manager.delete_namespace(namespace)
    # print(f"Deleted namespace '{namespace}'.")

if __name__ == "__main__":
    # Example Gmail addresses
    user_gmail = "helloworld45@gmail.com"  
    main(user_gmail)