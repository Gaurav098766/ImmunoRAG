# ingest/embed_store.py
"""
L1/L2 — Embed chunks with bge-small-en-v1.5 (dense) and Qdrant/bm25 (sparse),
upsert into Qdrant using named vectors for hybrid search.

Reads every data/processed/{pmcid}_chunks.json (output of chunk.py),
embeds each chunk's text with BOTH a dense and sparse model, and stores
both vectors + payload (pmcid, section, chunk_index, text) in a fresh
Qdrant collection.

Recreates the collection from scratch on every run.

Requires Qdrant running: docker compose up -d qdrant

Run:
    uv run python -m ingest.embed_store
"""

import json
from pathlib import Path

from fastembed import TextEmbedding, SparseTextEmbedding
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    VectorParams,
    SparseVectorParams,
    SparseVector,
)

from config import PROCESSED_DATA_DIR, RAW_DATA_DIR, QDRANT_URL, COLLECTION, DENSE_MODEL, SPARSE_MODEL

BATCH_SIZE = 64
VECTOR_SIZE = 384  # bge-small-en-v1.5 output dimension


def load_paper_metadata_lookup() -> dict:
    """
    Build a {pmcid: {pub_year, journal}} lookup from papers_metadata.json,
    so each chunk's payload can carry these filterable fields without
    needing to query Postgres from this script.
    """
    metadata_path = RAW_DATA_DIR / "papers_metadata.json"
    papers = json.loads(metadata_path.read_text())

    lookup = {}
    for p in papers:
        pub_year = p.get("pub_year")
        if not pub_year:  # catches 0, None, "", "0" — all mean "unknown"
            pub_year = None
        else:
            try:
                pub_year = int(pub_year)  # NEW: force numeric, whatever the source type was
            except (TypeError, ValueError):
                pub_year = None  # if it's genuinely unparseable, treat as unknown

        lookup[p["pmcid"]] = {
            "pub_year": pub_year,
            "journal": p.get("journal"),
        }
    return lookup

def load_all_chunks() -> list[dict]:
    """Load every {pmcid}_chunks.json file into one flat list of chunk dicts."""
    chunk_files = sorted(PROCESSED_DATA_DIR.glob("*_chunks.json"))
    all_chunks = []
    for f in chunk_files:
        all_chunks.extend(json.loads(f.read_text()))
    return all_chunks


def ensure_collection(client: QdrantClient):
    """
    Delete the collection if it exists, then create it fresh with BOTH
    a dense vector config ("dense") and a sparse vector config ("sparse").
    Named vectors let one point carry multiple vector types simultaneously.
    """
    if client.collection_exists(COLLECTION):
        client.delete_collection(COLLECTION)
        print(f"Deleted existing collection '{COLLECTION}'.")

    client.create_collection(
        collection_name=COLLECTION,
        vectors_config={
            "dense": VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        },
        sparse_vectors_config={
            "sparse": SparseVectorParams(),
        },
    )
    print(f"Created collection '{COLLECTION}' with dense (dim={VECTOR_SIZE}) + sparse vectors.")


def batched(items: list, batch_size: int):
    """Yield successive batch_size-sized slices of items."""
    for i in range(0, len(items), batch_size):
        yield items[i : i + batch_size]


def main():
    print("Loading paper metadata lookup...")
    metadata_lookup = load_paper_metadata_lookup()

    print("Loading chunks from disk...")
    chunks = load_all_chunks()
    print(f"Loaded {len(chunks)} chunks total.")

    print(f"Loading dense model '{DENSE_MODEL}'...")
    dense_embedder = TextEmbedding(model_name=DENSE_MODEL)

    print(f"Loading sparse model '{SPARSE_MODEL}'...")
    sparse_embedder = SparseTextEmbedding(model_name=SPARSE_MODEL)

    client = QdrantClient(url=QDRANT_URL)
    ensure_collection(client)

    point_id = 0
    embedded_count = 0

    for batch in batched(chunks, BATCH_SIZE):
        texts = [c["text"] for c in batch]

        dense_vectors = list(dense_embedder.embed(texts))
        sparse_vectors = list(sparse_embedder.embed(texts))

        points = []
        for chunk, dense_vec, sparse_vec in zip(batch, dense_vectors, sparse_vectors):
            paper_meta = metadata_lookup.get(chunk["pmcid"], {})

            points.append(
                PointStruct(
                    id=point_id,
                    vector={
                        "dense": dense_vec.tolist(),
                        "sparse": SparseVector(
                            indices=sparse_vec.indices.tolist(),
                            values=sparse_vec.values.tolist(),
                        ),
                    },
                    payload={
                        "pmcid": chunk["pmcid"],
                        "section": chunk["section"],
                        "chunk_index": chunk["chunk_index"],
                        "text": chunk["text"],
                        "pub_year": paper_meta.get("pub_year"),
                        "journal": paper_meta.get("journal"),
                    },
                )
            )
            point_id += 1

        client.upsert(collection_name=COLLECTION, points=points)
        embedded_count += len(points)
        print(f"  Embedded and upserted {embedded_count}/{len(chunks)} chunks...")

    print(f"\nDone. {embedded_count} chunks embedded (dense+sparse) and stored in '{COLLECTION}'.")


if __name__ == "__main__":
    main()