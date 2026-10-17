from app.services.embedding import get_embeddings

MAX_CONTEXT_CHARS = 3_200
MAX_CONTEXT_CHUNKS = 4
MAX_CHUNKS_PER_FILE = 2
RETRIEVAL_CANDIDATES = 12


def retrieve_context(query: str, vector_store) -> str:
    """Build a compact, diverse context window from the most relevant chunks."""
    query_embedding = get_embeddings([query])[0]
    candidates = vector_store.search(query_embedding, k=RETRIEVAL_CANDIDATES)

    context_parts = []
    chunks_per_file = {}
    current_length = 0

    for _, doc in candidates:
        file_path = doc["file"]
        if chunks_per_file.get(file_path, 0) >= MAX_CHUNKS_PER_FILE:
            continue

        chunk = f"File: {file_path}\n{doc['content'].strip()}"
        if not chunk.strip() or current_length + len(chunk) > MAX_CONTEXT_CHARS:
            continue

        context_parts.append(chunk)
        chunks_per_file[file_path] = chunks_per_file.get(file_path, 0) + 1
        current_length += len(chunk)
        if len(context_parts) >= MAX_CONTEXT_CHUNKS:
            break

    return "\n\n---\n\n".join(context_parts) or "No relevant indexed code was found."
