# ingest/build_graph.py
"""
L6 — Extract entities and relationships from chunk text using Groq,
build a knowledge graph in Neo4j.

Processes a capped subset of chunks (Abstract/Introduction sections only,
up to MAX_CHUNKS) — full-corpus extraction would mean thousands of LLM
calls for chunks unlikely to contain clean factual relationships anyway.

Entity types: Drug, Target, CellType, Condition
Relationship types: TARGETS, TREATS, CAUSES, EXPRESSED_BY, ASSOCIATED_WITH

Requires Neo4j running: docker compose up -d neo4j

Run:
    uv run python -m ingest.build_graph
"""

import json
import time
from pathlib import Path
from groq import Groq, RateLimitError, APIError

from groq import Groq
from neo4j import GraphDatabase

from config import (
    PROCESSED_DATA_DIR, GROQ_API_KEY, GROQ_MODEL,
    NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD,
)

TARGET_SECTIONS = {"Abstract", "Introduction"}
MAX_CHUNKS = 500
DELAY_BETWEEN_CALLS = 0.3  # seconds, be polite to Groq's free tier

VALID_ENTITY_TYPES = {"Drug", "Target", "CellType", "Condition"}
VALID_RELATIONSHIPS = {"TARGETS", "TREATS", "CAUSES", "EXPRESSED_BY", "ASSOCIATED_WITH"}

EXTRACTION_SYSTEM_PROMPT = """You extract structured entities and relationships from
cancer immunotherapy research text.

Entity types (use EXACTLY these labels):
- Drug: a named drug or therapy (e.g. pembrolizumab, nivolumab, CAR-T cell therapy)
- Target: a protein/molecule a drug acts on (e.g. PD-1, PD-L1, CTLA-4)
- CellType: an immune cell type (e.g. macrophages, T cells, TAMs, MDSCs)
- Condition: a disease, cancer type, or side effect (e.g. lung cancer, cytokine
  release syndrome, hypothyroidism)

Relationship types (use EXACTLY these labels):
- TARGETS: Drug -> Target
- TREATS: Drug -> Condition
- CAUSES: Drug -> Condition (for side effects)
- EXPRESSED_BY: Target -> CellType
- ASSOCIATED_WITH: generic fallback for any other clear relationship

Rules:
- Only extract entities and relationships EXPLICITLY stated in the text. Never infer
  or guess relationships not directly supported by the sentence.
- If the text contains no clear, extractable entities/relationships, return an empty
  list for both.
- Return ONLY raw JSON, no markdown fences, no explanation, in exactly this shape:
{
  "entities": [{"name": "...", "type": "Drug|Target|CellType|Condition"}],
  "relationships": [{"source": "...", "relation": "TARGETS|TREATS|CAUSES|EXPRESSED_BY|ASSOCIATED_WITH", "target": "..."}]
}
"""


# Add near the top of build_graph.py, after imports
PROGRESS_FILE = Path("data/processed/graph_progress.json")


def load_progress() -> set:
    """Track which pmcid+chunk_index combos have already been processed."""
    if PROGRESS_FILE.exists():
        return set(json.loads(PROGRESS_FILE.read_text()))
    return set()


def save_progress(done: set):
    PROGRESS_FILE.write_text(json.dumps(list(done)))


_groq_client = None


def get_groq_client() -> Groq:
    global _groq_client
    if _groq_client is None:
        _groq_client = Groq(api_key=GROQ_API_KEY)
    return _groq_client


def load_target_chunks() -> list[dict]:
    """
    Load chunks from Abstract/Introduction sections only, across all papers,
    capped at MAX_CHUNKS total.
    """
    chunk_files = sorted(PROCESSED_DATA_DIR.glob("*_chunks.json"))
    selected = []

    for f in chunk_files:
        chunks = json.loads(f.read_text())
        for chunk in chunks:
            if chunk["section"] in TARGET_SECTIONS:
                selected.append(chunk)
                if len(selected) >= MAX_CHUNKS:
                    return selected

    return selected


