from fastapi import FastAPI, HTTPException

from app.services.github_loader import clone_repo, load_code_files
from app.services.embedding import get_embeddings
from app.services.vector_store import VectorStore
from app.services.rag import retrieve_context
from app.services.code_parser import parse_python_file, extract_imports
from app.services.debug import debug_error
from app.services.llm import generate_answer
from app.utils.chunker import chunk_code
from app.evaluation.eval import evaluate_response

app = FastAPI()

vector_store = None


@app.post("/ingest")
def ingest(repo_url: str):
    global vector_store

    repo_path = clone_repo(repo_url)
    files = load_code_files(repo_path)

    all_chunks = []
    all_documents = []

    for file in files:
        content = file["content"]
        path = file["path"]

        try:
            parsed = parse_python_file(content)
        except Exception:
            parsed = {"functions": [], "classes": []}

        try:
            imports = extract_imports(content)
        except Exception: 
            
            imports = []

        chunks = chunk_code(content)

        for chunk in chunks:
            doc = {
                "content": chunk,
                "file": path,
                "functions": parsed["functions"],
                "classes": parsed["classes"],
                "imports": imports
            }

            all_chunks.append(chunk)
            all_documents.append(doc)

    embeddings = get_embeddings(all_chunks)

    vector_store = VectorStore(len(embeddings[0]))
    vector_store.add(embeddings, all_documents)

    return {"message": "Repo indexed successfully"}


@app.post("/query")
def query(q: str):
    if vector_store is None:
        raise HTTPException(status_code=400, detail="No repository indexed yet")

    try:
        context = retrieve_context(q, vector_store)
        answer = generate_answer(q, context)
        score = evaluate_response(q, answer, context)
    except Exception as exc:
        message = str(exc)
        if "RESOURCE_EXHAUSTED" in message or "429" in message:
            raise HTTPException(
                status_code=429,
                detail="Gemini API quota exceeded. Please retry later or use a key/project with available quota.",
            ) from exc
        raise HTTPException(status_code=500, detail=f"Query failed: {message}") from exc

    return {
        "answer": answer,
        "score": score
    }


@app.post("/debug")
def debug(error: str, code: str = ""):
    try:
        result = debug_error(error, code, vector_store)
    except Exception as exc:
        message = str(exc)
        if "RESOURCE_EXHAUSTED" in message or "429" in message:
            raise HTTPException(
                status_code=429,
                detail="Gemini API quota exceeded. Please retry later or use a key/project with available quota.",
            ) from exc
        raise HTTPException(status_code=500, detail=f"Debug failed: {message}") from exc
    return {"result": result}

@app.get("/")
def home():
    return {"message": "DevIntel API is running 🚀"}

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
