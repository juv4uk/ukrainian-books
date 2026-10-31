#!/usr/bin/env python3
"""Механічна транслітерація IAST → деванагарі.

Це **не** переклад і не редакторське читання: скрипт переводить символи за
сталою таблицею відповідностей. Він не відновлює сандгі, не додає вісарґу чи
анусвару, яких немає у вході, і не виправляє помилок джерела.

Призначення — показати читачеві деванагарі того самого читання, яке вже
звірене за свідком і збережене в полі `iast` картки. Якщо транслітерація
розійдеться з IAST, це помилка скрипта, а не варіант тексту.
"""

from __future__ import annotations

import sys

VOWELS = {
    "a": "अ", "ā": "आ", "i": "इ", "ī": "ई", "u": "उ", "ū": "ऊ",
    "ṛ": "ऋ", "ṝ": "ॠ", "ḷ": "ऌ", "e": "ए", "ai": "ऐ", "o": "ओ", "au": "औ",
}
MATRAS = {
    "a": "", "ā": "ा", "i": "ि", "ī": "ी", "u": "ु", "ū": "ू",
    "ṛ": "ृ", "ṝ": "ॄ", "ḷ": "ॢ", "e": "े", "ai": "ै", "o": "ो", "au": "ौ",
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
MARKS = {"ṃ": "ं", "ṁ": "ं", "ḥ": "ः", "'": "ऽ"}
VIRAMA = "्"
MAX_KEY = max(len(k) for k in list(CONSONANTS) + list(VOWELS))


def to_devanagari(text: str) -> str:
    """Перетворює рядок IAST на деванагарі, зберігаючи розділові знаки."""
    out: list[str] = []
    pending_consonant = False
    i = 0
    while i < len(text):
        chunk = None
        for size in range(MAX_KEY, 0, -1):
            candidate = text[i:i + size]
            if candidate in CONSONANTS or candidate in VOWELS:
                chunk = candidate
                break
        if chunk is None:
            char = text[i]
            if pending_consonant:
                out.append(VIRAMA)
                pending_consonant = False
            out.append(MARKS.get(char, char))
            i += 1
            continue
        if chunk in CONSONANTS:
            if pending_consonant:
                out.append(VIRAMA)
            out.append(CONSONANTS[chunk])
            pending_consonant = True
        else:  # голосний
            if pending_consonant:
                out.append(MATRAS[chunk])
                pending_consonant = False
            else:
                out.append(VOWELS[chunk])
        i += len(chunk)
    if pending_consonant:
        out.append(VIRAMA)
    return "".join(out)


def main(argv: list[str]) -> int:
    if not argv:
        print("вжиток: iast_to_devanagari.py '<IAST>'", file=sys.stderr)
        return 2
    print(to_devanagari(" ".join(argv)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
