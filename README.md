# DevIntel — AI-Powered Code Intelligence

> Explore a public GitHub codebase with a focused, private-by-design RAG workflow.

DevIntel is a full-stack developer tool that indexes a public GitHub repository, retrieves
the most relevant source code for a question, and uses Gemini to produce concise,
file-aware explanations. It also includes an AI debugging view for investigating errors
against the indexed codebase.

## Why DevIntel?

Reading an unfamiliar repository is slow: developers need to locate the right files,
trace relationships, and form a mental model before they can make a safe change.
DevIntel shortens that first-pass investigation without pretending the model has access
to code it has not retrieved.

## Highlights

- **Repository-aware Q&A** — clone and index a public HTTPS GitHub repository, then ask
  natural-language questions about its implementation.
- **Bring your own Gemini key** — a user enters their own key in the UI, so their own
  Gemini project and quota are used.
- **No key persistence** — API keys live only in browser memory for the active tab and
  are passed to the backend per request. They are never put in local storage, a database,
  logs, or the repository-index cache.
- **Focused retrieval** — FAISS selects relevant code chunks before Gemini is called;
  answers are instructed to cite files and identify insufficient context.
- **Debug assistant** — submit an error and optional code snippet for a concise,
  repository-aware debugging suggestion.
- **Polished developer experience** — React interface with a guided three-step workflow,
  password-style key input, clear key control, loading states, and useful API errors.

## Architecture

```text
React + Vite browser UI
        |
        | JSON + ephemeral session ID + per-request Gemini key
        v
FastAPI API
  ├─ URL validation and shallow Git clone
  ├─ Code loader, parser, chunker, and sentence-transformer embeddings
  ├─ FAISS repository index cache (contains code embeddings only)
  ├─ Diverse, size-limited context retrieval
  └─ Gemini generation with a concise system instruction
        |
        v
Answer or debugging guidance with source-file references
```

## Token-efficient RAG design

DevIntel keeps both latency and Gemini input usage practical:

- Repository embeddings are cached in a bounded, in-memory LRU cache for the lifetime of
  the server, so a repeated ingest does not re-embed the same codebase.
- A separate ephemeral browser-session mapping prevents one user’s active repository from
  replacing another user’s view; it never contains an API key.
- Retrieval considers a broader candidate set, but sends at most **four** diverse chunks,
  at most **two** from one file, and no more than **3,200 characters** of source context.
- Gemini responses are capped at **500 output tokens**.
- Debugging uses the same retrieved context once rather than duplicating it in the prompt.
- Large files, generated folders, dependencies, and unsupported file types are skipped
  before they affect cloning, embedding, or prompting.

## Security choices

| Concern | Implementation |
| --- | --- |
| Gemini credentials | Provided in `X-Gemini-API-Key` for one request only; never persisted or logged. |
| Browser state | Key and session ID exist in React memory only, not browser storage. |
| Repository source | Only public `https://github.com/owner/repository` URLs are accepted. |
| Cross-origin access | CORS defaults to local Vite origins and can be restricted with `DEVINTEL_ALLOWED_ORIGINS`. |
| Provider failures | Invalid keys, quota errors, and generic provider failures receive safe, actionable API responses. |

For production, serve both applications over HTTPS and set
`DEVINTEL_ALLOWED_ORIGINS` to an explicit comma-separated allowlist.

## Run locally

### Prerequisites

- Python 3.10+
- Node.js 20+
- A [Gemini API key](https://aistudio.google.com/app/apikey) for asking questions

### Backend

```bash
git clone https://github.com/AyushChowdhary/DevIntel.git
cd DevIntel/backend
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
sh start.sh
```

The API starts at `http://127.0.0.1:8000`.

### Frontend

Open a second terminal:

```bash
cd DevIntel/frontend
npm install
npm run dev
```

Open the Vite URL shown in the terminal (normally `http://127.0.0.1:5173`). The
development proxy forwards `/api` to the backend automatically. For a separately hosted
API, set `VITE_API_BASE_URL` during the frontend build.

## How to use it

1. Enter a Gemini API key. It is intentionally not saved when the page is refreshed.
2. Paste a public GitHub repository URL and select **Index repository**.
3. Ask a codebase question or switch to **Debug** to investigate an error.
4. Use **Clear key** when finished with a shared computer.

## Project structure

```text
DevIntel/
├── backend/
│   ├── app/
│   │   ├── evaluation/       # response-quality evaluation utilities
│   │   ├── services/         # GitHub loading, embeddings, FAISS, RAG, Gemini
│   │   ├── training/         # space for ML experimentation
│   │   ├── utils/            # source chunking utilities
│   │   └── main.py           # FastAPI routes and request boundaries
│   ├── requirements.txt
│   └── start.sh
├── frontend/
│   ├── src/                  # React application and responsive UI styles
│   ├── package.json
│   └── vite.config.js
└── README.md
```

## Interview talking points

- **Privacy and multi-user isolation:** API keys are transient while repository indexes
  are intentionally cacheable; separating those lifecycles avoids shared-key behaviour.
- **RAG quality versus cost:** retrieval diversity and hard context/output caps keep the
  prompt focused instead of sending an entire repository to an LLM.
- **Defensive API design:** URL, size, and request-body validation narrow the failure
  surface; public error messages do not expose provider internals or credential details.
- **Pragmatic full stack delivery:** Vite’s development proxy, FastAPI endpoints, CORS,
  error states, and the UI flow work together as one application.

## Future improvements

- Persist repository indexes in a shared vector store with safe eviction.
- Add authenticated accounts, encrypted server-side provider connections, and rate limits.
- Add repository branch selection and GitHub App integration for private repositories.
- Stream answers and show source chunk citations directly in the UI.

## Author

**Ayush Chowdhary** — Computer Science student interested in AI/ML, full-stack systems,
and practical developer tools. [GitHub](https://github.com/AyushChowdhary)
