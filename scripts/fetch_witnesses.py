#!/usr/bin/env python3
"""Звірити читання вірша «Аштавакра-ґіти» за двома свідками.

Навіщо: донедавна GRETIL був недосяжний із середовища збірки, тому картки
виходили одноголосними (`variants_checked = false`). Дзеркало GRETIL в
архіві INDOLOGY/GRETIL-mirror робить звірку відтворюваною.

Мережа потрібна; обидва джерела беруться з raw.githubusercontent.com.

Використання:
    python3 scripts/fetch_witnesses.py 1.3 1.4
    python3 scripts/fetch_witnesses.py --json 1.4
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
import urllib.request

SARIT_URL = ("https://raw.githubusercontent.com/sarit/SARIT-corpus/"
             "master/astavakragita.xml")
GRETIL_URL = ("https://raw.githubusercontent.com/INDOLOGY/GRETIL-mirror/main/"
              "gretil.sub.uni-goettingen.de/gretil/corpustei/sa_aSTAvakragItA.xml")

PADA_MARKERS = re.compile(r"[|/।]+")


def fetch(url: str) -> str:
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read().decode("utf-8", errors="replace")


def strip_tags(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = unicodedata.normalize("NFC", text)
    text = PADA_MARKERS.sub(" ", text)
    # SARIT додає номер вірша в кінці рядка («… muktaye 1 3»)
    text = re.sub(r"\s+\d+(?:\s+\d+)*\s*$", "", text)
    return re.sub(r"\s+", " ", text).strip()


def sarit_verse(xml: str, verse: str) -> str | None:
    pattern = rf'<lg[^>]*xml:id="verse_{re.escape(verse)}"[^>]*>(.*?)</lg>'
    match = re.search(pattern, xml, re.S)
    return strip_tags(match.group(1)) if match else None


def gretil_verse(xml: str, verse: str) -> str | None:
    pattern = rf'<lg[^>]*xml:id="Avg_{re.escape(verse)}"[^>]*>(.*?)</lg>'
    match = re.search(pattern, xml, re.S)
    return strip_tags(match.group(1)) if match else None


def compare(a: str, b: str) -> dict:
    """Порівняти два читання: спершу як є, потім без пробілів."""
    exact = a == b
    squeezed = re.sub(r"\s+", "", a) == re.sub(r"\s+", "", b)
    return {
        "identical": exact,
        "identical_ignoring_spaces": squeezed,
        "difference": None if exact else _first_difference(a, b),
    }


def _first_difference(a: str, b: str) -> str:
    limit = min(len(a), len(b))
    for i in range(limit):
        if a[i] != b[i]:
            return f"позиція {i}: SARIT «…{a[max(0,i-20):i+20]}» / GRETIL «…{b[max(0,i-20):i+20]}»"
    if len(a) != len(b):
        longer, name = (a, "SARIT") if len(a) > len(b) else (b, "GRETIL")
        return f"довжина: {name} довший на {abs(len(a)-len(b))} симв.: «{longer[limit:limit+40]}»"
    return "різниця поза межами порівняння"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("verses", nargs="+", help="номери віршів, напр. 1.3 1.4")
    parser.add_argument("--json", action="store_true", help="вивід у JSON")
    args = parser.parse_args()

    try:
        sarit_xml = fetch(SARIT_URL)
        gretil_xml = fetch(GRETIL_URL)
    except Exception as error:  # мережа
        print(f"МЕРЕЖА-ПРОВАЛ: {type(error).__name__}: {error}", file=sys.stderr)
        return 2

    report = []
    failed = 0
    for verse in args.verses:
        a = sarit_verse(sarit_xml, verse)
        b = gretil_verse(gretil_xml, verse)
        entry = {"verse": verse, "sarit": a, "gretil": b}
        if a is None or b is None:
            entry["status"] = "НЕ ЗНАЙДЕНО"
            failed += 1
        else:
            entry.update(compare(a, b))
            entry["status"] = ("ЗБІГ" if entry["identical"]
                               else "ЗБІГ-БЕЗ-ПРОБІЛІВ" if entry["identical_ignoring_spaces"]
                               else "РОЗБІЖНІСТЬ")
        report.append(entry)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for e in report:
            print(f"[{e['status']}] {e['verse']}")
            if e["sarit"]:
                print(f"  SARIT : {e['sarit']}")
            if e["gretil"]:
                print(f"  GRETIL: {e['gretil']}")
            if e.get("difference"):
                print(f"  РІЗНИЦЯ: {e['difference']}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
