from app.services.rag import retrieve_context
from app.services.llm import generate_answer


def debug_error(error, code_context, vector_store):
    query = f"{error}\n{code_context}"

    context = retrieve_context(query, vector_store)

    prompt = f"""
You are an expert debugging assistant.

Error:
{error}

Code Context:
{context}

Tasks:
1. Explain error
2. Root cause
3. Suggest fix

Answer:
"""

    return generate_answer(prompt, context)