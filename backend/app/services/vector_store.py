import faiss
import numpy as np


class VectorStore:
    """An in-memory, read-only-after-build FAISS index for one repository."""

    def __init__(self, dim: int):
        self.index = faiss.IndexFlatIP(dim)
        self.documents = []

    def add(self, embeddings, documents) -> None:
        vectors = np.asarray(embeddings, dtype=np.float32)
        if vectors.ndim != 2 or vectors.shape[0] != len(documents):
            raise ValueError("Embeddings and documents must have matching lengths.")
        if vectors.shape[1] != self.index.d:
            raise ValueError("Embedding dimension does not match the index.")

        faiss.normalize_L2(vectors)
        self.index.add(vectors)
        self.documents.extend(documents)

    def search(self, query_embedding, k: int = 5):
        """Return ``(similarity, document)`` pairs without FAISS sentinel entries."""
        if not self.documents:
            return []

        vector = np.asarray(query_embedding, dtype=np.float32).reshape(1, -1)
        if vector.shape[1] != self.index.d:
            raise ValueError("Query embedding dimension does not match the index.")

        faiss.normalize_L2(vector)
        scores, indices = self.index.search(vector, min(k, len(self.documents)))
        return [
            (float(score), self.documents[index])
            for score, index in zip(scores[0], indices[0])
            if index >= 0
        ]
