# ingest/embed_store.py
"""
L1 — Embed chunks with BAAI/bge-small-en-v1.5 and upsert into Qdrant.

Reads every data/processed/{pmcid}_chunks.json (output of chunk.py),
embeds each chunk's text, and stores dense vectors + payload
(pmcid, section, chunk_index, text) in a fresh Qdrant collection.

Recreates the collection from scratch on every run — no incremental
upsert tracking needed at L1 scale (6K chunks embeds in a few minutes
on CPU).

Requires Qdrant running: docker compose up -d qdrant

Run:
    uv run python -m ingest.embed_store
"""

import json
from pathlib import Path

from fastembed import TextEmbedding
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from config import PROCESSED_DATA_DIR, QDRANT_URL, COLLECTION, DENSE_MODEL

BATCH_SIZE = 64
VECTOR_SIZE = 384  # bge-small-en-v1.5 output dimension


def load_all_chunks() -> list[dict]:
    """Load every {pmcid}_chunks.json file into one flat list of chunk dicts."""
    chunk_files = sorted(PROCESSED_DATA_DIR.glob("*_chunks.json"))
    all_chunks = []
    for f in chunk_files:
        all_chunks.extend(json.loads(f.read_text()))
    return all_chunks


def ensure_collection(client: QdrantClient):
    """
    Delete the collection if it exists, then create it fresh.
    Recreating on every run keeps L1 simple — no need to reconcile
    stale points against changed chunking logic.
    """
    if client.collection_exists(COLLECTION):
        client.delete_collection(COLLECTION)
        print(f"Deleted existing collection '{COLLECTION}'.")

    client.create_collection(
        collection_name=COLLECTION,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
    )
    print(f"Created collection '{COLLECTION}' (dim={VECTOR_SIZE}, distance=COSINE).")


def batched(items: list, batch_size: int):
    """Yield successive batch_size-sized slices of items."""
    for i in range(0, len(items), batch_size):
        yield items[i : i + batch_size]


def main():
    print("Loading chunks from disk...")
    chunks = load_all_chunks()
    print(f"Loaded {len(chunks)} chunks total.")

    print(f"Loading embedding model '{DENSE_MODEL}' (first run downloads ONNX weights)...")
    embedder = TextEmbedding(model_name=DENSE_MODEL)

    client = QdrantClient(url=QDRANT_URL)
    ensure_collection(client)

    point_id = 0
    embedded_count = 0

    for batch in batched(chunks, BATCH_SIZE):
        texts = [c["text"] for c in batch]
        vectors = list(embedder.embed(texts))  # fastembed returns a generator; materialize per batch

        points = []
        for chunk, vector in zip(batch, vectors):
            points.append(
                PointStruct(
                    id=point_id,
                    vector=vector.tolist(),
                    payload={
                        "pmcid": chunk["pmcid"],
                        "section": chunk["section"],
                        "chunk_index": chunk["chunk_index"],
                        "text": chunk["text"],
                    },
                )
            )
            point_id += 1

        client.upsert(collection_name=COLLECTION, points=points)
        embedded_count += len(points)
        print(f"  Embedded and upserted {embedded_count}/{len(chunks)} chunks...")

    print(f"\nDone. {embedded_count} chunks embedded and stored in Qdrant collection '{COLLECTION}'.")


if __name__ == "__main__":
    main()