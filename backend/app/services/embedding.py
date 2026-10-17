import numpy as np
from functools import lru_cache
from sentence_transformers import SentenceTransformer


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    """Load the local embedding model only when a repository is first indexed."""
    return SentenceTransformer("all-MiniLM-L6-v2")


def get_embeddings(texts):
    if not texts:
        return np.empty((0, 0), dtype=np.float32)
    return get_embedding_model().encode(
        texts,
        batch_size=32,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,
    ).astype(np.float32)
