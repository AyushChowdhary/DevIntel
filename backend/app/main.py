from collections import OrderedDict
import os
from threading import RLock
from uuid import UUID

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.evaluation.eval import evaluate_response
from app.services.code_parser import extract_imports, parse_python_file
from app.services.debug import debug_error
from app.services.embedding import get_embeddings
from app.services.github_loader import clone_repo, load_code_files, normalize_repo_url
from app.services.llm import generate_answer
from app.services.rag import retrieve_context
from app.services.vector_store import VectorStore
from app.utils.chunker import chunk_code


app = FastAPI(title="DevIntel API")

# These caches intentionally contain repository indexes only—never Gemini API keys.
session_vector_stores: dict[str, VectorStore] = {}
repository_index_cache: OrderedDict[str, VectorStore] = OrderedDict()
cache_lock = RLock()
MAX_CACHED_REPOSITORIES = 8
DEFAULT_ALLOWED_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
allowed_origins = [
    origin.strip()
    for origin in os.getenv("DEVINTEL_ALLOWED_ORIGINS", DEFAULT_ALLOWED_ORIGINS).split(",")
    if origin.strip()
]


class IngestRequest(BaseModel):
    repo_url: str = Field(min_length=10, max_length=500)


class QueryRequest(BaseModel):
    q: str = Field(min_length=1, max_length=1_200)


class DebugRequest(BaseModel):
    error: str = Field(min_length=1, max_length=2_000)
    code: str = Field(default="", max_length=3_000)


def require_session_id(
    session_id: str | None = Header(default=None, alias="X-DevIntel-Session-ID"),
) -> str:
    """Validate the browser-memory session identifier without persisting it."""
    try:
        return str(UUID(session_id or ""))
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail="Start a new browser session and index a repository before continuing.",
        ) from exc


def require_gemini_api_key(
    api_key: str | None = Header(default=None, alias="X-Gemini-API-Key"),
) -> str:
    # The key is read from this request header, passed to Gemini, then discarded.
    normalized_key = (api_key or "").strip()
    if len(normalized_key) < 10:
        raise HTTPException(status_code=400, detail="Enter a valid Gemini API key to continue.")
    return normalized_key


def get_session_vector_store(session_id: str) -> VectorStore:
    with cache_lock:
        vector_store = session_vector_stores.get(session_id)
    if vector_store is None:
        raise HTTPException(status_code=400, detail="No repository is indexed for this browser session.")
    return vector_store


def get_cached_index(repo_url: str) -> VectorStore | None:
    with cache_lock:
        vector_store = repository_index_cache.get(repo_url)
        if vector_store is not None:
            repository_index_cache.move_to_end(repo_url)
        return vector_store


def cache_index(repo_url: str, vector_store: VectorStore) -> None:
    with cache_lock:
        repository_index_cache[repo_url] = vector_store
        repository_index_cache.move_to_end(repo_url)
        while len(repository_index_cache) > MAX_CACHED_REPOSITORIES:
            repository_index_cache.popitem(last=False)


def attach_index_to_session(session_id: str, vector_store: VectorStore) -> None:
    with cache_lock:
        session_vector_stores[session_id] = vector_store


def build_vector_store(repo_url: str) -> tuple[VectorStore, int, int]:
    repo_path, canonical_url = clone_repo(repo_url)
    files = load_code_files(repo_path)
    all_chunks = []
    all_documents = []

    for file in files:
        content = file["content"]
        path = file["path"]

        try:
            parsed = parse_python_file(content)
        except (SyntaxError, ValueError, TypeError):
            parsed = {"functions": [], "classes": []}

        try:
            imports = extract_imports(content)
        except (SyntaxError, ValueError, TypeError):
            imports = []

        for chunk in chunk_code(content):
            if not chunk.strip():
                continue
            all_chunks.append(chunk)
            all_documents.append(
                {
                    "content": chunk,
                    "file": path,
                    "functions": parsed["functions"],
                    "classes": parsed["classes"],
                    "imports": imports,
                }
            )

    if not all_chunks:
        raise HTTPException(status_code=422, detail="No supported source files were found in this repository.")

    embeddings = get_embeddings(all_chunks)
    vector_store = VectorStore(embeddings.shape[1])
    vector_store.add(embeddings, all_documents)
    cache_index(canonical_url, vector_store)
    return vector_store, len(files), len(all_chunks)


def raise_gemini_error(exc: Exception) -> None:
    """Return actionable but key-safe provider errors without exposing exception text."""
    message = str(exc).lower()
    if "resource_exhausted" in message or "quota" in message or "429" in message:
        raise HTTPException(
            status_code=429,
            detail="Gemini quota is exhausted for this key. Use a key with available quota or retry later.",
        ) from exc
    if "api key" in message or "api_key" in message or "unauthenticated" in message or "401" in message or "403" in message:
        raise HTTPException(
            status_code=401,
            detail="Gemini rejected this API key. Check the key and its project permissions.",
        ) from exc
    raise HTTPException(
        status_code=502,
        detail="Gemini could not complete this request. Please try again shortly.",
    ) from exc


@app.post("/ingest")
def ingest(request: IngestRequest, session_id: str = Header(alias="X-DevIntel-Session-ID")):
    session_id = require_session_id(session_id)
    try:
        canonical_url = normalize_repo_url(request.repo_url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    vector_store = get_cached_index(canonical_url)
    if vector_store is not None:
        attach_index_to_session(session_id, vector_store)
        return {
            "message": "Repository index restored from the in-memory cache.",
            "cached": True,
            "repository": canonical_url.removesuffix(".git"),
        }

    try:
        vector_store, file_count, chunk_count = build_vector_store(canonical_url)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail="The repository could not be cloned or indexed. Confirm that it is a public GitHub repository.",
        ) from exc

    attach_index_to_session(session_id, vector_store)
    return {
        "message": "Repository indexed successfully.",
        "cached": False,
        "files": file_count,
        "chunks": chunk_count,
        "repository": canonical_url.removesuffix(".git"),
    }


@app.post("/query")
def query(
    request: QueryRequest,
    session_id: str = Header(alias="X-DevIntel-Session-ID"),
    api_key: str = Header(alias="X-Gemini-API-Key"),
):
    vector_store = get_session_vector_store(require_session_id(session_id))
    api_key = require_gemini_api_key(api_key)
    try:
        context = retrieve_context(request.q.strip(), vector_store)
        answer = generate_answer(request.q.strip(), context, api_key)
        score = evaluate_response(request.q, answer, context)
    except HTTPException:
        raise
    except Exception as exc:
        raise_gemini_error(exc)

    return {"answer": answer, "score": score}


@app.post("/debug")
def debug(
    request: DebugRequest,
    session_id: str = Header(alias="X-DevIntel-Session-ID"),
    api_key: str = Header(alias="X-Gemini-API-Key"),
):
    vector_store = get_session_vector_store(require_session_id(session_id))
    api_key = require_gemini_api_key(api_key)
    try:
        result = debug_error(request.error.strip(), request.code.strip(), vector_store, api_key)
    except HTTPException:
        raise
    except Exception as exc:
        raise_gemini_error(exc)
    return {"result": result}


@app.get("/")
def home():
    return {"message": "DevIntel API is running."}


app.add_middleware(
    CORSMiddleware,
    # Configure DEVINTEL_ALLOWED_ORIGINS with a comma-separated production allowlist.
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-DevIntel-Session-ID", "X-Gemini-API-Key"],
)
