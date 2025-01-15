from typing import Dict, List
import numpy as np

def normalize_vector(vector: List[float]) -> List[float]:
    """Normalize vector to unit length"""
    norm = np.linalg.norm(vector)
    return (vector / norm).tolist() if norm != 0 else vector

def prepare_batch(
    vectors: List[List[float]], 
    metadata: List[Dict],
    start_id: int = 0
) -> List[Dict]:
    """Prepare vectors for batch insertion"""
    return [
        {
            'id': str(i + start_id),
            'values': normalize_vector(vec),
            'metadata': meta
        }
        for i, (vec, meta) in enumerate(zip(vectors, metadata))
    ]