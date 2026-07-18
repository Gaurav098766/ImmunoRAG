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


-- L4 — Read-only role for NL->SQL query execution.
-- Used exclusively by retrieve/analytics.py — never the main app user,
-- which retains full read/write for ingestion scripts (load_metadata.py,
-- fetch_trials.py, etc.). Defense-in-depth: even if code-level SQL
-- validation had a bug, the database itself refuses non-SELECT statements
-- for this role.

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'immunorag_readonly') THEN
        CREATE ROLE immunorag_readonly WITH LOGIN PASSWORD 'readonly_dev_pw';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE immunorag TO immunorag_readonly;
GRANT USAGE ON SCHEMA public TO immunorag_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO immunorag_readonly;

-- Ensures any FUTURE tables created by the main user are also
-- automatically readable by this role, without needing to re-grant
-- manually every time the schema grows (L5+ will add more tables).
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO immunorag_readonly;