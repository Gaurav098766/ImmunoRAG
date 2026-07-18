# ingest/parse.py
"""
L1/L3 — Parse raw JATS full-text XML into flat (section, text) pairs.

Reads data/raw/{pmcid}.xml, extracts all <sec> blocks (flat, no hierarchy)
plus the abstract, and writes clean structured text to
data/processed/{pmcid}.json for chunk.py to consume next.

Also detects and drops reference-list/bibliography sections that some
publishers embed as regular <sec> blocks inside <body> instead of the
proper <back><ref-list> location.

Run:
    uv run python -m ingest.parse
"""

import json
import re
from pathlib import Path

from lxml import etree

from config import RAW_DATA_DIR, PROCESSED_DATA_DIR

DROP_TAGS = {"table-wrap", "fig", "disp-formula", "graphic", "media"}

# Matches DOI-style identifiers, e.g. "10.1016/BS.IRCMB.2019.06.001"
DOI_PATTERN = re.compile(r'\b10\.\d{4,9}/\S+')

# Matches the start of a numbered citation entry, e.g. "23. Smith J," or "1. Lin X,"
NUMBERED_CITATION_PATTERN = re.compile(r'\b\d{1,3}\.\s+[A-Z][a-z]+\s+[A-Z]')

# sec-type values publishers use to explicitly mark reference lists
REF_SEC_TYPES = {"ref-list", "references", "bibliography"}


def is_reference_list(sec_elem, text: str) -> bool:
    """
    Heuristic check: is this <sec> actually a reference/bibliography list
    that slipped into <body> instead of living in <back><ref-list>?

    Two signals, either one is enough to flag it:
      1. Explicit sec-type attribute (some publishers do mark it).
      2. Content shape — reference lists are dense with DOIs and repeated
         numbered-citation patterns ("23. Smith J, Doe A. Title...").
         Normal prose essentially never has this density.
    """
    sec_type = sec_elem.get("sec-type", "").lower()
    if sec_type in REF_SEC_TYPES:
        return True

    word_count = len(text.split())
    if word_count == 0:
        return False

    doi_matches = len(DOI_PATTERN.findall(text))
    citation_matches = len(NUMBERED_CITATION_PATTERN.findall(text))

    density = (doi_matches + citation_matches) / word_count * 100
    return density > 1.5  # tuned conservatively — prose won't hit this


def extract_section_text(sec_elem) -> str:
    """
    Get the direct text of a <sec>, excluding nested <sec> children,
    the section's own <title> and <label> (numbering), and DROP_TAGS.
    """
    clone = etree.fromstring(etree.tostring(sec_elem))

    for nested_sec in clone.findall(".//sec"):
        nested_sec.getparent().remove(nested_sec)

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


def parse_paper(xml_path: Path) -> list[dict]:
    """
    Parse one paper's XML into a flat list of {section, text} dicts.
    Reference-list sections (detected via is_reference_list) are dropped.
    Falls back to treating the whole <body> as one section if the paper
    has no <sec> elements at all (some publishers use bare <p> tags
    directly under <body> for short communications/letters).
    """
    tree = etree.parse(str(xml_path))
    root = tree.getroot()

    sections = []

    abstract_elem = root.find(".//abstract")
    if abstract_elem is not None:
        abstract_text = " ".join(abstract_elem.itertext())
        abstract_text = " ".join(abstract_text.split())
        if abstract_text:
            sections.append({"section": "Abstract", "text": abstract_text})

    body_elem = root.find(".//body")
    if body_elem is None:
        return sections

    all_secs = list(body_elem.iter("sec"))

    if not all_secs:
        # NEW: no <sec> structure at all — fall back to whole-body text
        body_text = " ".join(body_elem.itertext())
        body_text = " ".join(body_text.split())
        if body_text and not is_reference_list(body_elem, body_text):
            sections.append({"section": "Body", "text": body_text})
        return sections

    skipped_ref_lists = 0
    for sec_elem in all_secs:
        title = get_section_title(sec_elem)
        text = extract_section_text(sec_elem)
        if not text:
            continue

        if is_reference_list(sec_elem, text):
            skipped_ref_lists += 1
            continue

        sections.append({"section": title, "text": text})

    if skipped_ref_lists:
        print(f"    (skipped {skipped_ref_lists} reference-list section(s) in {xml_path.stem})")

    return sections


def main():
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

    xml_files = sorted(RAW_DATA_DIR.glob("PMC*.xml"))
    print(f"Found {len(xml_files)} raw XML files to parse.")

    parsed_count, failed = 0, 0

    for xml_path in xml_files:
        pmcid = xml_path.stem
        out_path = PROCESSED_DATA_DIR / f"{pmcid}.json"

        sections = None
        try:
            sections = parse_paper(xml_path)
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