# retrieve/filtered.py
"""
L3 — Hybrid retrieval (dense + sparse + RRF) with optional metadata filters.

Same fusion approach as retrieve/hybrid.py, but supports filtering by
journal, minimum publication year, and/or section — applied as hard
constraints via Qdrant's native payload filtering, before RRF fusion.

Run interactively:
    uv run python -m retrieve.filtered
"""

from fastembed import TextEmbedding, SparseTextEmbedding
from qdrant_client import QdrantClient
from qdrant_client.models import SparseVector, Filter, FieldCondition, MatchValue, Range

from config import QDRANT_URL, COLLECTION, DENSE_MODEL, SPARSE_MODEL, TOP_K

RRF_K = 60
FETCH_MULTIPLIER = 3

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


def build_filter(journal: str = None, min_pub_year: int = None, section: str = None) -> Filter | None:
    """
    Translate optional filter args into a Qdrant Filter object.
    Returns None if no filters were provided (no constraint applied).
    """
    conditions = []

    if journal is not None:
        conditions.append(FieldCondition(key="journal", match=MatchValue(value=journal)))

    if min_pub_year is not None:
        conditions.append(FieldCondition(key="pub_year", range=Range(gte=min_pub_year)))

    if section is not None:
        conditions.append(FieldCondition(key="section", match=MatchValue(value=section)))

    if not conditions:
        return None

    return Filter(must=conditions)


def _search_dense(client, query, limit, query_filter):
    embedder = get_dense_embedder()
    query_vector = list(embedder.embed([query]))[0].tolist()
    return client.query_points(
        collection_name=COLLECTION,
        query=query_vector,
        using="dense",
        limit=limit,
        query_filter=query_filter,
    ).points


def _search_sparse(client, query, limit, query_filter):
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
        query_filter=query_filter,
    ).points


def _rrf_fuse(*ranked_lists, k: int = RRF_K) -> dict:
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


def filtered_search(
    query: str,
    top_k: int = TOP_K,
    journal: str = None,
    min_pub_year: int = None,
    section: str = None,
) -> list[dict]:
    """
    Hybrid search with optional hard-constraint metadata filters.
    Omit all filter args for plain unfiltered hybrid search.
    """
    client = QdrantClient(url=QDRANT_URL)
    fetch_limit = top_k * FETCH_MULTIPLIER
    query_filter = build_filter(journal, min_pub_year, section)

    dense_hits = _search_dense(client, query, fetch_limit, query_filter)
    sparse_hits = _search_sparse(client, query, fetch_limit, query_filter)

    fused = _rrf_fuse(dense_hits, sparse_hits)
    ranked = sorted(fused.values(), key=lambda pair: pair[0], reverse=True)[:top_k]

    results = []
    for rrf_score, hit in ranked:
        results.append({
            "rrf_score": rrf_score,
            "pmcid": hit.payload["pmcid"],
            "section": hit.payload["section"],
            "chunk_index": hit.payload["chunk_index"],
            "journal": hit.payload.get("journal"),
            "pub_year": hit.payload.get("pub_year"),
            "text": hit.payload["text"],
        })
    return results


def main():
    print("ImmunoRAG — Filtered Hybrid Retrieval")
    print("Enter a query, optionally followed by filters.")
    print("Format: <query> | journal=<name> | year>=<int> | section=<name>")
    print("Example: macrophages in TME | year>=2024")
    print("Type 'quit' to exit.\n")

    while True:
        raw = input("Query> ").strip()
        if raw.lower() in ("quit", "exit"):
            break
        if not raw:
            continue

        parts = [p.strip() for p in raw.split("|")]
        query = parts[0]
        journal = None
        min_pub_year = None
        section = None

        for part in parts[1:]:
            if part.startswith("journal="):
                journal = part.split("=", 1)[1]
            elif part.startswith("year>="):
                min_pub_year = int(part.split(">=", 1)[1])
            elif part.startswith("section="):
                section = part.split("=", 1)[1]

        results = filtered_search(query, journal=journal, min_pub_year=min_pub_year, section=section)
        print(f"\nTop {len(results)} results (journal={journal}, year>={min_pub_year}, section={section}):\n")
        for i, r in enumerate(results, 1):
            print(f"[{i}] rrf={r['rrf_score']:.5f} | {r['pmcid']} | {r['journal']} ({r['pub_year']}) | {r['section']}")
            print(f"    {r['text'][:150]}...\n")


if __name__ == "__main__":
    main()