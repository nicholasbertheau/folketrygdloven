"""
Laster ned gjeldende lover fra Lovdata og parser folketrygdloven til JSON.
Kjøres av GitHub Actions (update.yml) eller manuelt.
"""

import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import urllib.request

LOVDATA_URL = "https://api.lovdata.no/v1/publicData/get/gjeldende-lover.tar.bz2"
FTRL_FILENAME = "nl-19970228-019.xml"
OUTPUT_FILE = "folketrygdloven.json"


def download_and_extract():
    """Last ned og pakk ut folketrygdloven fra Lovdata."""
    with tempfile.TemporaryDirectory() as tmpdir:
        archive_path = os.path.join(tmpdir, "lover.tar.bz2")
        print(f"Laster ned fra {LOVDATA_URL}...")
        urllib.request.urlretrieve(LOVDATA_URL, archive_path)

        print("Pakker ut...")
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


def main():
    html_content = download_and_extract()
    law_data = parse_law(html_content)

    total_paras = sum(
        len(ch["paragraphs"]) for p in law_data["parts"] for ch in p["chapters"]
    )
    total_chapters = sum(len(p["chapters"]) for p in law_data["parts"])

    print(f"Parsed: {len(law_data['parts'])} deler, {total_chapters} kapitler, {total_paras} paragrafer")

    output_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), OUTPUT_FILE)
    if not os.path.isabs(output_path):
        output_path = OUTPUT_FILE

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(law_data, f, ensure_ascii=False, indent=2)

    print(f"Lagret til {output_path}")


if __name__ == "__main__":
    main()
