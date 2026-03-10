# main.py — RepoMind FastAPI Backend

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()

from ingestion.pipeline import run_ingestion_pipeline
from retrieval.hybrid_search import hybrid_search
from retrieval.vector_store import get_client, vector_search
from retrieval.bm25_index import build_bm25_index
from llm.ollama_client import ask_ollama
from llm.prompt_templates import qa_prompt, explain_file_prompt, explain_pr_prompt
from tools.linter import run_scan
from tools.patch_generator import generate_patch, push_patch_as_pr
from github_client import get_file_content, get_pr_diff

app = FastAPI(title="RepoMind API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Rebuild BM25 from ChromaDB on startup ─────────────────────────────────────
@app.on_event("startup")
async def rebuild_indexes():
    """
    On every server start, reload BM25 indexes from whatever
    is already stored in ChromaDB so /ask works immediately.
    """
    try:
        from ingestion.parser import CodeChunk
        client = get_client()
        collections = client.list_collections()

        if not collections:
            print("[startup] No indexed repos found in ChromaDB yet.")
            return

        for col in collections:
            repo_full = col.name.replace("_", "/", 1)  # reverse the safe_name
            print(f"[startup] Rebuilding BM25 for {repo_full}…")

            collection = client.get_collection(col.name)
            result = collection.get()  # fetch all stored chunks

            if not result["documents"]:
                continue

            chunks = []
            for i, doc in enumerate(result["documents"]):
                meta = result["metadatas"][i]
                chunks.append(CodeChunk(
                    content=doc,
                    file_path=meta.get("file_path", ""),
                    name=meta.get("name", ""),
                    start_line=meta.get("start_line", 0),
                    end_line=meta.get("end_line", 0),
                    chunk_type=meta.get("chunk_type", "file"),
                    language=meta.get("language", ""),
                ))

            build_bm25_index(repo_full, chunks)
            print(f"[startup] ✅ BM25 rebuilt for {repo_full} ({len(chunks)} chunks)")

    except Exception as e:
        print(f"[startup] Warning: could not rebuild indexes: {e}")


# ── Request / Response Models ──────────────────────────────────────────────────

class IndexRequest(BaseModel):
    owner: str
    repo: str

class AskRequest(BaseModel):
    repo: str
    question: str

class ExplainFileRequest(BaseModel):
    repo: str
    file_path: str

class ExplainPRRequest(BaseModel):
    repo: str
    pr_number: int

class IssuesRequest(BaseModel):
    repo: str
    file_path: str = ""
    scan_type: str = "lint"

class PatchRequest(BaseModel):
    repo: str
    issue_description: str

class PushPRRequest(BaseModel):
    repo: str
    patch: str
    title: str

# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


@app.post("/index")
async def index_repo(req: IndexRequest):
    try:
        result = await run_ingestion_pipeline(req.owner, req.repo)
        return {
            "status": "indexed",
            "repo": f"{req.owner}/{req.repo}",
            "chunks": result["chunks"],
            "files": result["files"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ask")
async def ask_question(req: AskRequest):
    try:
        chunks = await hybrid_search(req.repo, req.question, top_k=6)
        if not chunks:
            return {
                "answer": "This repo hasn't been indexed yet. Click ⚡ Index first.",
                "citations": []
            }

        prompt = qa_prompt(req.question, chunks)
        answer = await ask_ollama(prompt)
        citations = list({c["file_path"] for c in chunks})

        return {"answer": answer, "citations": citations}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/explain-file")
async def explain_file(req: ExplainFileRequest):
    try:
        content = await get_file_content(req.repo, req.file_path)
        if not content:
            raise HTTPException(status_code=404, detail="File not found")

        prompt = explain_file_prompt(req.file_path, content)
        explanation = await ask_ollama(prompt)
        return {"explanation": explanation, "file": req.file_path}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/explain-pr")
async def explain_pr(req: ExplainPRRequest):
    try:
        diff = await get_pr_diff(req.repo, req.pr_number)
        prompt = explain_pr_prompt(req.pr_number, diff)
        explanation = await ask_ollama(prompt)
        return {"explanation": explanation, "pr_number": req.pr_number}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/detect-issues")
async def detect_issues(req: IssuesRequest):
    try:
        issues = await run_scan(req.repo, req.file_path, req.scan_type)
        return {"issues": issues, "count": len(issues)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate-patch")
async def gen_patch(req: PatchRequest):
    try:
        result = await generate_patch(req.repo, req.issue_description)
        return {"patch": result["patch"], "files": result.get("files", []), "preview": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/push-pr")
async def push_pr(req: PushPRRequest):
    try:
        pr_url = await push_patch_as_pr(req.repo, req.patch, req.title)
        return {"pr_url": pr_url, "status": "created"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("APP_PORT", 8000)), reload=True)
