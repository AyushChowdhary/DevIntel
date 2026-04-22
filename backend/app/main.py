from fastapi import FastAPI

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
        except:
            parsed = {"functions": [], "classes": []}

        try:
            imports = extract_imports(content)
        except:
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
        return {"error": "No repository indexed yet"}

    context = retrieve_context(q, vector_store)
    answer = generate_answer(q, context)
    score = evaluate_response(q, answer, context)

    return {
        "answer": answer,
        "score": score
    }


@app.post("/debug")
def debug(error: str, code: str = ""):
    result = debug_error(error, code, vector_store)
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
