#!/usr/bin/env python3
"""Механічна транслітерація IAST → деванагарі.

Це **не** переклад, не редакторське читання й **не свідок**. Скрипт переводить
символи за сталою таблицею: приголосні, голосні, матрі, вірама, анусвара,
вісарґа, аваґраха, данда. Він не відновлює сандгі, не додає знаків, яких немає
у вході, і не виправляє помилок джерела.

Призначення — показати читачеві деванагарі того самого читання, яке вже
збережене в полі `iast` картки. **Якщо деванагарі розійдеться з IAST,
правильною є картка, а не скрипт.**

Головна вимога: на невідомому символі скрипт **падає голосно**
(`UnsupportedSymbol`), а не пропускає його тихо. Тихого пропуску тут немає
навмисно: пропущений символ непомітно зіпсував би сакральний текст, і ніхто б
не дізнався, де саме.

Зворотна функція `to_iast` існує лише для самоперевірки (`--roundtrip`):
вона доводить, що відображення оборотне на реальних віршах.

Вжиток:
    python3 scripts/iast_to_devanagari.py 'kathaṃ jñānam avāpnoti'
    python3 scripts/iast_to_devanagari.py --cards          # прогін по всіх картках
    python3 scripts/iast_to_devanagari.py --roundtrip      # самоперевірка на картках
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.iast_tokens import (  # noqa: E402
    DEVANAGARI_DANDA,
    UnsupportedSymbol,
    tokenize,
)

ROOT = Path(__file__).resolve().parents[1]
CARDS = ROOT / "editorial" / "cards"

VOWELS = {
    "a": "अ", "ā": "आ", "i": "इ", "ī": "ई", "u": "उ", "ū": "ऊ",
    "ṛ": "ऋ", "ṝ": "ॠ", "ḷ": "ऌ", "ḹ": "ॡ", "e": "ए", "ai": "ऐ",
    "o": "ओ", "au": "औ",
}
MATRAS = {
    "a": "", "ā": "ा", "i": "ि", "ī": "ी", "u": "ु", "ū": "ू",
    "ṛ": "ृ", "ṝ": "ॄ", "ḷ": "ॢ", "ḹ": "ॣ", "e": "े", "ai": "ै",
    "o": "ो", "au": "ौ",
}
CONSONANTS = {
    "k": "क", "kh": "ख", "g": "ग", "gh": "घ", "ṅ": "ङ",
    "c": "च", "ch": "छ", "j": "ज", "jh": "झ", "ñ": "ञ",
    "ṭ": "ट", "ṭh": "ठ", "ḍ": "ड", "ḍh": "ढ", "ṇ": "ण",
    "t": "त", "th": "थ", "d": "द", "dh": "ध", "n": "न",
    "p": "प", "ph": "फ", "b": "ब", "bh": "भ", "m": "म",
    "y": "य", "r": "र", "l": "ल", "v": "व",
    "ś": "श", "ṣ": "ष", "s": "स", "h": "ह",
}
MARKS = {"ṃ": "ं", "ṁ": "ं", "ḥ": "ः"}
AVAGRAHA = "ऽ"
DANDA = {"|": "।", "||": "॥"}
VIRAMA = "्"

REVERSE_CONSONANTS = {v: k for k, v in CONSONANTS.items()}
REVERSE_VOWELS = {v: k for k, v in VOWELS.items()}
REVERSE_MATRAS = {v: k for k, v in MATRAS.items() if v}
REVERSE_MARKS = {"ं": "ṃ", "ः": "ḥ"}
REVERSE_DANDA = {v: k for k, v in DANDA.items()}


def to_devanagari(text: str, where: str = "") -> str:
    """Перетворити рядок IAST на деванагарі.

    Невідомий символ піднімає `UnsupportedSymbol` — мовчазного пропуску немає.
    """
    out: list[str] = []
    pending_consonant = False
    for kind, key in tokenize(text, where):
        if kind == "C":
            if pending_consonant:
                out.append(VIRAMA)
            out.append(CONSONANTS[key])
            pending_consonant = True
            continue
        if kind == "V":
            if pending_consonant:
                out.append(MATRAS[key])
                pending_consonant = False
            else:
                out.append(VOWELS[key])
            continue
        # Далі — усе, що не є приголосним чи голосним: перед ним склад
        # закривається вірамою, якщо приголосний лишився без голосного.
        if pending_consonant:
            out.append(VIRAMA)
            pending_consonant = False
        if kind == "M":
            out.append(MARKS[key])
        elif kind == "A":
            out.append(AVAGRAHA)
        elif kind == "D":
            out.append(DANDA[key])
        elif kind == "DV":
            out.append(key)
        else:  # "S" і "P" переносяться без змін
            out.append(key)
    if pending_consonant:
        out.append(VIRAMA)
    return "".join(out)


def to_iast(text: str) -> str:
    """Зворотне відображення деванагарі → IAST. Лише для самоперевірки."""
    out: list[str] = []
    i = 0
    length = len(text)
    while i < length:
        char = text[i]
        if char in REVERSE_CONSONANTS:
            out.append(REVERSE_CONSONANTS[char])
            nxt = text[i + 1] if i + 1 < length else ""
            if nxt == VIRAMA:
                i += 2
                continue
            if nxt in REVERSE_MATRAS:
                out.append(REVERSE_MATRAS[nxt])
                i += 2
                continue
            # Без вірами й без матрі — неявний «a».
            out.append("a")
            i += 1
            continue
        if char in REVERSE_VOWELS:
            out.append(REVERSE_VOWELS[char])
            i += 1
            continue
        if char in REVERSE_MARKS:
            out.append(REVERSE_MARKS[char])
            i += 1
            continue
        if char in REVERSE_DANDA:
            out.append(REVERSE_DANDA[char])
            i += 1
            continue
        if char == AVAGRAHA:
            out.append("'")
            i += 1
            continue
        if char in DEVANAGARI_DANDA:
            i += 1
            continue
        out.append(char)
        i += 1
    return "".join(out)


def load_cards(folder: Path = CARDS) -> list[dict]:
    """Усі картки з полем `iast`; порожні пропускаються з підрахунком."""
    cards: list[dict] = []
    for path in sorted(folder.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        cards.append(data)
    return cards


def run_cards(folder: Path = CARDS) -> dict:
    """Прогін по всіх картках. Перший збій — виняток, а не «попередження»."""
    cards = load_cards(folder)
    converted = 0
    skipped: list[str] = []
    already: list[str] = []
    total_chars = 0
    alphabet: set[str] = set()
    for card in cards:
        ident = str(card.get("id") or "?")
        iast = card.get("iast")
        if not iast:
            skipped.append(ident)
            continue
        if any(0x0900 <= ord(c) <= 0x097F for c in iast):
            already.append(ident)
        total_chars += len(iast)
        alphabet.update(iast)
        to_devanagari(iast, where=f"картці {ident}")
        converted += 1
    return {
        "cards_total": len(cards),
        "cards_converted": converted,
        "cards_without_iast": skipped,
        "cards_already_devanagari": already,
        "characters_converted": total_chars,
        "alphabet": "".join(sorted(alphabet)),
        "status": "ok",
    }


def run_roundtrip(folder: Path = CARDS) -> dict:
    """Довести оборотність: IAST → деванагарі → IAST на всіх картках."""
    cards = load_cards(folder)
    failures: list[str] = []
    checked = 0
    for card in cards:
        iast = card.get("iast")
        if not iast:
            continue
        ident = str(card.get("id") or "?")
        checked += 1
        back = to_iast(to_devanagari(iast, where=f"картці {ident}"))
        if back != iast:
            failures.append(f"{ident}: {iast!r} → {back!r}")
    return {
        "cards_checked": checked,
        "failures": failures,
        "status": "ok" if not failures else "failed",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("text", nargs="*", help="рядок IAST (можна кілька)")
    parser.add_argument("--cards", action="store_true",
                        help="прогін по всіх картках editorial/cards/*.json")
    parser.add_argument("--roundtrip", action="store_true",
                        help="самоперевірка оборотності на всіх картках")
    args = parser.parse_args(argv)

    try:
        if args.cards:
            print(json.dumps(run_cards(), ensure_ascii=False, indent=2))
            return 0
        if args.roundtrip:
            result = run_roundtrip()
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["status"] == "ok" else 1
        if not args.text:
            parser.error("потрібен рядок IAST, або --cards, або --roundtrip")
        print(to_devanagari(" ".join(args.text)))
        return 0
    except UnsupportedSymbol as exc:
        print(f"ПОМИЛКА: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
