# ingestion/pipeline.py

from github_client import list_repo_files, get_file_batch
from ingestion.parser import parse_file, SUPPORTED_EXTENSIONS
from ingestion.embedder import embed_chunks
from retrieval.vector_store import store_chunks
from retrieval.bm25_index import build_bm25_index

MAX_FILE_SIZE_BYTES = 100_000
FETCH_BATCH_SIZE = 20


async def run_ingestion_pipeline(owner: str, repo: str) -> dict:
    repo_full = f"{owner}/{repo}"
    print(f"\n[pipeline] Starting ingestion for {repo_full}")

    # Step 1: List files
    supported_exts = list(SUPPORTED_EXTENSIONS.keys())
    all_files = await list_repo_files(repo_full, extensions=supported_exts)
    all_files = [f for f in all_files if f["size"] < MAX_FILE_SIZE_BYTES]
    print(f"[pipeline] Found {len(all_files)} supported files")

    if not all_files:
        return {"chunks": 0, "files": 0}

    # Step 2: Fetch + Parse
    all_chunks = []
    file_paths = [f["path"] for f in all_files]
    total_fetched = 0

    for i in range(0, len(file_paths), FETCH_BATCH_SIZE):
        batch_paths = file_paths[i:i + FETCH_BATCH_SIZE]
        print(f"[pipeline] Fetching files {i+1}–{min(i+FETCH_BATCH_SIZE, len(file_paths))} / {len(file_paths)}")
        file_contents = await get_file_batch(repo_full, batch_paths)
        total_fetched += len(file_contents)

        for path, content in file_contents.items():
            try:
                chunks = parse_file(path, content)
                all_chunks.extend(chunks)
            except Exception as e:
                print(f"[pipeline] Warning: could not parse {path}: {e}")

    print(f"[pipeline] Parsed {len(all_chunks)} chunks from {total_fetched} files")

    if not all_chunks:
        return {"chunks": 0, "files": total_fetched}

    # Step 3: Embed + Store in ChromaDB
    chunks_as_dicts = [
        {
            "content":    c.content,
            "file_path":  c.file_path,
            "name":       c.name,
            "start_line": c.start_line,
            "end_line":   c.end_line,
            "chunk_type": c.chunk_type,
            "language":   c.language,
        }
        for c in all_chunks
    ]

    store_chunks(repo_full, chunks_as_dicts)
    print(f"[pipeline] Stored {len(all_chunks)} chunks in ChromaDB")

    # Step 4: BM25 index
    build_bm25_index(repo_full, all_chunks)
    print(f"[pipeline] BM25 index built")

    return {"chunks": len(all_chunks), "files": total_fetched}
