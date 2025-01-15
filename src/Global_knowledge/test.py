from document_loader import RegulationLoader
from embeddings import EmbeddingManager
from vectordb import PineconeManager
import asyncio
from dotenv import load_dotenv
import os
import time
from typing import List
from langchain_core.documents import Document

load_dotenv()

async def process_in_batches(docs: List[Document], pinecone_manager: PineconeManager, reg_type: str, batch_size: int = 50):
    total_docs = len(docs)
    for i in range(0, total_docs, batch_size):
        batch = docs[i:i + batch_size]
        print(f"Processing batch {i//batch_size + 1} of {(total_docs + batch_size - 1)//batch_size}")
        
        retries = 3
        while retries > 0:
            try:
                success = pinecone_manager.upsert_documents(batch, namespace=reg_type)
                if success:
                    print(f"Successfully processed batch of {len(batch)} documents")
                    break
            except Exception as e:
                print(f"Error processing batch: {str(e)}")
                retries -= 1
                if retries > 0:
                    print(f"Retrying in 60 seconds... ({retries} retries left)")
                    time.sleep(60)
                else:
                    print("Failed to process batch after all retries")
                    raise
        
        # Rate limiting - wait between batches
        if i + batch_size < total_docs:
            print("Waiting 30 seconds before next batch...")
            time.sleep(30)

async def process_regulations():
    loader = RegulationLoader()
    embedding_manager = EmbeddingManager()
    pinecone_manager = PineconeManager(embedding_manager.embeddings)

    regulations = {
        # "FDCPA": "src/data/fair-debt-collection-practices-act.pdf",
        # "FCRA": "src/data/fcra.pdf",
        "METRO2": "src/data/Metro-2.pdf"
    }

    for reg_type, file_path in regulations.items():
        print(f"Processing {reg_type} document...")
        if os.path.exists(file_path):
            docs = await loader.load_pdf(file_path, reg_type)
            print(f"Loaded {len(docs)} documents, processing in batches...")
            await process_in_batches(docs, pinecone_manager, reg_type)
            print(f"Completed processing {reg_type}")
        else:
            print(f"File not found: {file_path}")

if __name__ == "__main__":
    asyncio.run(process_regulations())