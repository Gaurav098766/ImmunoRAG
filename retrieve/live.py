# retrieve/live.py
"""
L5 — Live openFDA API queries with Redis caching.

Queries openFDA's drug adverse event and label endpoints for a given drug,
caching responses in Redis (TTL-based) to avoid redundant API calls.

Requires Redis running: docker compose up -d redis

Run interactively:
    uv run python -m retrieve.live
"""

import json

import httpx
import redis

from config import REDIS_URL, OPENFDA_BASE_URL, CACHE_TTL_SECONDS

_redis_client = None


def get_redis_client() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    return _redis_client


def _cache_key(endpoint: str, drug_name: str) -> str:
    return f"openfda:{endpoint}:{drug_name.strip().lower()}"


def _get_cached(key: str) -> dict | None:
    """Try to read from Redis. Returns None on cache miss OR if Redis is unavailable."""
    try:
        client = get_redis_client()
        cached = client.get(key)
        return json.loads(cached) if cached else None
    except redis.RedisError:
        return None  # fail open — treat as cache miss, don't crash the query


def _set_cached(key: str, value: dict):
    """Write to Redis. Silently no-ops if Redis is unavailable."""
    try:
        client = get_redis_client()
        client.set(key, json.dumps(value), ex=CACHE_TTL_SECONDS)  # ex= replaces deprecated setex
    except redis.RedisError:
        pass


def fetch_adverse_events(drug_name: str, limit: int = 5) -> dict:
    """
    Query openFDA's drug adverse event endpoint for a given drug.
    Checks Redis cache first; falls back to live API on miss.
    """
    cache_key = _cache_key("adverse_events", drug_name)
    cached = _get_cached(cache_key)
    if cached is not None:
        return {**cached, "_cache_hit": True}

    url = f"{OPENFDA_BASE_URL}/drug/event.json"
    params = {
        "search": f'patient.drug.medicinalproduct:"{drug_name}"',
        "limit": limit,
    }

    with httpx.Client(timeout=15.0) as client:
        resp = client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    result = {
        "drug_name": drug_name,
        "total_reports": data.get("meta", {}).get("results", {}).get("total", 0),
        "results": data.get("results", []),
    }

    _set_cached(cache_key, result)
    return {**result, "_cache_hit": False}


def fetch_drug_label(drug_name: str) -> dict:
    """
    Query openFDA's drug label endpoint for a given drug (indications,
    warnings, dosage info as reported in the official label).
    Checks Redis cache first; falls back to live API on miss.
    """
    cache_key = _cache_key("label", drug_name)
    cached = _get_cached(cache_key)
    if cached is not None:
        return {**cached, "_cache_hit": True}

    url = f"{OPENFDA_BASE_URL}/drug/label.json"
    params = {
        "search": f'openfda.generic_name:"{drug_name}"',
        "limit": 1,
    }

    with httpx.Client(timeout=15.0) as client:
        resp = client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    results = data.get("results", [])
    label_info = results[0] if results else {}

    result = {
        "drug_name": drug_name,
        "indications": label_info.get("indications_and_usage", ["Not found"])[0][:500] if label_info.get("indications_and_usage") else "Not found",
        "warnings": label_info.get("warnings", ["Not found"])[0][:500] if label_info.get("warnings") else "Not found",
    }

    _set_cached(cache_key, result)
    return {**result, "_cache_hit": False}


def main():
    print("ImmunoRAG — Live openFDA Queries (cached via Redis)")
    print("Format: <drug_name> | events   OR   <drug_name> | label")
    print("Example: pembrolizumab | events")
    print("Type 'quit' to exit.\n")

    while True:
        raw = input("Query> ").strip()
        if raw.lower() in ("quit", "exit"):
            break
        if not raw or "|" not in raw:
            continue

        drug_name, mode = [p.strip() for p in raw.split("|", 1)]

        if mode == "events":
            result = fetch_adverse_events(drug_name)
            print(f"\n[cache_hit={result['_cache_hit']}] Total reports: {result['total_reports']}")
            for r in result["results"][:3]:
                reactions = [rx.get("reactionmeddrapt") for rx in r.get("patient", {}).get("reaction", [])]
                print(f"  - Reactions: {reactions}")
        elif mode == "label":
            result = fetch_drug_label(drug_name)
            print(f"\n[cache_hit={result['_cache_hit']}]")
            print(f"  Indications: {result['indications'][:200]}...")
            print(f"  Warnings: {result['warnings'][:200]}...")
        print()


if __name__ == "__main__":
    main()