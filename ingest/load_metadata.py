# ingest/load_metadata.py
"""
L3 — Load paper metadata from data/raw/papers_metadata.json into PostgreSQL.

Reads the metadata JSON produced by fetch_papers.py and upserts one row
per paper into the `papers` table. Idempotent — safe to re-run; existing
rows are updated rather than duplicated.

Requires Postgres running: docker compose up -d postgres

Run:
    uv run python -m ingest.load_metadata
"""

import json

import psycopg

from config import RAW_DATA_DIR, POSTGRES_DSN

METADATA_PATH = RAW_DATA_DIR / "papers_metadata.json"

UPSERT_SQL = """
    INSERT INTO papers (
        pmcid, doi, title, authors, journal, pub_year, publication_date,
        keywords, publication_types, cited_by_count, license, full_text_urls
    )
    VALUES (
        %(pmcid)s, %(doi)s, %(title)s, %(authors)s, %(journal)s, %(pub_year)s,
        %(publication_date)s, %(keywords)s, %(publication_types)s,
        %(cited_by_count)s, %(license)s, %(full_text_urls)s
    )
    ON CONFLICT (pmcid) DO UPDATE SET
        doi = EXCLUDED.doi,
        title = EXCLUDED.title,
        authors = EXCLUDED.authors,
        journal = EXCLUDED.journal,
        pub_year = EXCLUDED.pub_year,
        publication_date = EXCLUDED.publication_date,
        keywords = EXCLUDED.keywords,
        publication_types = EXCLUDED.publication_types,
        cited_by_count = EXCLUDED.cited_by_count,
        license = EXCLUDED.license,
        full_text_urls = EXCLUDED.full_text_urls;
"""


def normalize_record(paper: dict) -> dict:
    """
    Prepare one paper's metadata dict for insertion:
    - pub_year: 0 (a data artifact, not a real year) becomes NULL
    - full_text_urls: serialized to JSON string for the JSONB column
    """
    pub_year = paper.get("pub_year")
    if not pub_year:  # catches 0, None, "" — all mean "unknown"
        pub_year = None

    return {
        "pmcid": paper["pmcid"],
        "doi": paper.get("doi"),
        "title": paper.get("title"),
        "authors": paper.get("authors"),
        "journal": paper.get("journal"),
        "pub_year": pub_year,
        "publication_date": paper.get("publication_date"),
        "keywords": paper.get("keywords") or [],
        "publication_types": paper.get("publication_types") or [],
        "cited_by_count": paper.get("cited_by_count", 0),
        "license": paper.get("license"),
        "full_text_urls": json.dumps(paper.get("full_text_urls") or []),
    }


def main():
    print(f"Loading metadata from {METADATA_PATH}...")
    papers = json.loads(METADATA_PATH.read_text())
    print(f"Found {len(papers)} paper records.")

    with psycopg.connect(POSTGRES_DSN) as conn:
        with conn.cursor() as cur:
            for paper in papers:
                record = normalize_record(paper)
                cur.execute(UPSERT_SQL, record)
        conn.commit()

    print(f"Done. Upserted {len(papers)} rows into 'papers' table.")


if __name__ == "__main__":
    main()