from pinecone import Pinecone, ServerlessSpec
from langchain_pinecone import PineconeVectorStore
import os
from uuid import uuid4
from typing import List
from langchain_core.documents import Document

class PineconeManager:
    def __init__(self, embeddings):
        pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
        
        # Initialize index
        index_name = os.getenv("PINECONE_INDEX")
        existing_indexes = [index_info["name"] for index_info in pc.list_indexes()]
        
        if index_name not in existing_indexes:
            pc.create_index(
                name=index_name,
                dimension=1536,  # Azure OpenAI ada-002 dimension
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1")
            )
        
        self.index = pc.Index(index_name)
        self.vector_store = PineconeVectorStore(
            index=self.index,
            embedding=embeddings
        )

    def upsert_documents(self, documents: List[Document], namespace: str):
        try:
            ids = [str(uuid4()) for _ in range(len(documents))]
            self.vector_store.add_documents(
                documents=documents,
                ids=ids,
                namespace=namespace
            )
            print(f"Successfully uploaded {len(documents)} documents to namespace: {namespace}")
            return True
        except Exception as e:
            print(f"Error uploading documents: {str(e)}")
            return False

    def similarity_search(self, query: str, namespace: str, k=5):
        return self.vector_store.similarity_search(
            query=query,
            k=k,
            namespace=namespace
        )