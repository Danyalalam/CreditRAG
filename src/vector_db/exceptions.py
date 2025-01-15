class VectorDBException(Exception):
    """Base exception for vector database operations"""
    pass

class ConnectionError(VectorDBException):
    """Raised when connection to Pinecone fails"""
    pass

class NamespaceError(VectorDBException):
    """Raised when namespace operations fail"""
    pass