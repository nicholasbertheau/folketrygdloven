"""
Laster ned gjeldende lover og forskrifter fra Lovdata,
parser folketrygdloven og tilhørende forskrifter til JSON,
og genererer endringslogg.
Kjøres av GitHub Actions (update.yml) eller manuelt.
"""

import json
import os
import re
import hashlib
import sys
import tarfile
import tempfile
import urllib.request
from datetime import date

LOVDATA_LOVER_URL = "https://api.lovdata.no/v1/publicData/get/gjeldende-lover.tar.bz2"
LOVDATA_FORSKRIFTER_URL = "https://api.lovdata.no/v1/publicData/get/gjeldende-sentrale-forskrifter.tar.bz2"
FTRL_FILENAME = "nl-19970228-019.xml"
OUTPUT_FILE = "folketrygdloven.json"
FORSKRIFTER_FILE = "forskrifter.json"
CHANGELOG_FILE = "changelog.json"


def get_root_dir():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(script_dir)
    if not os.path.isdir(root):
        root = "."
    return root


def download_and_extract_ftrl(tmpdir):
    """Last ned og pakk ut folketrygdloven fra Lovdata."""
    archive_path = os.path.join(tmpdir, "lover.tar.bz2")
    print(f"Laster ned lover fra {LOVDATA_LOVER_URL}...")
    urllib.request.urlretrieve(LOVDATA_LOVER_URL, archive_path)

    print("Pakker ut folketrygdloven...")
    with tarfile.open(archive_path, "r:bz2") as tar:
        member = None
        for m in tar.getmembers():
            if FTRL_FILENAME in m.name:
                member = m
                break
        if not member:
            print(f"FEIL: Fant ikke {FTRL_FILENAME} i arkivet")
            sys.exit(1)

        tar.extract(member, tmpdir)
        filepath = os.path.join(tmpdir, member.name)
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()


def download_and_extract_forskrifter(tmpdir):
    """Last ned og pakk ut forskrifter fra Lovdata."""
    archive_path = os.path.join(tmpdir, "forskrifter.tar.bz2")
    print(f"Laster ned forskrifter fra {LOVDATA_FORSKRIFTER_URL}...")
    urllib.request.urlretrieve(LOVDATA_FORSKRIFTER_URL, archive_path)

    print("Pakker ut forskrifter...")
    with tarfile.open(archive_path, "r:bz2") as tar:
        tar.extractall(tmpdir)

    sf_dir = os.path.join(tmpdir, "sf")
    if not os.path.isdir(sf_dir):
        for d in os.listdir(tmpdir):
            candidate = os.path.join(tmpdir, d)
            if os.path.isdir(candidate) and d != "__MACOSX":
                sf_dir = candidate
                break

    return sf_dir


