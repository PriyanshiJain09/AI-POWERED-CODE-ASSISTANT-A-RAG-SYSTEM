# retrieval/hybrid_search.py — BM25 + ChromaDB vector search via RRF

from retrieval.vector_store import vector_search, collection_exists
from retrieval.bm25_index import bm25_search


def _rrf(result_lists: list[list[dict]], k: int = 60) -> list[dict]:
    """Reciprocal Rank Fusion — merges ranked lists into one."""
    scores: dict[str, float] = {}
    docs:   dict[str, dict]  = {}

    for result_list in result_lists:
        for rank, doc in enumerate(result_list):
            key = f"{doc['file_path']}::{doc['name']}::{doc.get('start_line', 0)}"
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
            docs[key] = doc

    ranked = sorted(scores, key=lambda k: scores[k], reverse=True)
    return [docs[k] for k in ranked]


async def hybrid_search(repo_full: str, query: str, top_k: int = 6) -> list[dict]:
    """
    Combines BM25 keyword search + ChromaDB vector search.
    Falls back gracefully if either index is missing.
    """
    bm25_results = bm25_search(repo_full, query, top_k=top_k * 2)
    vec_results  = []

    if collection_exists(repo_full):
        vec_results = vector_search(repo_full, query, top_k=top_k * 2)

    if not bm25_results and not vec_results:
        return []

    fused = _rrf([bm25_results, vec_results])
    return fused[:top_k]
