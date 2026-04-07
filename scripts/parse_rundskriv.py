#!/usr/bin/env python3
"""Parse rundskriv HTML for kapittel 20 into structured JSON."""

import json
import re
import sys
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_FILE = REPO_ROOT / "rundskriv_kap20.json"

SOURCE_URL = "https://lovdata.no/nav/rundskriv/r20-00"


def clean_section_html(section_div: Tag) -> str:
    """Get inner HTML of a section div, minus the heading and namedAnchors."""
    # Work on a copy so we don't mutate the tree
    clone = section_div.__copy__()
    # BeautifulSoup __copy__ is shallow; we need a deep copy
    clone = BeautifulSoup(str(section_div), "html.parser").find("div")

    # Remove the first h3 (the section title)
    h3 = clone.find("h3")
    if h3:
        h3.decompose()

    # Remove all <a class="namedAnchor"> tags
    for anchor in clone.find_all("a", class_="namedAnchor"):
        anchor.decompose()

    # Convert absolute lovdata links to relative
    for a in clone.find_all("a", href=True):
        href = a["href"]
        if href.startswith("https://lovdata.no/"):
            a["href"] = href.replace("https://lovdata.no", "")
        # hrefs like /nav/lov/... are already relative — keep them

    # Return inner HTML (children of the div, not the div itself)
    return "".join(str(child) for child in clone.children).strip()


def extract_paragraf_nr(title: str) -> str:
    """Extract paragraph number from a title like '§ 20-1 a. Forholdet...'

    Rules:
      '§ 20-1 Formål...'       -> '20-1'
      '§ 20-1 a. Forholdet...' -> '20-1a'
      '§ 20-7a Pensjons...'    -> '20-7a'
      '§ 20-19a Gjenlevende..' -> '20-19a'
    """
    # Match § followed by the number, optional letter suffix (with or without space)
    m = re.match(r"§\s*(20-\d+)\s*([a-z])?", title)
    if not m:
        raise ValueError(f"Could not extract paragraf number from: {title!r}")
    nr = m.group(1)
    letter = m.group(2) or ""
    return nr + letter


def download_rundskriv():
    """Download rundskriv HTML from Lovdata."""
    import urllib.request
    print(f"Laster ned rundskriv fra {SOURCE_URL}...")
    req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "Mozilla/5.0"})
    resp = urllib.request.urlopen(req)
    return resp.read().decode("utf-8")


def main():
    # Accept optional file argument for local testing
    if len(sys.argv) > 1:
        input_path = Path(sys.argv[1])
        if not input_path.exists():
            print(f"ERROR: Input file not found: {input_path}", file=sys.stderr)
            sys.exit(1)
        html = input_path.read_text(encoding="utf-8")
    else:
        html = download_rundskriv()

    soup = BeautifulSoup(html, "html.parser")

    # --- Generell del (KAPITTEL_1) ---
    kap1 = soup.find("div", id="KAPITTEL_1")
    if not kap1:
        print("ERROR: KAPITTEL_1 not found", file=sys.stderr)
        sys.exit(1)

    kap1_h2 = kap1.find("h2")
    generell_title = kap1_h2.get_text(strip=True) if kap1_h2 else "Kapittel 20 – Generell del"

    generell_sections = []
    for child_div in kap1.find_all("div", recursive=False):
        div_id = child_div.get("id", "")
        if not re.match(r"KAPITTEL_1-\d+$", div_id):
            continue
        h3 = child_div.find("h3")
        if not h3:
            continue
        generell_sections.append({
            "title": h3.get_text(strip=True),
            "html": clean_section_html(child_div),
        })

    # --- Paragrafkommentarer (KAPITTEL_2) ---
    kap2 = soup.find("div", id="KAPITTEL_2")
    if not kap2:
        print("ERROR: KAPITTEL_2 not found", file=sys.stderr)
        sys.exit(1)

    paragraf_kommentarer = []
    for child_div in kap2.find_all("div", recursive=False):
        div_id = child_div.get("id", "")
        if not re.match(r"KAPITTEL_2-\d+$", div_id):
            continue
        h3 = child_div.find("h3")
        if not h3:
            continue
        title = h3.get_text(strip=True)
        paragraf_kommentarer.append({
            "paragrafNr": extract_paragraf_nr(title),
            "title": title,
            "html": clean_section_html(child_div),
        })

    # --- Build output ---
    output = {
        "title": "Rundskriv til ftrl. kapittel 20",
        "source": SOURCE_URL,
        "lastFetched": str(date.today()),
        "generellDel": {
            "title": generell_title,
            "sections": generell_sections,
        },
        "paragrafKommentarer": paragraf_kommentarer,
    }

    OUTPUT_FILE.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    # --- Summary ---
    print(f"✓ Wrote {OUTPUT_FILE}")
    print(f"  Generell del: {len(generell_sections)} sections")
    print(f"  Paragrafkommentarer: {len(paragraf_kommentarer)} entries")
    print()
    for entry in paragraf_kommentarer:
        print(f"  § {entry['paragrafNr']:8s}  {len(entry['html']):>7,} chars  {entry['title']}")


if __name__ == "__main__":
    main()