def extract_entities_relationships(text: str) -> dict | None:
    """
    Send one chunk's text to Groq, parse the returned JSON.
    Returns None if extraction failed or produced invalid JSON.
    Logs the actual failure reason instead of silently swallowing it.
    Raises RateLimitError so the caller can stop the whole run rather
    than silently failing every remaining chunk.
    """
    client = get_groq_client()
    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            temperature=0,
        )
        raw = response.choices[0].message.content.strip()
        raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(raw)

        if "entities" not in parsed or "relationships" not in parsed:
            print("    [skip] response missing expected keys")
            return None
        return parsed

    except RateLimitError as e:
        print(f"    [RATE LIMIT] {str(e)[:150]}")
        raise
    except json.JSONDecodeError as e:
        print(f"    [JSON PARSE ERROR] {str(e)[:150]}")
        return None
    except APIError as e:
        print(f"    [API ERROR] {str(e)[:150]}")
        return None


def validate_extraction(data: dict) -> dict:
    """
    Filter out any entities/relationships that don't match our fixed schema
    (defensive — never trust LLM output blindly, same principle as analytics.py).
    """
    valid_entities = [
        e for e in data.get("entities", [])
        if e.get("type") in VALID_ENTITY_TYPES and e.get("name")
    ]
    valid_entity_names = {e["name"] for e in valid_entities}

    valid_relationships = [
        r for r in data.get("relationships", [])
        if r.get("relation") in VALID_RELATIONSHIPS
        and r.get("source") in valid_entity_names
        and r.get("target") in valid_entity_names
    ]

    return {"entities": valid_entities, "relationships": valid_relationships}


def write_to_neo4j(driver, data: dict, pmcid: str):
    """
    Upsert entities as nodes and relationships as edges into Neo4j.
    MERGE ensures re-running this script doesn't create duplicates —
    the same entity (e.g. "PD-1") mentioned across many chunks becomes
    ONE node, not one per mention.
    """
    with driver.session() as session:
        for entity in data["entities"]:
            session.run(
                f"MERGE (n:{entity['type']} {{name: $name}})",
                name=entity["name"],
            )

        for rel in data["relationships"]:
            session.run(
                f"""
                MATCH (a {{name: $source}}), (b {{name: $target}})
                MERGE (a)-[r:{rel['relation']}]->(b)
                SET r.source_pmcid = $pmcid
                """,
                source=rel["source"],
                target=rel["target"],
                pmcid=pmcid,
            )


def main():
    print("Loading Abstract/Introduction chunks...")
    chunks = load_target_chunks()
    print(f"Selected {len(chunks)} chunks for extraction (capped at {MAX_CHUNKS}).")


    done = load_progress()
    print(f"Already processed in a previous run: {len(done)} chunks.")

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    total_entities = 0
    total_relationships = 0
    skipped = 0
    i = 0

    try:
        for i, chunk in enumerate(chunks, 1):
            chunk_key = f"{chunk['pmcid']}::{chunk['section']}::{chunk['chunk_index']}"
            if chunk_key in done:
                continue

            raw = extract_entities_relationships(chunk["text"])
            if raw is None:
                skipped += 1
                done.add(chunk_key)
                time.sleep(DELAY_BETWEEN_CALLS)
                continue

            validated = validate_extraction(raw)
            if not validated["entities"]:
                skipped += 1
                done.add(chunk_key)
                time.sleep(DELAY_BETWEEN_CALLS)
                continue

            write_to_neo4j(driver, validated, chunk["pmcid"])
            total_entities += len(validated["entities"])
            total_relationships += len(validated["relationships"])
            done.add(chunk_key)

            if i % 50 == 0:
                print(f"  Processed {i}/{len(chunks)} chunks...")
                save_progress(done)  # periodic save, don't lose progress on crash

            time.sleep(DELAY_BETWEEN_CALLS)
    except RateLimitError:
        print(f"\nStopped early due to rate limit — processed {i}/{len(chunks)} chunks before hitting the daily cap.")
    finally:
        save_progress(done)  # always save final state, even on early stop
        driver.close()

    print(f"\nDone. Processed {len(chunks)} chunks, skipped {skipped} (no valid extraction).")
    print(f"Total entities upserted: {total_entities} (mentions, not unique count)")
    print(f"Total relationships upserted: {total_relationships} (mentions, not unique count)")


if __name__ == "__main__":
    main()