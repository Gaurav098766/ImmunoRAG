# retrieve/hybrid.py
"""
L2 — Hybrid retrieval: BM25 sparse search + dense search, fused via
Reciprocal Rank Fusion (RRF).

Runs both searches independently against the same Qdrant collection
(dense embeddings via bge-small, sparse via Qdrant/bm25), then combines
their rankings using RRF — which fuses based on RANK POSITION rather
than raw scores, since cosine similarity and BM25 scores aren't on
comparable scales.

Run interactively:
    uv run python -m retrieve.hybrid
"""

from fastembed import TextEmbedding, SparseTextEmbedding
from qdrant_client import QdrantClient
from qdrant_client.models import SparseVector

from config import QDRANT_URL, COLLECTION, DENSE_MODEL, SPARSE_MODEL, TOP_K

RRF_K = 60          # standard RRF damping constant
FETCH_MULTIPLIER = 3  # fetch more from each individual search before fusing

_dense_embedder = None
_sparse_embedder = None


def get_dense_embedder() -> TextEmbedding:
    global _dense_embedder
    if _dense_embedder is None:
        _dense_embedder = TextEmbedding(model_name=DENSE_MODEL)
    return _dense_embedder


def get_sparse_embedder() -> SparseTextEmbedding:
    global _sparse_embedder
    if _sparse_embedder is None:
        _sparse_embedder = SparseTextEmbedding(model_name=SPARSE_MODEL)
    return _sparse_embedder


def _search_dense(client: QdrantClient, query: str, limit: int) -> list:
    """Run dense-only search, return raw Qdrant hit objects (ordered by rank)."""
    embedder = get_dense_embedder()
    query_vector = list(embedder.embed([query]))[0].tolist()

    return client.query_points(
        collection_name=COLLECTION,
        query=query_vector,
        using="dense",
        limit=limit,
    ).points


def _search_sparse(client: QdrantClient, query: str, limit: int) -> list:
    """Run sparse (BM25) search, return raw Qdrant hit objects (ordered by rank)."""
    embedder = get_sparse_embedder()
    sparse_vec = list(embedder.embed([query]))[0]

    query_sparse = SparseVector(
        indices=sparse_vec.indices.tolist(),
        values=sparse_vec.values.tolist(),
    )

    return client.query_points(
        collection_name=COLLECTION,
        query=query_sparse,
        using="sparse",
        limit=limit,
    ).points


def _rrf_fuse(*ranked_lists: list, k: int = RRF_K) -> dict:
    """
    Fuse multiple ranked lists of Qdrant hits using Reciprocal Rank Fusion.

    Each list is ordered best-to-worst (rank 0 = best). A doc's RRF score
    is the sum of 1/(k + rank) across every list it appears in — docs that
    rank well in either (or both) lists get pushed toward the top, and a
    doc only in one list still contributes rather than being dropped.

    Returns {point_id: (rrf_score, hit_object)} — hit_object taken from
    whichever list found it first, since payload is identical either way.
    """
    fused = {}
    for ranked_list in ranked_lists:
        for rank, hit in enumerate(ranked_list):
            rrf_contribution = 1.0 / (k + rank)
            if hit.id in fused:
                prev_score, prev_hit = fused[hit.id]
                fused[hit.id] = (prev_score + rrf_contribution, prev_hit)
            else:
                fused[hit.id] = (rrf_contribution, hit)
    return fused


def hybrid_search(query: str, top_k: int = TOP_K) -> list[dict]:
    """
    Run dense + sparse search independently, fuse via RRF, return the
    top_k fused results in the same shape as dense_search() for drop-in
    compatibility with downstream code (agent, API).
    """
    client = QdrantClient(url=QDRANT_URL)
    fetch_limit = top_k * FETCH_MULTIPLIER

    dense_hits = _search_dense(client, query, fetch_limit)
    sparse_hits = _search_sparse(client, query, fetch_limit)

    fused = _rrf_fuse(dense_hits, sparse_hits)

    # sort by RRF score descending, take top_k
    ranked = sorted(fused.values(), key=lambda pair: pair[0], reverse=True)[:top_k]

    results = []
    for rrf_score, hit in ranked:
        results.append({
            "rrf_score": rrf_score,
            "pmcid": hit.payload["pmcid"],
            "section": hit.payload["section"],
            "chunk_index": hit.payload["chunk_index"],
            "text": hit.payload["text"],
        })
    return results


def main():
    print("ImmunoRAG — Hybrid Retrieval (BM25 + Dense, RRF fusion)")
    print("Type a question, or 'quit' to exit.\n")

    while True:
        query = input("Query> ").strip()
        if query.lower() in ("quit", "exit"):
            break
        if not query:
            continue

        results = hybrid_search(query)
        print(f"\nTop {len(results)} results:\n")
        for i, r in enumerate(results, 1):
            print(f"[{i}] rrf={r['rrf_score']:.5f} | {r['pmcid']} | {r['section']}")
            print(f"    {r['text'][:150]}...\n")


if __name__ == "__main__":
    main()