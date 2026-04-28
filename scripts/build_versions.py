"""
Bygger versions.json med liste over historiske snapshots av
folketrygdloven.json og rundskriv_kap20.json basert på git-historikken.

Brukes av frontend som primær kilde for versjonsvelgeren, slik at vi
slipper å treffe GitHubs API (som har streng rate-limit for uautentiserte
forespørsler).
"""

import json
import os
import subprocess
import sys


VERSIONED_FILES = ["folketrygdloven.json", "rundskriv_kap20.json", "rundskriv_kap12.json"]
OUTPUT_FILE = "versions.json"
MAX_ENTRIES = 500


def get_root_dir():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(script_dir) or "."


def git(*args, cwd):
    return subprocess.check_output(
        ["git", *args], cwd=cwd, text=True, stderr=subprocess.STDOUT
    )


def collect_commits(root_dir):
    """Henter alle commits som har endret én av de versjonerte filene."""
    seen = {}
    for fname in VERSIONED_FILES:
        try:
            out = git(
                "log",
                f"--max-count={MAX_ENTRIES}",
                "--pretty=format:%H%x09%aI%x09%s",
                "--",
                fname,
                cwd=root_dir,
            )
        except subprocess.CalledProcessError as e:
            print(f"git log feilet for {fname}: {e.output}", file=sys.stderr)
            continue

        for line in out.splitlines():
            parts = line.split("\t", 2)
            if len(parts) < 3:
                continue
            sha, date, message = parts
            entry = seen.setdefault(
                sha,
                {"sha": sha, "date": date, "message": message, "files": []},
            )
            entry["files"].append(fname)

    versions = sorted(seen.values(), key=lambda v: v["date"], reverse=True)
    return versions[:MAX_ENTRIES]


def main():
    root = get_root_dir()
    versions = collect_commits(root)

    payload = {
        "repo": "nicholasbertheau/folketrygdloven",
        "files": VERSIONED_FILES,
        "count": len(versions),
        "versions": versions,
    }

    out_path = os.path.join(root, OUTPUT_FILE)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"Skrev {out_path} med {len(versions)} versjoner")


if __name__ == "__main__":
    main()
