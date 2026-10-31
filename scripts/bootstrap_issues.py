#!/usr/bin/env python3
"""Вивести задачі або створити відсутні GitHub Issues через авторизований gh."""
import argparse
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def gh(*args: str) -> str:
    return subprocess.run(["gh", *args], check=True, text=True,
                          capture_output=True).stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default="juv4uk/ukrainian-books")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    issues = json.loads((ROOT / "tasks/ISSUES.json").read_text(encoding="utf-8"))
    if args.dry_run:
        for row in issues:
            print("[план]", row["title"])
        return
    if not shutil.which("gh"):
        raise SystemExit("Потрібен авторизований GitHub CLI (gh)")
    existing = json.loads(gh("issue", "list", "--repo", args.repo,
                             "--state", "all", "--limit", "200",
                             "--json", "title"))
    titles = {row["title"] for row in existing}
    for row in issues:
        if row["title"] in titles:
            print("[вже є]", row["title"])
            continue
        print("[створено]", gh("issue", "create", "--repo", args.repo,
                             "--title", row["title"], "--body", row["body"]))


if __name__ == "__main__":
    main()
