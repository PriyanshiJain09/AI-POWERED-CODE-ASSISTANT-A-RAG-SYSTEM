# retrieval/vector_store.py — ChromaDB (no Docker needed)

import os
import chromadb
from sentence_transformers import SentenceTransformer

CHROMA_PATH = os.getenv("CHROMA_PATH", "./chroma_db")

_client = None
_embedder = None


def get_client():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=CHROMA_PATH)
    return _client


def get_embedder():
    global _embedder
    if _embedder is None:
        model_name = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        print(f"[vector_store] Loading embedder: {model_name}")
        _embedder = SentenceTransformer(model_name)
    return _embedder


def _safe_name(repo_name: str) -> str:
    """ChromaDB collection names can't have slashes or hyphens."""
    return repo_name.replace("/", "_").replace("-", "_")


def store_chunks(repo_name: str, chunks: list[dict]) -> None:
    """Embed and store chunks in ChromaDB."""
    collection = get_client().get_or_create_collection(name=_safe_name(repo_name))
    embedder = get_embedder()

    texts     = [c["content"] for c in chunks]
    ids       = [f"{c['file_path']}::{c['start_line']}" for c in chunks]
    metadatas = [
        {
            "file_path":  c["file_path"],
            "name":       c.get("name", ""),
            "start_line": c.get("start_line", 0),
            "end_line":   c.get("end_line", 0),
            "language":   c.get("language", ""),
            "chunk_type": c.get("chunk_type", ""),
        }
        for c in chunks
    ]

    print(f"[vector_store] Embedding {len(texts)} chunks…")
    embeddings = embedder.encode(texts, batch_size=32, show_progress_bar=True).tolist()

    # Upsert in batches of 500 to avoid memory issues
    batch_size = 500
    for i in range(0, len(chunks), batch_size):
        collection.upsert(
            ids=ids[i:i+batch_size],
            documents=texts[i:i+batch_size],
            embeddings=embeddings[i:i+batch_size],
            metadatas=metadatas[i:i+batch_size],
        )

    print(f"[vector_store] ✅ Stored {len(chunks)} chunks for '{repo_name}'")


def vector_search(repo_name: str, query: str, top_k: int = 5) -> list[dict]:
    """Search ChromaDB by semantic similarity."""
    safe = _safe_name(repo_name)

    # Check collection exists
    existing = [c.name for c in get_client().list_collections()]
    if safe not in existing:
        return []

    collection = get_client().get_collection(name=safe)
    embedder = get_embedder()

    query_embedding = embedder.encode(query).tolist()
    results = collection.query(query_embeddings=[query_embedding], n_results=top_k)

    chunks = []
    for i, doc in enumerate(results["documents"][0]):
        meta = results["metadatas"][0][i]
        chunks.append({
            "content":    doc,
            "file_path":  meta.get("file_path", ""),
            "name":       meta.get("name", ""),
            "start_line": meta.get("start_line", 0),
            "end_line":   meta.get("end_line", 0),
            "language":   meta.get("language", ""),
            "chunk_type": meta.get("chunk_type", ""),
            "score":      results["distances"][0][i],
        })
    return chunks


def collection_exists(repo_name: str) -> bool:
    existing = [c.name for c in get_client().list_collections()]
    return _safe_name(repo_name) in existing
