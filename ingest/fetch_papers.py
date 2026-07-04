# ingest/fetch_papers.py
"""
L1 — Fetch open-access cancer immunotherapy papers from Europe PMC.

Searches Europe PMC for full-text-available papers matching a query,
then downloads the raw JATS full-text XML for each into data/raw/.

Run:
    uv run python -m ingest.fetch_papers
"""

import json
import time
from pathlib import Path

import httpx

# --- assumed config.py contents; adjust import if your names differ ---
from config import RAW_DATA_DIR  # a Path, e.g. Path("data/raw")

EUROPEPMC_SEARCH_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
EUROPEPMC_FULLTEXT_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/{id}/fullTextXML"

# Tune this query as you like — this one targets review + trial articles
# with immunotherapy in the title/abstract, open access only.
SEARCH_QUERY = (
    '"cancer immunotherapy" AND (SRC:PMC) AND OPEN_ACCESS:Y '
    'AND (PUB_TYPE:"Journal Article")'
)

MAX_PAPERS = 150          # keep small for L1 — you're proving the pipeline, not building a corpus
PAGE_SIZE = 25            # Europe PMC max per page is 1000, but small pages = easier to debug
REQUEST_DELAY_SECONDS = 0.4  # be polite; ~2.5 req/sec


def search_papers(query: str, max_results: int) -> list[dict]:
    """
    Query Europe PMC's /search endpoint and page through results using
    cursorMark pagination until max_results is hit or results run out.

    Returns a list of raw hit dicts (each has pmcid, title, authorString,
    journalTitle, pubYear, doi, etc. — whatever Europe PMC gives us).
    """
    results= []
    cursor_mark = "*"  # Europe PMC's pagination token; "*" means "start"

    with httpx.Client(timeout=30.0) as client:
        while len(results) < max_results:
            params = {
                "query": query,
                "format": "json",
                "pageSize": PAGE_SIZE,
                "cursorMark": cursor_mark,
                "resultType": "core",  # gives us fuller metadata per hit
            }
            resp = client.get(EUROPEPMC_SEARCH_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

            hits = data.get("resultList", {}).get("result", [])
            if not hits:
                break  # no more results

            results.extend(hits)

            next_cursor = data.get("nextCursorMark")
            if not next_cursor or next_cursor == cursor_mark:
                break  # Europe PMC signals "no more pages" this way
            cursor_mark = next_cursor

            time.sleep(REQUEST_DELAY_SECONDS)

    return results[:max_results]


def fetch_fulltext_xml(pmcid: str, client: httpx.Client) -> str | None:
    """
    Download raw JATS full-text XML for a single PMCID.
    Returns the XML as a string, or None if unavailable (some open-access
    hits still lack full text — we skip those rather than fail loudly).
    """
    url = EUROPEPMC_FULLTEXT_URL.format(id=pmcid)
    try:
        print(url)
        resp = client.get(url, timeout=30.0)
        print(resp)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.text
    except httpx.HTTPStatusError:
        return None


def save_xml(pmcid: str, xml_content: str, raw_dir: Path) -> Path:
    """Write raw XML to data/raw/{pmcid}.xml. Returns the path written."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    out_path = raw_dir / f"{pmcid}.xml"
    out_path.write_text(xml_content, encoding="utf-8")
    return out_path


def main():
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Searching Europe PMC: {SEARCH_QUERY!r}")
    hits = search_papers(SEARCH_QUERY, MAX_PAPERS)
    print(f"Found {len(hits)} candidate papers.")

    metadata = []
    fetched, skipped = 0, 0

    with httpx.Client() as client:
        for hit in hits:
            pmcid = hit.get("pmcid")
            if not pmcid:
                skipped += 1
                continue

            out_path = RAW_DATA_DIR / f"{pmcid}.xml"
            if out_path.exists():
                # already downloaded in a previous run — don't re-fetch
                fetched += 1
                metadata.append(_extract_metadata(hit))
                continue

            xml_content = fetch_fulltext_xml(pmcid, client)
            if xml_content is None:
                skipped += 1
                time.sleep(REQUEST_DELAY_SECONDS)
                continue

            save_xml(pmcid, xml_content, RAW_DATA_DIR)
            metadata.append(_extract_metadata(hit))
            fetched += 1

            print(f"  [{fetched}] saved {pmcid} — {hit.get('title', '')[:70]}")
            time.sleep(REQUEST_DELAY_SECONDS)

    metadata_path = RAW_DATA_DIR / "papers_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(f"\nDone. Fetched: {fetched}, Skipped (no full text): {skipped}")
    print(f"Metadata written to {metadata_path}")


def _extract_metadata(hit: dict) -> dict:
    """Pull just the fields we'll need later (L3 loads these into Postgres)."""
    return {
        # Unique identifiers
        "id": hit.get("id"),
        "pmcid": hit.get("pmcid"),
        "doi": hit.get("doi"),

        # Bibliographic info
        "title": hit.get("title"),
        "authors": hit.get("authorString"),
        "journal": (
            hit.get("journalTitle")
            or hit.get("journalInfo", {})
                  .get("journal", {})
                  .get("title")
        ),
        "pub_year": (
            hit.get("pubYear")
            or hit.get("journalInfo", {}).get("yearOfPublication")
        ),
        "publication_date": (
            hit.get("firstPublicationDate")
            or hit.get("electronicPublicationDate")
            or hit.get("journalInfo", {}).get("printPublicationDate")
        ),
        # Search / filtering
        "keywords": hit.get("keywordList", {}).get("keyword", []),
        "publication_types": hit.get("pubTypeList", {}).get("pubType", []),
        # Citation / ranking
        "cited_by_count": hit.get("citedByCount", 0),
        # Licensing
        "license": hit.get("license"),
        # URLs
        "full_text_urls": hit.get("fullTextUrlList", {}).get("fullTextUrl", []),
    }


if __name__ == "__main__":
    main()