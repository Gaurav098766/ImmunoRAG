# ImmunoRAG

A progressive, 12-level Retrieval-Augmented Generation (RAG) system built over
**cancer immunotherapy research literature** — engineered from the ground up to run
entirely on constrained hardware: **CPU-only, 8GB RAM, no GPU.**

No self-hosted LLMs. No multi-GB models. Every design choice — from the embedding
model to the vector database to the LLM API — was made to prove that a genuinely
capable, multi-modal RAG system doesn't require expensive infrastructure.

---

## What it actually does

ImmunoRAG answers questions about cancer immunotherapy by combining several
different ways of finding and reasoning over information, depending on what the
question actually needs:

- **Search research papers** by both meaning and exact keyword matching (e.g. "how
  does PD-1 blockade work" finds relevant text even without exact keyword overlap)
- **Filter results** by publication year, journal, or paper section
- **Answer data questions in plain English** — "how many Phase 3 trials exist for
  CAR-T therapies?" gets translated into a real SQL query and answered directly
- **Pull live drug safety data** from the FDA's public adverse-event database,
  cached for speed
- **Traverse a knowledge graph** connecting drugs to the biological targets they
  act on, the cell types involved, and the conditions they treat/cause — built by
  having an LLM read the literature and extract these relationships
- **Route each question automatically** to whichever of the above tools actually
  fits, via an AI agent, and expose the whole thing through a web API

---

## Why build it this way

Cancer immunotherapy is a genuinely complex, fast-moving field — spanning
published research, actively-running clinical trials, and real-world drug safety
data that all update independently of each other. A system that only searches
papers would miss ongoing trials; a system that only has trial data would miss
mechanistic detail from the literature. ImmunoRAG combines these deliberately,
and treats "can this run on modest, affordable hardware" as a first-class design
constraint, not an afterthought — every model and tool choice was picked for a
strong balance of quality and efficiency, not by defaulting to the biggest/most
expensive option.

---

## Architecture — 12 progressive levels

The system is built level by level, from a basic RAG pipeline (L1) to a fully
agentic, production-shaped system (L12). Each level is fully working and
deployable on its own before the next is added — nothing is ever a rewrite.

| Level | What it adds |
|---|---|
| **L1** | Naive dense retrieval — semantic search over embedded paper chunks |
| **L2** | Hybrid retrieval — adds keyword (BM25) search, fused with semantic search |
| **L3** | Metadata filtering — filter results by journal, publication year, section |
| **L4** | Analytics — natural-language questions answered via generated SQL queries |
| **L5** | Live data + caching — real-time FDA drug safety data, Redis-cached |
| **L6** | Knowledge graph — LLM-extracted drug/target/cell-type/condition relationships in Neo4j |
| **L7** | Agentic routing — an AI agent dynamically picks the right tool per question |
| **L8** | Precision — query expansion (HyDE) + reranking for higher-quality answers, served via a FastAPI web API |
| **L9** | Observability — full tracing/monitoring of the system's behavior |
| **L10** | Extended agentic reasoning — multi-step, self-correcting question answering |
| **L11** | Multi-modal — incorporating tables and figures from papers, not just text |
| **L12** | Embedding fine-tuning — specializing the search model further for this domain |

**Current status:** Levels 1–6 complete and verified. Actively building toward L8.

---

## Tech stack

Every choice below was made with the 8GB RAM / no-GPU constraint in mind:

- **LLM:** [Groq](https://groq.com) API (free tier) — fast inference, no local model needed
- **Embeddings:** `BAAI/bge-small-en-v1.5` via [fastembed](https://github.com/qdrant/fastembed) — small, CPU-friendly, ONNX runtime
- **Vector search:** [Qdrant](https://qdrant.tech) — hybrid dense + sparse (BM25) search, lightweight, self-hosted
- **Relational data:** PostgreSQL 16 — paper metadata, clinical trial data
- **Knowledge graph:** Neo4j 5 Community Edition (memory-capped)
- **Cache:** Redis — for live external API responses
- **Agent framework:** LangGraph
- **Web framework:** FastAPI
- **Document parsing:** lxml, parsing raw JATS XML from Europe PMC

## Data sources

- **[Europe PMC](https://europepmc.org)** — 148 open-access cancer immunotherapy
  research papers, full text
- **[ClinicalTrials.gov](https://clinicaltrials.gov)** — registered clinical trial data
  (phase, status, sponsor, enrollment)
- **[openFDA](https://open.fda.gov)** — real-world drug adverse event reports and
  official FDA drug labeling

---

## Running it locally

```bash
# clone and install dependencies
git clone <this-repo-url>
cd immunorag
uv sync

# copy and fill in environment variables
cp .env.example .env

# bring up the services this level needs (see docker-compose.yml)
docker compose up -d qdrant postgres

# run the ingestion pipeline
uv run python -m ingest.fetch_papers
uv run python -m ingest.parse
uv run python -m ingest.chunk
uv run python -m ingest.embed_store

# query it
uv run python -m retrieve.hybrid
```

See individual module docstrings under `ingest/` and `retrieve/` for details on
each stage.

---

## Project structure

immunorag/
├── ingest/ # data fetching, parsing, chunking, embedding, graph-building
├── retrieve/ # search, filtering, analytics, live-API, graph-query modules
├── agent/ # agentic routing (LangGraph)
├── app/ # FastAPI web API
├── db/ # PostgreSQL schema
├── scripts/ # verification / smoke-test scripts
└── data/ # raw and processed corpus data (not committed — regenerable)