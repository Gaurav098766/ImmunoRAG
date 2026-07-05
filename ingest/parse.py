# ingest/parse.py
"""
L1 — Parse raw JATS full-text XML into flat (section, text) pairs.

Reads data/raw/{pmcid}.xml, extracts all <sec> blocks (flat, no hierarchy)
plus the abstract, and writes clean structured text to
data/processed/{pmcid}.json for chunk.py to consume next.

Run:
    uv run python -m ingest.parse
"""

import json
from pathlib import Path

from lxml import etree

from config import RAW_DATA_DIR, PROCESSED_DATA_DIR

# Tags whose text we want to drop entirely (not just unwrap) —
# these are typically captions/labels that create noisy, out-of-context text
DROP_TAGS = {"table-wrap", "fig", "disp-formula", "graphic", "media"}

def extract_section_text(sec_elem) -> str:
    """
    Get the direct text of a <sec>, excluding nested <sec> children,
    the section's own <title> and <label> (numbering), and DROP_TAGS.
    """
    clone = etree.fromstring(etree.tostring(sec_elem))

    for nested_sec in clone.findall(".//sec"):
        nested_sec.getparent().remove(nested_sec)

    # Remove title and label so they don't duplicate/leak into text
    for tag in ("title", "label"):
        elem = clone.find(tag)
        if elem is not None:
            clone.remove(elem)

    for tag in DROP_TAGS:
        for elem in clone.findall(f".//{tag}"):
            elem.getparent().remove(elem)

    text = " ".join(clone.itertext())
    return " ".join(text.split())


def get_section_title(sec_elem) -> str:
    """First direct <title> child's text, or 'untitled' if absent."""
    title_elem = sec_elem.find("title")
    if title_elem is not None:
        title_text = " ".join(title_elem.itertext()).strip()
        if title_text:
            return title_text
    return "untitled"


def parse_paper(xml_path: Path, i: int) -> list[dict]:
    """
    Parse one paper's XML into a flat list of {section, text} dicts.
    Returns [] if the XML has no <body> (shouldn't happen given our
    open-access filter, but defensive anyway).
    """
    tree = etree.parse(str(xml_path))
    root = tree.getroot()

    sections = []

    # Abstract lives outside <body>, handle separately
    abstract_elem = root.find(".//abstract")
    if i==0:
        print(abstract_elem)
    if abstract_elem is not None:
        abstract_text = " ".join(abstract_elem.itertext())
        abstract_text = " ".join(abstract_text.split())
        if abstract_text:
            sections.append({"section": "Abstract", "text": abstract_text})

    body_elem = root.find(".//body")
    if i==0:
        print(body_elem)
    if body_elem is None:
        return sections  # abstract-only paper, or malformed — still return what we have

    for sec_elem in body_elem.iter("sec"):
        title = get_section_title(sec_elem)
        if i==0:
            print(title)
        text = extract_section_text(sec_elem)
        if i==0:
            print(text)
        if text:  # skip empty sections (e.g. a <sec> that's just a nested container)
            sections.append({"section": title, "text": text})

    return sections


def main():
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

    xml_files = sorted(RAW_DATA_DIR.glob("PMC*.xml"))
    print(f"Found {len(xml_files)} raw XML files to parse.")

    parsed_count, failed = 0, 0

    for i, xml_path in enumerate(xml_files):
        pmcid = xml_path.stem
        out_path = PROCESSED_DATA_DIR / f"{pmcid}.json"

        if out_path.exists():
            parsed_count += 1
            continue  # idempotent — skip already-parsed papers

        try:
            sections = parse_paper(xml_path,i)
        except etree.XMLSyntaxError as e:
            print(f"  FAILED to parse {pmcid}: {e}")
            failed += 1
            continue

        if not sections:
            print(f"  WARNING: no sections extracted for {pmcid}")

        out_path.write_text(json.dumps(sections, indent=2), encoding="utf-8")
        parsed_count += 1

    print(f"\nDone. Parsed: {parsed_count}, Failed: {failed}")


if __name__ == "__main__":
    main()