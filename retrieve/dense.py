# retrieve/dense.py
"""
L1/L2 — Naive dense retrieval over the Qdrant chunk collection.

Embeds a query with the same model used at ingest time (bge-small-en-v1.5)
and returns the top-k most similar chunks by cosine similarity, searching
only the "dense" named vector (collection also holds a "sparse" vector
per point as of L2 — see retrieve/hybrid.py for combined search).

Run interactively:
    uv run python -m retrieve.dense
"""

from fastembed import TextEmbedding
from qdrant_client import QdrantClient

from config import QDRANT_URL, COLLECTION, DENSE_MODEL, TOP_K

_embedder = None  # lazy-loaded singleton, avoids reloading the model per call


def get_embedder() -> TextEmbedding:
    global _embedder
    if _embedder is None:
        _embedder = TextEmbedding(model_name=DENSE_MODEL)
    return _embedder


def dense_search(query: str, top_k: int = TOP_K) -> list[dict]:
    """
    Embed the query and return the top_k most similar chunks from Qdrant,
    searching only the "dense" named vector.
    """
    embedder = get_embedder()
    query_vector = list(embedder.embed([query]))[0].tolist()

    client = QdrantClient(url=QDRANT_URL)
    hits = client.query_points(
        collection_name=COLLECTION,
        query=query_vector,
        using="dense",  # <-- NEW: specify which named vector to search
        limit=top_k,
    ).points

    results = []
    for hit in hits:
        results.append({
            "score": hit.score,
            "pmcid": hit.payload["pmcid"],
            "section": hit.payload["section"],
            "chunk_index": hit.payload["chunk_index"],
            "text": hit.payload["text"],
        })
    return results


def main():
    print("ImmunoRAG — Dense Retrieval")
    print("Type a question, or 'quit' to exit.\n")

    while True:
        query = input("Query> ").strip()
        if query.lower() in ("quit", "exit"):
            break
        if not query:
            continue

        results = dense_search(query)
        print(f"\nTop {len(results)} results:\n")
        for i, r in enumerate(results, 1):
            print(f"[{i}] score={r['score']:.4f} | {r['pmcid']} | {r['section']}")
            print(f"    {r['text'][:150]}...\n")


if __name__ == "__main__":
    main()