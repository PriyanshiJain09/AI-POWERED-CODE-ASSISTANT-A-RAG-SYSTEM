# retrieval/bm25_index.py — In-memory BM25 keyword index

import re
from rank_bm25 import BM25Okapi
from ingestion.parser import CodeChunk

# In-memory store: repo_full_name → {bm25, chunks}
_indexes: dict[str, dict] = {}


def _tokenize(text: str) -> list[str]:
    """Simple tokenizer: lowercase, split on non-alphanumeric."""
    return re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", text.lower())


def build_bm25_index(repo_full: str, chunks: list[CodeChunk]) -> None:
    """Build (or rebuild) the BM25 index for a repo."""
    corpus = [
        _tokenize(f"{c.file_path} {c.name} {c.content}")
        for c in chunks
    ]
    bm25 = BM25Okapi(corpus)
    _indexes[repo_full] = {"bm25": bm25, "chunks": chunks}
    print(f"[bm25] Index built for {repo_full} ({len(chunks)} docs)")


def bm25_search(repo_full: str, query: str, top_k: int = 5) -> list[dict]:
    """Return top_k chunks by BM25 score."""
    if repo_full not in _indexes:
        return []

    idx = _indexes[repo_full]
    bm25: BM25Okapi = idx["bm25"]
    chunks: list[CodeChunk] = idx["chunks"]

    tokens = _tokenize(query)
    scores = bm25.get_scores(tokens)

    # Pair scores with chunks and sort
    ranked = sorted(
        zip(scores, chunks),
        key=lambda x: x[0],
        reverse=True,
    )

    results = []
    for score, chunk in ranked[:top_k]:
        if score > 0:
            results.append({
                "file_path":  chunk.file_path,
                "name":       chunk.name,
                "content":    chunk.content,
                "start_line": chunk.start_line,
                "end_line":   chunk.end_line,
                "chunk_type": chunk.chunk_type,
                "language":   chunk.language,
                "bm25_score": float(score),
            })

    return results


def index_exists(repo_full: str) -> bool:
    return repo_full in _indexes
