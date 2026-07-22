import os
from dotenv import load_dotenv
from pathlib import Path
load_dotenv()

QDRANT_URL   = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION   = os.getenv("COLLECTION", "immuno_chunks")
DENSE_MODEL  = "BAAI/bge-small-en-v1.5"
SPARSE_MODEL = "Qdrant/bm25"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL   = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
CHUNK_WORDS  = 350
CHUNK_OVERLAP = 50
TOP_K = 8

# --- paths (new) ---
BASE_DIR       = Path(__file__).resolve().parent
RAW_DATA_DIR   = BASE_DIR / "data" / "raw"
PROCESSED_DATA_DIR = BASE_DIR / "data" / "processed"


POSTGRES_USER = os.getenv("POSTGRES_USER", "immunorag")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "immunorag_dev_pw")
POSTGRES_DB = os.getenv("POSTGRES_DB", "immunorag")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")

POSTGRES_DSN = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"


POSTGRES_READONLY_USER = os.getenv("POSTGRES_READONLY_USER", "immunorag_readonly")
POSTGRES_READONLY_PASSWORD = os.getenv("POSTGRES_READONLY_PASSWORD", "readonly_dev_pw")

POSTGRES_READONLY_DSN = (
    f"postgresql://{POSTGRES_READONLY_USER}:{POSTGRES_READONLY_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)


REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

OPENFDA_BASE_URL = "https://api.fda.gov"
CACHE_TTL_SECONDS = 3600  # 1 hour — openFDA data doesn't change minute-to-minute


NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "immunorag_neo4j_pw")