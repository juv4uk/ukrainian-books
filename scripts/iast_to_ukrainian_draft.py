#!/usr/bin/env python3
"""Чорнова українська передача IAST, а НЕ затверджена наукова транскрипція.

Кожна видана сторінка потребує звірки санскритолога. У цьому інструменті
вихідне IAST ніколи не замінюється редакторською підказкою.
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata

# Умовні редакторські відповідності. Не є таблицею всіх правил Д. Бурби:
# голосна довгота, ретрофлексія, анусвара й сандгі втрачають відмінності.
LETTERS = {
    "kh": "кх", "gh": "г", "ch": "чх", "jh": "джг",
    "ṭh": "тх", "ḍh": "дг", "th": "тх", "dh": "дг",
    "ph": "пх", "bh": "бг", "ai": "ай", "au": "ау",
    "k": "к", "g": "ґ", "ṅ": "н", "c": "ч", "j": "дж",
    "ñ": "нь", "ṭ": "т", "ḍ": "д", "ṇ": "н",
    "t": "т", "d": "д", "n": "н",
    "p": "п", "b": "б", "m": "м",
    "y": "й", "r": "р", "l": "л", "v": "в",
    "ś": "ш", "ṣ": "ш", "s": "с", "h": "г",
    "a": "а", "ā": "а", "i": "і", "ī": "і",
    "u": "у", "ū": "у", "ṛ": "рі", "ṝ": "рі",
    "ḷ": "лі", "e": "е", "o": "о",
    "ḥ": "х",
}
KEYS = sorted(LETTERS, key=len, reverse=True)
SEPARATORS = set(" \t\n\r.,;:!?—–-()[]’'")
CONSONANTS = set("kgṅcjñṭḍṇtdnpbmyrlvśṣsh")
SOFTEN = set("tdnls")
Y_VOWELS = {
    "a": "я", "ā": "я", "i": "ї", "ī": "ї",
    "u": "ю", "ū": "ю", "e": "є",
    "ai": "яй", "o": "йо", "au": "яу",
}


def _one_line(source: str) -> tuple[str, list[str]]:
    text = unicodedata.normalize("NFC", source).casefold()
    result: list[str] = []
    notes: set[str] = set()
    i = 0
    previous = ""
    while i < len(text):
        char = text[i]
        if char in SEPARATORS:
            result.append("’" if char == "'" else char)
            previous = "" if char.isspace() else previous
            i += 1
            continue

        if text.startswith(("jñā", "jña"), i):
            result.append("джня")
            notes.add("палатальне jñ: потрібна філологічна звірка")
            previous = "a"
            i += 3
            continue

        if char == "y":
            next_vowel = next((v for v in sorted(Y_VOWELS, key=len, reverse=True)
                               if text.startswith(v, i + 1)), None)
            if next_vowel is not None:
                rendered = Y_VOWELS[next_vowel]
                if previous in SOFTEN:
                    rendered = "ь" + rendered
                elif previous in CONSONANTS:
                    rendered = "’" + rendered
                result.append(rendered)
                notes.add("йотовані сполуки: потрібна редакторська звірка")
                i += 1 + len(next_vowel)
                previous = next_vowel
                continue

        if char in ("ṃ", "ṁ"):
            following = text[i + 1:i + 2]
            if not following or following.isspace():
                result.append("м")
            elif following in "pbmv":
                result.append("м")
            elif following in "cj":
                result.append("нь")
            else:
                result.append("н")
            notes.add("анусвара: умовне наближення, перевірити морфему й контекст")
            previous = char
            i += 1
            continue

        token = next((k for k in KEYS if text.startswith(k, i)), None)
        if token is None:
            raise ValueError(f"Непідтримуваний символ IAST на позиції {i}: {char!r}")
        result.append(LETTERS[token])
        if token in ("ā", "ī", "ū", "ṝ", "ai", "au"):
            notes.add("довгота й дифтонги: кирилична підказка не передає всіх розрізнень")
        if token in ("ṭ", "ḍ", "ṇ", "ṣ", "ṛ", "ṝ", "ḷ", "ś", "ñ", "ṅ"):
            notes.add("місце творення й складотворчі сонанти спрощено")
        if token in ("gh", "jh", "ḍh", "dh", "bh", "h"):
            notes.add("дзвінкі придихові та h: потрібна звірка з редакційним стандартом")
        if token == "ḥ":
            notes.add("вісарґа: потрібна перевірка кінцевої вимови")
        previous = token[-1]
        i += len(token)

    return "".join(result), sorted(notes)


def draft_reading(iast: str) -> dict:
    """Вивести контрольовані кандидати для кожного піввірша, не для друку."""
    if not isinstance(iast, str) or not iast.strip():
        raise ValueError("Потрібний непорожній рядок IAST")
    normalized = iast.replace("॥", "||").replace("।", "|")
    parts = [part.strip() for part in re.split(r"\s*\|+\s*", normalized)
             if part.strip()]
    if not parts:
        raise ValueError("Не знайдено рядків IAST")
    lines = []
    warnings: set[str] = set()
    for index, part in enumerate(parts, 1):
        reading, notes = _one_line(part)
        if not reading.strip():
            raise ValueError("Порожній рядок після перетворення")
        lines.append({"line": index, "iast": part, "ukrainian_candidate": reading})
        warnings.update(notes)
    return {
        "status": "потребує-ручної-звірки",
        "purpose": "чернеткова підказка; НЕ джерельний свідок і НЕ затверджена транскрипція",
        "lines": lines,
        "warnings": sorted(warnings),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("iast", nargs="+", help="рядки IAST із | між піввіршами")
    args = parser.parse_args()
    try:
        result = draft_reading(" ".join(args.iast))
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
