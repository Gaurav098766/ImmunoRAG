import os
from dotenv import load_dotenv
load_dotenv()

QDRANT_URL   = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION   = os.getenv("COLLECTION", "immuno_chunks")
DENSE_MODEL  = "BAAI/bge-small-en-v1.5"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL   = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
CHUNK_WORDS  = 350
CHUNK_OVERLAP = 50
TOP_K = 8