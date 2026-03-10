# RepoMind — Backend

FastAPI backend for the RepoMind Chrome Extension.  
Runs **100% locally** — no data leaves your machine.

---

## Stack

| Component | What it does |
|---|---|
| **FastAPI** | REST API server |
| **tree-sitter** | Parses code into function-level chunks |
| **sentence-transformers** | Local embeddings (`all-MiniLM-L6-v2`) |
| **Qdrant** | Vector database (runs via Docker) |
| **BM25** | Keyword search index (in-memory) |
| **Ollama + CodeLlama** | Local LLM for Q&A and patch generation |
| **PyGithub** | GitHub API for fetching files and pushing PRs |

---

## Quick Start

### Prerequisites
- Python 3.11+
- Docker
- [Ollama](https://ollama.ai)
- A GitHub Personal Access Token

### 1. Clone and setup
```bash
git clone <your-repo>
cd repomind-backend
chmod +x setup.sh && ./setup.sh
```

### 2. Add your GitHub token
```bash
# Edit .env
GITHUB_TOKEN=ghp_your_token_here
```
Create a token at https://github.com/settings/tokens  
Required scopes: `repo` (read), `pull_requests` (read+write)

### 3. Start everything
```bash
# Terminal 1 — Ollama
ollama serve

# Terminal 2 — Qdrant (if not started by setup.sh)
docker run -p 6333:6333 qdrant/qdrant

# Terminal 3 — FastAPI
source .venv/bin/activate
python main.py
```

### 4. Verify it's working
```bash
curl http://localhost:8000/health
# → {"status": "ok", "version": "1.0.0"}
```

Interactive API docs: http://localhost:8000/docs

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/index` | Index a repo (owner + repo name) |
| `POST` | `/ask` | Ask a question about a repo |
| `POST` | `/explain-file` | Explain a specific file |
| `POST` | `/explain-pr` | Summarise a pull request |
| `POST` | `/detect-issues` | Run linter or semgrep scan |
| `POST` | `/generate-patch` | Generate an AI patch (preview) |
| `POST` | `/push-pr` | Push confirmed patch as a GitHub PR |

---

## Project Structure

```
repomind-backend/
├── main.py                  # FastAPI app + all routes
├── github_client.py         # GitHub API wrapper
├── ingestion/
│   ├── parser.py            # tree-sitter code chunking
│   ├── embedder.py          # sentence-transformers
│   └── pipeline.py          # orchestrates full index flow
├── retrieval/
│   ├── vector_store.py      # Qdrant operations
│   ├── bm25_index.py        # keyword search
│   └── hybrid_search.py     # RRF fusion of both
├── llm/
│   ├── ollama_client.py     # Ollama API calls
│   └── prompt_templates.py  # all prompts
├── tools/
│   ├── linter.py            # ruff + semgrep (with fallbacks)
│   └── patch_generator.py   # diff generation + PR push
├── .env.example
├── requirements.txt
└── setup.sh
```

---

## How Indexing Works

```
POST /index {"owner": "vercel", "repo": "next.js"}
      ↓
1. List all .py/.ts/.js files via GitHub tree API
2. Fetch content in batches of 20 (respects rate limits)
3. Parse each file → function-level chunks (tree-sitter)
4. Embed each chunk (sentence-transformers, ~90ms/chunk)
5. Store vectors in Qdrant collection "vercel__next.js"
6. Build BM25 keyword index in memory
```

## How Q&A Works

```
POST /ask {"repo": "vercel/next.js", "question": "..."}
      ↓
1. BM25 search → top 12 keyword-matched chunks
2. Vector search → top 12 semantically similar chunks
3. Reciprocal Rank Fusion → top 6 best chunks
4. Build prompt: context + question
5. Ask Ollama (CodeLlama) → answer with citations
```
