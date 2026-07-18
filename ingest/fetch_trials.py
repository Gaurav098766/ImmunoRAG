# ingest/fetch_trials.py
"""
L4 — Fetch cancer immunotherapy clinical trials from ClinicalTrials.gov API v2
and load directly into the `trials` Postgres table.

Run:
    uv run python -m ingest.fetch_trials
"""

import httpx
import psycopg

from config import POSTGRES_DSN

CTGOV_API_URL = "https://clinicaltrials.gov/api/v2/studies"
SEARCH_QUERY = "cancer immunotherapy"
MAX_TRIALS = 200
PAGE_SIZE = 50

UPSERT_SQL = """
    INSERT INTO trials (
        nct_id, title, status, phase, sponsor, conditions, interventions,
        enrollment_count, start_date, completion_date
    )
    VALUES (
        %(nct_id)s, %(title)s, %(status)s, %(phase)s, %(sponsor)s,
        %(conditions)s, %(interventions)s, %(enrollment_count)s,
        %(start_date)s, %(completion_date)s
    )
    ON CONFLICT (nct_id) DO UPDATE SET
        title = EXCLUDED.title,
        status = EXCLUDED.status,
        phase = EXCLUDED.phase,
        sponsor = EXCLUDED.sponsor,
        conditions = EXCLUDED.conditions,
        interventions = EXCLUDED.interventions,
        enrollment_count = EXCLUDED.enrollment_count,
        start_date = EXCLUDED.start_date,
        completion_date = EXCLUDED.completion_date;
"""


def fetch_trials(query: str, max_results: int) -> list[dict]:
    """Page through ClinicalTrials.gov API v2 search results."""
    studies = []
    page_token = None

    with httpx.Client(timeout=30.0) as client:
        while len(studies) < max_results:
            params = {
                "query.term": query,
                "pageSize": PAGE_SIZE,
                "format": "json",
            }
            if page_token:
                params["pageToken"] = page_token

            resp = client.get(CTGOV_API_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

            page_studies = data.get("studies", [])
            if not page_studies:
                break

            studies.extend(page_studies)

            page_token = data.get("nextPageToken")
            if not page_token:
                break

    return studies[:max_results]


def extract_trial_record(study: dict) -> dict | None:
    """Pull the fields we care about out of one study's nested JSON."""
    protocol = study.get("protocolSection", {})

    ident = protocol.get("identificationModule", {})
    nct_id = ident.get("nctId")
    if not nct_id:
        return None

    status_mod = protocol.get("statusModule", {})
    design_mod = protocol.get("designModule", {})
    sponsor_mod = protocol.get("sponsorCollaboratorsModule", {})
    conditions_mod = protocol.get("conditionsModule", {})
    arms_mod = protocol.get("armsInterventionsModule", {})

    phases = design_mod.get("phases", [])
    phase = phases[0] if phases else None

    enrollment_info = design_mod.get("enrollmentInfo", {})
    enrollment_count = enrollment_info.get("count")

    lead_sponsor = sponsor_mod.get("leadSponsor", {})

    interventions = [
        i.get("name") for i in arms_mod.get("interventions", []) if i.get("name")
    ]

    return {
        "nct_id": nct_id,
        "title": ident.get("briefTitle"),
        "status": status_mod.get("overallStatus"),
        "phase": phase,
        "sponsor": lead_sponsor.get("name"),
        "conditions": conditions_mod.get("conditions", []),
        "interventions": interventions,
        "enrollment_count": enrollment_count,
        "start_date": status_mod.get("startDateStruct", {}).get("date"),
        "completion_date": status_mod.get("completionDateStruct", {}).get("date"),
    }


def main():
    print(f"Fetching trials from ClinicalTrials.gov: {SEARCH_QUERY!r}")
    studies = fetch_trials(SEARCH_QUERY, MAX_TRIALS)
    print(f"Found {len(studies)} trials.")

    records = []
    skipped = 0
    for study in studies:
        record = extract_trial_record(study)
        if record is None:
            skipped += 1
            continue
        records.append(record)

    print(f"Extracted {len(records)} valid records ({skipped} skipped, no NCT ID).")

    with psycopg.connect(POSTGRES_DSN) as conn:
        with conn.cursor() as cur:
            for record in records:
                cur.execute(UPSERT_SQL, record)
        conn.commit()

    print(f"Done. Upserted {len(records)} trials into 'trials' table.")


if __name__ == "__main__":
    main()