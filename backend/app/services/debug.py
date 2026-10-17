from app.services.llm import generate_answer
from app.services.rag import retrieve_context


def debug_error(error: str, code_context: str, vector_store, api_key: str) -> str:
    retrieval_query = f"{error}\n{code_context}"
    context = retrieve_context(retrieval_query, vector_store)
    task = (
        "Diagnose this error. State the likely root cause, cite the relevant files, "
        "and propose a focused fix.\n\n"
        f"Error:\n{error}\n\n"
        f"User-supplied code, if any:\n{code_context or '(none)'}"
    )
    return generate_answer(task, context, api_key)
