from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
import asyncio
from typing import List
from langchain_core.documents import Document

class RegulationLoader:
    def __init__(self):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=100,
            separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""]
        )

    async def load_pdf(self, file_path: str, regulation_type: str) -> List[Document]:
        loader = PyPDFLoader(file_path)
        pages = []
        async for page in loader.alazy_load():
            page.metadata.update({
                "regulation_type": regulation_type,
                "source": file_path,
                "page": len(pages) + 1
            })
            pages.append(page)
        
        split_docs = self.text_splitter.split_documents(pages)
        return split_docs