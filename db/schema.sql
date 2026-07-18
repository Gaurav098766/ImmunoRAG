-- db/schema.sql
-- L3 — Paper-level metadata table.
-- One row per paper; chunk-level data stays in Qdrant.
-- Populated by ingest/load_metadata.py from data/raw/papers_metadata.json.

CREATE TABLE IF NOT EXISTS papers (
    pmcid               TEXT PRIMARY KEY,
    doi                 TEXT,
    title               TEXT NOT NULL,
    authors             TEXT,
    journal             TEXT,
    pub_year            INTEGER,
    publication_date    TEXT,
    keywords            TEXT[],
    publication_types   TEXT[],
    cited_by_count      INTEGER DEFAULT 0,
    license             TEXT,
    full_text_urls      JSONB,
    created_at          TIMESTAMPTZ DEFAULT now()
);

-- Indexes for the filters we'll actually query on in retrieve/filtered.py
CREATE INDEX IF NOT EXISTS idx_papers_pub_year ON papers (pub_year);
CREATE INDEX IF NOT EXISTS idx_papers_journal ON papers (journal);
CREATE INDEX IF NOT EXISTS idx_papers_license ON papers (license);


-- L4 — Clinical trials table (ClinicalTrials.gov data)
-- Structurally distinct from papers (phase, enrollment, sponsor, status)
-- but lives in the same Postgres DB, queryable via the same NL->SQL layer.

CREATE TABLE IF NOT EXISTS trials (
    nct_id              TEXT PRIMARY KEY,
    title               TEXT NOT NULL,
    status              TEXT,
    phase               TEXT,
    sponsor             TEXT,
    conditions          TEXT[],
    interventions       TEXT[],
    enrollment_count    INTEGER,
    start_date          TEXT,
    completion_date     TEXT,
    created_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_trials_status ON trials (status);
CREATE INDEX IF NOT EXISTS idx_trials_phase ON trials (phase);