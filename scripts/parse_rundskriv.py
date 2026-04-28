#!/usr/bin/env python3
"""Parse rundskriv HTML for konfigurerte kapitler til strukturert JSON.

Standard kjører for alle kapitler i RUNDSKRIV. Bruk `--kapittel N` for
å begrense, eller send en lokal HTML-fil som siste argument for testing.
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup, NavigableString, Tag

REPO_ROOT = Path(__file__).resolve().parent.parent

# Konfigurasjon: hvilke rundskriv vi parser.
RUNDSKRIV = [
    {
        "kapittel": 20,
        "navn": "Alderspensjon",
        "url": "https://lovdata.no/nav/rundskriv/r20-00",
        "kortnavn": "R20-00",
    },
    {
        "kapittel": 12,
        "navn": "Uføretrygd",
        "url": "https://lovdata.no/nav/rundskriv/r12-00",
        "kortnavn": "R12-00",
    },
]


def output_file_for(kapittel: int) -> Path:
    return REPO_ROOT / f"rundskriv_kap{kapittel}.json"


def clean_section_html(section_div: Tag) -> str:
    """Get inner HTML of a section div, minus the heading and namedAnchors."""
    clone = BeautifulSoup(str(section_div), "html.parser").find("div")

    h3 = clone.find("h3")
    if h3:
        h3.decompose()

    for anchor in clone.find_all("a", class_="namedAnchor"):
        anchor.decompose()

    for a in clone.find_all("a", href=True):
        href = a["href"]
        if href.startswith("https://lovdata.no/"):
            a["href"] = href.replace("https://lovdata.no", "")

    return "".join(str(child) for child in clone.children).strip()


def make_paragraf_nr_extractor(kapittel: int):
    pattern = re.compile(rf"§\s*({kapittel}-\d+)\s*([a-z])?")

    def extract(title: str) -> str:
        m = pattern.match(title)
        if not m:
            raise ValueError(f"Could not extract paragraf number from: {title!r}")
        return m.group(1) + (m.group(2) or "")

    return extract


def download_html(url: str) -> str:
    import urllib.request
    print(f"Laster ned rundskriv fra {url}...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    resp = urllib.request.urlopen(req)
    return resp.read().decode("utf-8")


def parse_one(cfg: dict, html: str) -> dict:
    kapittel = cfg["kapittel"]
    soup = BeautifulSoup(html, "html.parser")
    extract_paragraf_nr = make_paragraf_nr_extractor(kapittel)

    # --- Generell del (KAPITTEL_1) ---
    kap1 = soup.find("div", id="KAPITTEL_1")
    if not kap1:
        raise RuntimeError(f"KAPITTEL_1 ikke funnet i kap. {kapittel}")

    kap1_h2 = kap1.find("h2")
    generell_title = (
        kap1_h2.get_text(strip=True)
        if kap1_h2
        else f"Kapittel {kapittel} – Generell del"
    )

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
        raise RuntimeError(f"KAPITTEL_2 ikke funnet i kap. {kapittel}")

    paragraf_kommentarer = []
    for child_div in kap2.find_all("div", recursive=False):
        div_id = child_div.get("id", "")
        if not re.match(r"KAPITTEL_2-\d+$", div_id):
            continue
        h3 = child_div.find("h3")
        if not h3:
            continue
        title = h3.get_text(strip=True)
        try:
            paragraf_nr = extract_paragraf_nr(title)
        except ValueError as e:
            print(f"  ADVARSEL: {e}", file=sys.stderr)
            continue
        paragraf_kommentarer.append({
            "paragrafNr": paragraf_nr,
            "title": title,
            "html": clean_section_html(child_div),
        })

    return {
        "title": f"Rundskriv til ftrl. kapittel {kapittel}",
        "kapittel": kapittel,
        "navn": cfg.get("navn", ""),
        "kortnavn": cfg.get("kortnavn", ""),
        "source": cfg["url"],
        "lastFetched": str(date.today()),
        "generellDel": {
            "title": generell_title,
            "sections": generell_sections,
        },
        "paragrafKommentarer": paragraf_kommentarer,
    }


def run_for(cfg: dict, local_html: Optional[Path] = None):
    if local_html:
        html = local_html.read_text(encoding="utf-8")
    else:
        html = download_html(cfg["url"])

    output = parse_one(cfg, html)
    out_path = output_file_for(cfg["kapittel"])
    out_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"✓ Skrev {out_path}")
    print(f"  Generell del: {len(output['generellDel']['sections'])} seksjoner")
    print(f"  Paragrafkommentarer: {len(output['paragrafKommentarer'])} oppføringer")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--kapittel",
        type=int,
        choices=[c["kapittel"] for c in RUNDSKRIV],
        help="Begrens til ett kapittel (default: alle)",
    )
    parser.add_argument(
        "html_file",
        nargs="?",
        type=Path,
        help="Lokal HTML-fil (kun gyldig sammen med --kapittel)",
    )
    args = parser.parse_args()

    if args.html_file and not args.kapittel:
        parser.error("--kapittel kreves når en lokal HTML-fil er gitt")

    targets = [c for c in RUNDSKRIV if not args.kapittel or c["kapittel"] == args.kapittel]
    for cfg in targets:
        print(f"\n=== Kapittel {cfg['kapittel']} – {cfg.get('navn','')} ===")
        run_for(cfg, args.html_file if cfg["kapittel"] == args.kapittel else None)


if __name__ == "__main__":
    main()
