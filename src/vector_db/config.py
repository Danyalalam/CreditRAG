from dataclasses import dataclass
from dotenv import load_dotenv
import os
import sys
import logging

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

@dataclass
class PineconeConfig:
    api_key: str = os.getenv('PINECONE_API_KEY')
    index_name: str = os.getenv('PINECONE_INDEX_NAME')

    def __post_init__(self):
        missing = []
        if not self.api_key:
            missing.append('PINECONE_API_KEY')
        if not self.index_name:
            missing.append('PINECONE_INDEX_NAME')
        
        if missing:
            error_msg = f"Missing required environment variables: {', '.join(missing)}"
            logger.error(error_msg)
            sys.exit(error_msg)
        else:
            logger.info("All required Pinecone configuration variables are loaded successfully.")