def parse_law(html_content):
    """Parser HTML til strukturert JSON."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html_content, "html.parser")
    main = soup.find("main", class_="documentBody")

    law_data = {
        "title": "Lov om folketrygd (folketrygdloven)",
        "shortTitle": "Folketrygdloven - ftrl",
        "dokID": "NL/lov/1997-02-28-19",
        "parts": [],
    }

    for del_section in main.find_all("section", class_="section", recursive=False):
        del_h2 = del_section.find("h2")
        part = {
            "title": del_h2.get_text().strip() if del_h2 else "",
            "id": del_section.get("id", ""),
            "chapters": [],
        }

        for kap_section in del_section.find_all(
            "section", class_="section", recursive=False
        ):
            kap_h3 = kap_section.find("h3")
            chapter = {
                "title": kap_h3.get_text().strip() if kap_h3 else "",
                "id": kap_section.get("id", ""),
                "paragraphs": [],
            }

            for article in kap_section.find_all(
                "article", class_="legalArticle", recursive=False
            ):
                header = article.find(
                    ["h4", "h5", "h6", "div"], class_="legalArticleHeader"
                )
                if not header:
                    header = article.find("h4")

                title_el = article.find(
                    ["h4", "h5", "h6", "div"], class_="legalArticleTitle"
                )

                header_text = header.get_text().strip() if header else ""
                title_text = title_el.get_text().strip() if title_el else ""

                full_title = header_text
                if title_text and title_text not in header_text:
                    full_title = f"{header_text} {title_text}"

                article_copy = BeautifulSoup(str(article), "html.parser")
                for h in article_copy.find_all(
                    ["h4", "h5", "h6", "div"],
                    class_=["legalArticleHeader", "legalArticleTitle"],
                ):
                    h.decompose()

                body_text = article_copy.get_text().strip()

                para = {
                    "id": article.get("id", ""),
                    "title": full_title,
                    "text": body_text,
                    "html": str(article),
                }
                chapter["paragraphs"].append(para)

            if chapter["paragraphs"]:
                part["chapters"].append(chapter)

        if part["chapters"]:
            law_data["parts"].append(part)

    return law_data


def parse_forskrifter(sf_dir):
    """Parser forskrifter som har hjemmel i folketrygdloven."""
    from bs4 import BeautifulSoup

    forskrifter = []
    for fname in sorted(os.listdir(sf_dir)):
        if not fname.endswith(".xml"):
            continue
        fpath = os.path.join(sf_dir, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()

        if "1997-02-28-19" not in content:
            continue

        soup = BeautifulSoup(content, "html.parser")

        # Only include if ftrl is in the header (hjemmel)
        header = soup.find("header")
        if not header or "lov/1997-02-28-19" not in str(header):
            continue

        title_el = soup.find("dd", class_="title")
        title = title_el.get_text().strip() if title_el else fname

        short_el = soup.find("dd", class_="titleShort")
        short = short_el.get_text().strip() if short_el else ""

        dok_el = soup.find("dd", class_="dokid")
        dokid = dok_el.get_text().strip() if dok_el else ""

        legacy_el = soup.find("dd", class_="legacyID")
        legacy = legacy_el.get_text().strip() if legacy_el else ""

        # Find which ftrl paragraphs are referenced
        body = soup.find("main") or soup.find("body")
        body_str = str(body) if body else content
        refs = sorted(set(re.findall(
            r"lov/1997-02-28-19/(§[\d]+-[\d]+[a-z]?)", body_str
        )))

        forskrifter.append({
            "title": title,
            "shortTitle": short,
            "dokid": dokid,
            "legacy": legacy,
            "ftrlRefs": refs,
        })

    forskrifter.sort(key=lambda x: x["title"])
    return forskrifter


def compute_hash(data):
    """Beregn hash av data for endringsdeteksjon."""
    text = json.dumps(data, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def build_paragraph_titles(law_data):
    """Bygg mapping fra paragraf-id til tittel."""
    titles = {}
    for part in law_data["parts"]:
        for ch in part["chapters"]:
            for p in ch["paragraphs"]:
                titles[p["id"]] = p["title"]
    return titles


def update_changelog(root_dir, old_law, new_law, old_forskrifter, new_forskrifter):
    """Generer endringslogg basert på diff mellom gammel og ny data."""
    changelog_path = os.path.join(root_dir, CHANGELOG_FILE)

    try:
        with open(changelog_path, "r", encoding="utf-8") as f:
            changelog = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        changelog = {"lastChecked": "", "lastChanged": "", "entries": []}

    today = date.today().isoformat()
    changelog["lastChecked"] = today
    changes = []

    if old_law and new_law:
        old_titles = build_paragraph_titles(old_law)
        new_titles = build_paragraph_titles(new_law)
        old_ids = set(old_titles.keys())
        new_ids = set(new_titles.keys())

        added = new_ids - old_ids
        removed = old_ids - new_ids

        for pid in sorted(added):
            changes.append(f"Ny paragraf: {new_titles[pid]}")
        for pid in sorted(removed):
            changes.append(f"Fjernet paragraf: {old_titles[pid]}")

        # Check for text changes in existing paragraphs
        old_texts = {}
        for part in old_law.get("parts", []):
            for ch in part["chapters"]:
                for p in ch["paragraphs"]:
                    old_texts[p["id"]] = p["text"]

        new_texts = {}
        for part in new_law.get("parts", []):
            for ch in part["chapters"]:
                for p in ch["paragraphs"]:
                    new_texts[p["id"]] = p["text"]

        for pid in sorted(old_ids & new_ids):
            if old_texts.get(pid) != new_texts.get(pid):
                changes.append(f"Endret: {new_titles[pid]}")

    if old_forskrifter is not None and new_forskrifter is not None:
        old_f_ids = {f["dokid"] for f in old_forskrifter}
        new_f_ids = {f["dokid"] for f in new_forskrifter}
        added_f = new_f_ids - old_f_ids
        removed_f = old_f_ids - new_f_ids

        new_f_map = {f["dokid"]: f for f in new_forskrifter}
        old_f_map = {f["dokid"]: f for f in old_forskrifter}

        for fid in sorted(added_f):
            f = new_f_map[fid]
            changes.append(f"Ny forskrift: {f['shortTitle'] or f['title']}")
        for fid in sorted(removed_f):
            f = old_f_map[fid]
            changes.append(f"Fjernet forskrift: {f['shortTitle'] or f['title']}")

    if changes:
        changelog["lastChanged"] = today
        changelog["entries"].insert(0, {
            "date": today,
            "type": "update",
            "changes": changes,
        })
        # Keep max 50 entries
        changelog["entries"] = changelog["entries"][:50]

    with open(changelog_path, "w", encoding="utf-8") as f:
        json.dump(changelog, f, ensure_ascii=False, indent=2)

    return changes


def main():
    root_dir = get_root_dir()

    # Load existing data for changelog comparison
    old_law = None
    old_forskrifter = None
    law_path = os.path.join(root_dir, OUTPUT_FILE)
    forskrifter_path = os.path.join(root_dir, FORSKRIFTER_FILE)

    try:
        with open(law_path, "r", encoding="utf-8") as f:
            old_law = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    try:
        with open(forskrifter_path, "r", encoding="utf-8") as f:
            old_forskrifter = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    with tempfile.TemporaryDirectory() as tmpdir:
        # Download and parse law
        html_content = download_and_extract_ftrl(tmpdir)
        law_data = parse_law(html_content)

        total_paras = sum(
            len(ch["paragraphs"])
            for p in law_data["parts"]
            for ch in p["chapters"]
        )
        total_chapters = sum(len(p["chapters"]) for p in law_data["parts"])
        print(f"Lov: {len(law_data['parts'])} deler, {total_chapters} kapitler, {total_paras} paragrafer")

        # Download and parse forskrifter
        sf_dir = download_and_extract_forskrifter(tmpdir)
        forskrifter = parse_forskrifter(sf_dir)
        print(f"Forskrifter med hjemmel i ftrl: {len(forskrifter)}")

    # Update changelog
    changes = update_changelog(root_dir, old_law, law_data, old_forskrifter, forskrifter)
    if changes:
        print(f"Endringslogg: {len(changes)} endringer")
        for c in changes[:5]:
            print(f"  - {c}")
    else:
        print("Ingen endringer siden sist.")

    # Save law data
    with open(law_path, "w", encoding="utf-8") as f:
        json.dump(law_data, f, ensure_ascii=False, indent=2)
    print(f"Lagret {law_path}")

    # Save forskrifter
    with open(forskrifter_path, "w", encoding="utf-8") as f:
        json.dump(forskrifter, f, ensure_ascii=False, indent=2)
    print(f"Lagret {forskrifter_path}")


if __name__ == "__main__":
    main()
