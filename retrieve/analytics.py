# retrieve/analytics.py
"""
L4 — Natural language to SQL analytics over papers + trials tables.

Translates a natural-language question into a SQL SELECT query using Groq,
validates it's read-only and safe, executes it against a restricted
read-only Postgres role, and returns results.

Requires Postgres running: docker compose up -d postgres

Run interactively:
    uv run python -m retrieve.analytics
"""

import re

import psycopg
from groq import Groq

from config import GROQ_API_KEY, GROQ_MODEL, POSTGRES_READONLY_DSN

QUERY_TIMEOUT_MS = 5000  # 5 seconds — generous for this corpus size, prevents runaway queries

SCHEMA_DESCRIPTION = """
Table: papers
  pmcid               TEXT PRIMARY KEY
  doi                 TEXT
  title               TEXT
  authors             TEXT
  journal             TEXT
  pub_year            INTEGER (nullable — some papers have unknown year)
  publication_date    TEXT
  keywords            TEXT[]
  publication_types   TEXT[]
  cited_by_count      INTEGER
  license             TEXT
  full_text_urls      JSONB

Table: trials
  nct_id              TEXT PRIMARY KEY
  title               TEXT
  status              TEXT (e.g. 'RECRUITING', 'COMPLETED', 'TERMINATED')
  phase               TEXT (e.g. 'PHASE1', 'PHASE2', 'PHASE3')
  sponsor             TEXT
  conditions          TEXT[]
  interventions       TEXT[]
  enrollment_count    INTEGER
  start_date          TEXT
  completion_date     TEXT
"""

SYSTEM_PROMPT = f"""You are a SQL query generator for a PostgreSQL database.

Database schema:
{SCHEMA_DESCRIPTION}

Rules:
- Generate ONLY a single SELECT statement. Never generate INSERT, UPDATE, DELETE,
  DROP, ALTER, TRUNCATE, GRANT, or CREATE statements under any circumstances.
- Never generate multiple statements separated by semicolons.
- Use only the tables and columns listed above — do not invent column names.
- Return ONLY the raw SQL query, no explanation, no markdown code fences, no comments.
- If the question cannot be answered with a SELECT query on this schema, return
  exactly: NOT_SUPPORTED
"""

FORBIDDEN_KEYWORDS = {
    "insert", "update", "delete", "drop", "alter",
    "truncate", "grant", "create", "revoke",
}

_groq_client = None


def get_groq_client() -> Groq:
    global _groq_client
    if _groq_client is None:
        _groq_client = Groq(api_key=GROQ_API_KEY)
    return _groq_client


def generate_sql(question: str) -> str | None:
    """
    Ask Groq to translate a natural-language question into SQL.
    Returns None if Groq indicates the question isn't answerable via SQL.
    """
    client = get_groq_client()
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        temperature=0,  # deterministic — we want consistent SQL, not creative SQL
    )

    sql = response.choices[0].message.content.strip()

    # strip markdown fences if the model added them despite instructions
    sql = re.sub(r"^```sql\s*|\s*```$", "", sql, flags=re.IGNORECASE).strip()

    if sql == "NOT_SUPPORTED":
        return None
    return sql


def validate_sql(sql: str) -> tuple[bool, str]:
    """
    Code-level safety check — never trust the LLM's output alone.
    Returns (is_valid, reason_if_invalid).
    """
    normalized = sql.strip().lower()

    if not normalized.startswith("select"):
        return False, "Query does not start with SELECT."

    # reject multiple statements (semicolon anywhere except optionally at the very end)
    stripped = normalized.rstrip(";").strip()
    if ";" in stripped:
        return False, "Multiple statements detected (semicolon found mid-query)."

    for keyword in FORBIDDEN_KEYWORDS:
        # word-boundary match so e.g. "updated_at" doesn't false-trigger on "update"
        if re.search(rf"\b{keyword}\b", normalized):
            return False, f"Forbidden keyword detected: {keyword}"

    return True, ""


def execute_sql(sql: str) -> list[dict]:
    """
    Execute a validated SELECT query against the READ-ONLY Postgres role.
    Statement timeout enforced to prevent runaway queries.
    """
    with psycopg.connect(POSTGRES_READONLY_DSN) as conn:
        with conn.cursor() as cur:
            cur.execute(f"SET statement_timeout = {QUERY_TIMEOUT_MS}")
            cur.execute(sql)
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            return [dict(zip(columns, row)) for row in rows]


def analytics_query(question: str) -> dict:
    """
    Full pipeline: NL question -> SQL -> validate -> execute -> results.
    Returns a dict with 'sql', 'results', and 'error' (None if successful).
    """
    sql = generate_sql(question)
    if sql is None:
        return {"sql": None, "results": None, "error": "Question not supported by available schema."}

    is_valid, reason = validate_sql(sql)
    if not is_valid:
        return {"sql": sql, "results": None, "error": f"Rejected unsafe SQL: {reason}"}

    try:
        results = execute_sql(sql)
        return {"sql": sql, "results": results, "error": None}
    except psycopg.Error as e:
        return {"sql": sql, "results": None, "error": f"SQL execution failed: {e}"}


def main():
    print("ImmunoRAG — Analytics (NL -> SQL)")
    print("Ask a question about papers or trials, or 'quit' to exit.\n")

    while True:
        question = input("Query> ").strip()
        if question.lower() in ("quit", "exit"):
            break
        if not question:
            continue

        result = analytics_query(question)

        print(f"\nGenerated SQL: {result['sql']}")
        if result["error"]:
            print(f"Error: {result['error']}\n")
            continue

        rows = result["results"]
        print(f"Results ({len(rows)} rows):")
        for row in rows[:20]:  # cap display, don't flood terminal
            print(f"  {row}")
        if len(rows) > 20:
            print(f"  ... and {len(rows) - 20} more rows")
        print()


if __name__ == "__main__":
    main()