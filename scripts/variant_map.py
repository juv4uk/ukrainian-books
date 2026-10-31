#!/usr/bin/env python3
"""Карта різночитань «Аштавакра-ґіти»: SARIT проти GRETIL.

Відтворює числа, опубліковані в research/ashtavakra/variant-map.md.

Три категорії, і третя — ФІЛЬТР, а не вирок:
  точний   — рядки збігаються побайтово;
  орфографія — різниця лише в поділі слів, аваґрасі, анусварі, сибілянтах,
               довготі голосних або подвоєнні приголосних;
  кандидат — після згортання всього переліченого рядки ЩЕ різняться.
               Це запрошення до філологічної перевірки, не список варіантів.

Згортання навмисно грубе й симетричне: воно може ПРИХОВАТИ різницю
(напр. aham/ahan після ṃ→n), тому кожен кандидат треба читати очима.
"""

from __future__ import annotations

import argparse
import json
import re
import sys

from fetch_witnesses import GRETIL_URL, SARIT_URL, fetch, strip_tags

FOLD = str.maketrans({
    "ā": "a", "ī": "i", "ū": "u", "ṛ": "r", "ṝ": "r", "ḷ": "l",
    "ṃ": "n", "ṁ": "n", "ñ": "n", "ṅ": "n", "ṇ": "n",
    "ś": "s", "ṣ": "s", "ṭ": "t", "ḍ": "d", "ḥ": "",
    "’": "", "'": "", "+": "", " ": "", "\n": "", "\t": "",
})


def verses(xml: str, prefix: str) -> dict[str, str]:
    pattern = rf'<lg[^>]*xml:id="{prefix}([\d]+\.[\d]+)"[^>]*>(.*?)</lg>'
    return {m.group(1): strip_tags(m.group(2))
            for m in re.finditer(pattern, xml, re.S)}


def folded(text: str) -> str:
    return re.sub(r"(.)\1+", r"\1", text.translate(FOLD))


def key(verse: str) -> tuple[int, int]:
    major, minor = verse.split(".")
    return int(major), int(minor)


VOWELS = set("aiueo")


def consonants(text: str) -> str:
    return "".join(ch for ch in folded(text) if ch not in VOWELS)


def classify(sarit_xml: str, gretil_xml: str) -> dict:
    sarit = verses(sarit_xml, "verse_")
    gretil = verses(gretil_xml, "Avg_")
    common = sorted(set(sarit) & set(gretil), key=key)
    exact, orthographic, candidates = [], [], []
    vowel_only, consonant_diff = [], []
    for verse in common:
        a, b = sarit[verse], gretil[verse]
        if a == b:
            exact.append(verse)
        elif re.sub(r"\s+", "", a) == re.sub(r"\s+", "", b) or folded(a) == folded(b):
            orthographic.append(verse)
        else:
            candidates.append(verse)
            if consonants(a) == consonants(b):
                vowel_only.append(verse)
            else:
                consonant_diff.append(verse)
    return {
        "sarit_verses": len(sarit),
        "gretil_verses": len(gretil),
        "common": len(common),
        "only_gretil": sorted(set(gretil) - set(sarit), key=key),
        "only_sarit": sorted(set(sarit) - set(gretil), key=key),
        "exact": len(exact),
        "orthographic": len(orthographic),
        "candidates": candidates,
        "vowel_only": vowel_only,
        "consonant_diff": consonant_diff,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = classify(fetch(SARIT_URL), fetch(GRETIL_URL))
    except Exception as error:
        print(f"МЕРЕЖА-ПРОВАЛ: {type(error).__name__}: {error}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    print(f"SARIT: {result['sarit_verses']} віршів | GRETIL: {result['gretil_verses']}")
    print(f"лише GRETIL: {result['only_gretil']}")
    print(f"лише SARIT:  {result['only_sarit']}")
    print(f"спільних: {result['common']}")
    print(f"  точний збіг:  {result['exact']}")
    print(f"  орфографія:   {result['orthographic']}")
    print(f"  кандидатів:   {len(result['candidates'])} — ФІЛЬТР, не вирок")
    print(f"    лише голосні:      {len(result['vowel_only'])}")
    print(f"    різні приголосні:  {len(result['consonant_diff'])} — читати першими")
    return 0


if __name__ == "__main__":
    sys.exit(main())
