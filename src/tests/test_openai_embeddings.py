from langchain_openai import AzureOpenAIEmbeddings
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
text = "Hello World!"
embeddings = AzureOpenAIEmbeddings(
    deployment="text-embedding-ada-002",  # Add your Azure deployment name
    model="text-embedding-ada-002",
    azure_endpoint="https://langrag.openai.azure.com/",
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    api_version="2023-05-15"  # Make sure to use the correct API version
)
text_embedding = embeddings.embed_query(text)
print(text_embedding)