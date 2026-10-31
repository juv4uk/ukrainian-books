#!/usr/bin/env python3
"""Практична українська транслітерація IAST.

Це передача **звучання** українськими літерами, а не наукова латинська
транскрипція й не переклад. Скрипт переводить символи за сталою таблицею,
яка виведена з уже зроблених вручну наукових розділів
(`books/ashtavakra-gita/rozdil-5-naukove.md`, `rozdil-6-naukove.md`) і
перевіряється на них у тестах.

Головне застереження: якщо транслітерація розійдеться з ручним зразком,
правий зразок, а не скрипт. Скрипт не відновлює сандгі й не виправляє
джерела — він лише передає те, що вже звірене в полі `iast`.

Запуск: python3 scripts/iast_to_ukrainska.py "na te saṅgo 'sti"
"""
from __future__ import annotations

import sys

# Приголосні: IAST → українська. Довші сполуки стоять перед коротшими,
# інакше «kh» розібралося б як «k» + «h».
CONSONANTS = (
    ("cch", "ччх"), ("ch", "чх"), ("kh", "кх"), ("gh", "ґг"), ("jh", "джг"), ("ṭh", "тх"),
    ("ḍh", "дг"), ("th", "тх"), ("dh", "дг"), ("ph", "пх"), ("bh", "бг"),
    ("k", "к"), ("g", "ґ"), ("ṅ", "н"), ("c", "ч"), ("jj", "ддж"), ("j", "дж"),
    ("ñ", "нь"), ("ṭ", "т"), ("ḍ", "д"), ("ṇ", "н"), ("t", "т"),
    ("d", "д"), ("n", "н"), ("p", "п"), ("b", "б"), ("m", "м"),
    ("y", "й"), ("r", "р"), ("l", "л"), ("v", "в"), ("ś", "ш"),
    ("ṣ", "ш"), ("s", "с"), ("h", "х"),
)

VOWELS = {
    "a": "а", "ā": "а", "i": "і", "ī": "і", "u": "у", "ū": "у",
    "ṛ": "рі", "ṝ": "рі", "ḷ": "лі", "e": "е", "ai": "ай", "o": "о", "au": "ау",
}

# Після приголосного «й» переходить у м'якість, а голосний м'якшується.
# Це видно у зразках: tya → тья, vyā → вья, tyi → тьї, jñā → джня.
SOFT = {"a": "я", "ā": "я", "i": "ї", "ī": "ї", "u": "ю", "ū": "ю",
        "e": "є", "o": "ьо", "ai": "яй", "au": "яу"}

# Після голосного «й» лишається «й» перед і та перед приголосним, але
# зливається з «а» в «я» (layam → лаям).
Y_AFTER_VOWEL = {"a": "я", "ā": "я"}

MARKS = {"ṃ": "м", "ṁ": "м", "ḥ": "х", "'": "’", "’": "’"}

PUNCT = {"|": "|", "||": "||"}


def transliterate(text: str) -> str:
    """Передати IAST українськими літерами."""
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch in " \n\t":
            out.append(" ")
            i += 1
            continue
        if text.startswith("||", i):
            out.append("||"); i += 2; continue
        if ch == "|":
            out.append("|"); i += 1; continue
        if ch in MARKS:
            out.append(MARKS[ch]); i += 1; continue

        matched = None
        for src, dst in CONSONANTS:
            if text.startswith(src, i):
                matched = (src, dst); break
        if matched:
            src, dst = matched
            i += len(src)
            nxt = text[i] if i < n else ""
            palatal = dst.endswith("ь")          # ñ
            if dst in ("й",) and nxt in SOFT:    # y перед голосним
                after_vowel = bool(out) and out[-1] and out[-1][-1] in "аеиіоуяюєї"
                if nxt in ("a", "ā"):
                    # після приголосного м'якість лишається: tya → тья
                    out.append("я" if after_vowel else "ья")
                elif after_vowel:
                    out.append("й" + VOWELS.get(nxt, ""))
                else:
                    out.append("ь" + SOFT[nxt])
                i += 1
                continue
            if dst == "й" and nxt not in SOFT:   # y у кінці складу
                after_vowel = bool(out) and out[-1] and out[-1][-1] in "аеиіоуяюєї"
                out.append("й" if after_vowel else "ь")
                continue
            if palatal:
                # ñ не дає окремого «ь»: джня, не джнья
                out.append(dst[:-1])
                if nxt in SOFT:
                    out.append(SOFT[nxt]); i += 1
                continue
            out.append(dst)
            continue

        if text.startswith(("ai", "au"), i):
            out.append(VOWELS[text[i:i+2]]); i += 2; continue
        if ch in VOWELS:
            out.append(VOWELS[ch]); i += 1; continue
        out.append(ch); i += 1
    return " ".join("".join(out).split())


def main() -> int:
    if len(sys.argv) < 2:
        print("вжиток: python3 scripts/iast_to_ukrainska.py \"<IAST>\"", file=sys.stderr)
        return 2
    print(transliterate(" ".join(sys.argv[1:])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
