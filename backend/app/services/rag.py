from app.services.embedding import get_embeddings

MAX_CONTEXT = 3000


def retrieve_context(query, vector_store):
    query_embedding = get_embeddings([query])[0]
    results = vector_store.search(query_embedding)

    context = ""

    for doc in results:
        chunk = f"\n📁 File: {doc['file']}\n{doc['content']}\n"

        if len(context) + len(chunk) > MAX_CONTEXT:
            break

        context += chunk

    return context
