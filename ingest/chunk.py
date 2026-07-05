# ingest/chunk.py
"""
L1 — Split parsed (section, text) pairs into overlapping word-count chunks.

Reads data/processed/{pmcid}.json (output of parse.py) and produces
data/processed/{pmcid}_chunks.json — a flat list of chunk dicts ready
for embed_store.py to embed and upsert into Qdrant.

Run:
    uv run python -m ingest.chunk
"""

import json
from pathlib import Path

from config import PROCESSED_DATA_DIR, CHUNK_WORDS, CHUNK_OVERLAP


def chunk_text(text: str, chunk_words: int, overlap: int) -> list[str]:
    """
    Split text into overlapping word-count chunks.

    e.g. chunk_words=350, overlap=50 means each chunk after the first
    starts 300 words after the previous chunk started (350-50=300),
    so the last 50 words of chunk N are repeated as the first 50 words
    of chunk N+1.
    """
    words = text.split()
    if len(words) <= chunk_words:
        return [text]  # short section — no need to split

    stride = chunk_words - overlap
    chunks = []
    start = 0
    while start < len(words):
        chunk_words_slice = words[start : start + chunk_words]
        chunks.append(" ".join(chunk_words_slice))
        if start + chunk_words >= len(words):
            break  # reached the end
        start += stride

    return chunks


def chunk_paper(sections: list[dict]) -> list[dict]:
    """
    Chunk every section of a paper, tagging each resulting chunk with
    its section label and a 0-based index within that section.
    """
    chunks = []
    for sec in sections:
        section_label = sec["section"]
        text_chunks = chunk_text(sec["text"], CHUNK_WORDS, CHUNK_OVERLAP)
        for idx, chunk_text_str in enumerate(text_chunks):
            chunks.append({
                "section": section_label,
                "chunk_index": idx,
                "text": chunk_text_str,
            })
    return chunks


def main():
    parsed_files = sorted(PROCESSED_DATA_DIR.glob("PMC*.json"))
    # skip files that are already chunk outputs from a previous run
    parsed_files = [p for p in parsed_files if not p.stem.endswith("_chunks")]

    print(f"Found {len(parsed_files)} parsed papers to chunk.")

    total_chunks = 0
    for p in parsed_files:
        pmcid = p.stem
        out_path = PROCESSED_DATA_DIR / f"{pmcid}_chunks.json"

        if out_path.exists():
            continue  # idempotent

        sections = json.loads(p.read_text())
        chunks = chunk_paper(sections)

        for chunk in chunks:
            chunk["pmcid"] = pmcid  # tag every chunk with its source paper

        out_path.write_text(json.dumps(chunks, indent=2), encoding="utf-8")
        total_chunks += len(chunks)

    print(f"Done. Total chunks created: {total_chunks}")


if __name__ == "__main__":
    main()