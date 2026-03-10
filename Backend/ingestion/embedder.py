# ingestion/embedder.py — Only used for standalone query embedding now
# Chunk embedding is handled inside vector_store.py to keep it simple

import os
import numpy as np
from sentence_transformers import SentenceTransformer
from ingestion.parser import CodeChunk

_model = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        model_name = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        _model = SentenceTransformer(model_name)
    return _model


def embed_chunks(chunks: list[CodeChunk]) -> list[np.ndarray]:
    """Embed a list of CodeChunks — kept for compatibility."""
    model = get_model()
    texts = [f"File: {c.file_path}\nFunction: {c.name}\n\n{c.content}" for c in chunks]
    return list(model.encode(texts, batch_size=32, show_progress_bar=True, normalize_embeddings=True))


def embed_query(query: str) -> np.ndarray:
    return get_model().encode(query, normalize_embeddings=True)
