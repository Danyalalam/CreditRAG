from typing import Dict, List, Optional
import logging
import uuid
from pinecone import Pinecone, ServerlessSpec
from config import PineconeConfig
from exceptions import ConnectionError, NamespaceError, VectorDBException

logger = logging.getLogger(__name__)

class PineconeManager:
    DEFAULT_DIMENSION = 1536  # Define a default dimension

    def __init__(self, config: PineconeConfig):
        self.config = config
        self.pc = self._connect()
        self.index = self._initialize_index()
        self.dimension = self._get_index_dimension()

    def _connect(self) -> Pinecone:
        """
        Initializes the Pinecone client by creating an instance of the Pinecone class.

        Returns:
            Pinecone: An instance of the Pinecone client.

        Raises:
            ConnectionError: If Pinecone client initialization fails.
        """
        try:
            pc = Pinecone(api_key=self.config.api_key)
            logger.info("Pinecone client initialized.")
            return pc
        except Exception as e:
            raise ConnectionError(f"Failed to initialize Pinecone client: {str(e)}")

    def _initialize_index(self) -> Pinecone.Index:
        """
        Initializes the Pinecone index. Creates it if it doesn't exist.

        Returns:
            Pinecone.Index: The initialized Pinecone index.

        Raises:
            ConnectionError: If index initialization fails.
        """
        try:
            existing_indexes_response = self.pc.list_indexes()
            # Extract index names based on the Pinecone client response structure
            if hasattr(existing_indexes_response, 'names') and callable(existing_indexes_response.names):
                existing_indexes = existing_indexes_response.names()
            elif isinstance(existing_indexes_response, list):
                existing_indexes = existing_indexes_response
            else:
                # Handle unexpected response structure
                raise ConnectionError("Unexpected response structure from list_indexes()")
            
            logger.debug(f"Existing indexes: {existing_indexes}")
            
            if self.config.index_name not in existing_indexes:
                self.pc.create_index(
                    name=self.config.index_name,
                    dimension=self.DEFAULT_DIMENSION, 
                    metric='cosine',
                    spec=ServerlessSpec(
                        cloud='aws',
                        region='us-east-1'
                    )
                )
                logger.info(f"Created Pinecone index: {self.config.index_name}")
            
            index = self.pc.Index(self.config.index_name)
            logger.info(f"Connected to Pinecone index: {self.config.index_name}")
            return index
        except ConnectionError:
            raise  # Re-raise connection errors
        except Exception as e:
            raise ConnectionError(f"Failed to initialize Pinecone index: {str(e)}")

    def _get_index_dimension(self) -> int:
        """
        Retrieves the dimension of the Pinecone index.

        Returns:
            int: The dimension of the index.

        Raises:
            ConnectionError: If unable to retrieve index dimension.
        """
        try:
            index_info = self.index.describe_index_stats()
            dimension = index_info.get('dimension')
            if not dimension:
                raise ConnectionError("Unable to retrieve index dimension.")
            logger.info(f"Index '{self.config.index_name}' has dimension: {dimension}")
            return dimension
        except Exception as e:
            raise ConnectionError(f"Failed to retrieve index dimension: {str(e)}")

    def create_namespace(self, namespace: str) -> None:
        """
        Creates a namespace by upserting a dummy vector.

        Args:
            namespace (str): The name of the namespace to create.

        Raises:
            NamespaceError: If namespace creation fails.
        """
        try:
            dummy_vector = {
                'id': str(uuid.uuid4()),
                'values': [1.0] + [0.0] * (self.dimension - 1),  # First value is non-zero
                'metadata': {'source': 'dummy'}
            }
            self.upsert_vectors([dummy_vector], namespace)
            logger.info(f"Namespace '{namespace}' created with a dummy vector.")
        except Exception as e:
            raise NamespaceError(f"Failed to create namespace '{namespace}': {str(e)}")

    def list_namespaces(self) -> List[str]:
        """
        Lists all namespaces in the Pinecone index.

        Returns:
            List[str]: A list of namespace names.

        Raises:
            NamespaceError: If listing namespaces fails.
        """
        try:
            index_stats = self.index.describe_index_stats()
            namespaces = list(index_stats.get('namespaces', {}).keys())
            logger.info(f"Retrieved namespaces: {namespaces}")
            return namespaces
        except Exception as e:
            raise NamespaceError(f"Failed to list namespaces: {str(e)}")

    def delete_namespace(self, namespace: str) -> None:
        """
        Deletes a namespace and all its vectors.

        Args:
            namespace (str): The name of the namespace to delete.

        Raises:
            NamespaceError: If deleting the namespace fails.
        """
        try:
            self.index.delete(delete_all=True, namespace=namespace)
            logger.info(f"Deleted namespace '{namespace}'.")
        except Exception as e:
            raise NamespaceError(f"Failed to delete namespace '{namespace}': {str(e)}")

    def upsert_vectors(self, vectors: List[Dict], namespace: str) -> None:
        """
        Upserts vectors into a specified namespace.

        Args:
            vectors (List[Dict]): A list of vectors to upsert.
            namespace (str): The target namespace.

        Raises:
            VectorDBException: If upserting vectors fails.
        """
        try:
            self.index.upsert(vectors=vectors, namespace=namespace)
            logger.info(f"Upserted {len(vectors)} vectors into namespace '{namespace}'.")
        except Exception as e:
            raise VectorDBException(f"Failed to upsert vectors: {str(e)}")

    def query_vectors(self, query_vector: List[float], namespace: str, top_k: int = 5) -> Dict:
        """
        Queries vectors in a specified namespace.

        Args:
            query_vector (List[float]): The vector to query against.
            namespace (str): The namespace to query within.
            top_k (int, optional): Number of top results to retrieve. Defaults to 5.

        Returns:
            Dict: The query results.

        Raises:
            VectorDBException: If querying vectors fails.
        """
        try:
            response = self.index.query(
                vector=query_vector,
                namespace=namespace,
                top_k=top_k,
                include_metadata=True
            )
            logger.info(f"Query successful in namespace '{namespace}'. Retrieved top {top_k} results.")
            return response
        except Exception as e:
            raise VectorDBException(f"Query failed: {str(e)}")

    def delete_vectors(self, ids: List[str], namespace: str) -> None:
        """
        Deletes specific vectors from a namespace.

        Args:
            ids (List[str]): A list of vector IDs to delete.
            namespace (str): The namespace from which to delete vectors.

        Raises:
            VectorDBException: If deleting vectors fails.
        """
        try:
            self.index.delete(ids=ids, namespace=namespace)
            logger.info(f"Deleted {len(ids)} vectors from namespace '{namespace}'.")
        except Exception as e:
            raise VectorDBException(f"Failed to delete vectors: {str(e)}")