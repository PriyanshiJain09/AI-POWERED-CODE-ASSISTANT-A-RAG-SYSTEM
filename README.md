> AI-powered GitHub code assistant — runs as a Chrome side panel

## Features
- 💬 Ask questions about any public repo (grounded answers with citations)
- 📖 Explain files and PRs instantly
- 🔍 Detect issues via linter and semgrep
- 🔧 Generate AI patches and push as GitHub PRs

## Stack
- **Frontend:** Chrome Extension (Manifest V3, Side Panel API)
- **Backend:** FastAPI + Python
- **LLM:** Groq (LLaMA 3.3 70B) 
- **Embeddings:** sentence-transformers (all-MiniLM-L6-v2)
- **Vector DB:** ChromaDB
- **Search:** Hybrid BM25 + semantic vector search
- **Parsing:** tree-sitter (function-level chunks)

## Setup

### Backend
```bash
cd Backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
cp .env
uvicorn main:app --reload
```

### Chrome Extension
1. Go to `chrome://extensions`
2. Enable Developer Mode
3. Click Load unpacked → select `chrome-extension/` folder
4. Visit any GitHub repo and click the RepoMind icon

## Architecture
```
Chrome Extension (side panel)
        ↕ REST API
    FastAPI Backend
    ├── GitHub API (repo ingestion)
    ├── tree-sitter (code parsing)
    ├── sentence-transformers (embeddings)
    ├── ChromaDB (vector store)
    ├── BM25 (keyword index)
    └── Groq LLaMA 3.3 70B (LLM)
```