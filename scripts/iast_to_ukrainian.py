#!/usr/bin/env python3
"""Практична транслітерація IAST → українська кирилиця.

Це **не** наукова транскрипція санскриту і не фонетичний запис. Це практична
передача звучання українськими літерами, потрібна читачеві, який не знає
латинської діакритики: він має побачити, як вірш **звучить**, а не як він
записаний в IAST.

Таблиця відповідностей, обґрунтування кожного рішення й перелік того, що
свідомо втрачено, — у `docs/TRANSLITERATSIIA.md`. Цей файл — виконувана
частина того документа; якщо вони розійдуться, правильною є таблиця в
документі, а розходження — дефект.

Три принципи, закладені в код:

1. **Довгота не передається.** ``ā ī ū`` → ``а і у``: українська не розрізняє
   довгих і коротких голосних, а діакритика в кирилиці читалася б як наголос.
2. **Місце творення зберігається там, де це можливо.** ``ṭ ḍ ṇ`` → ``т д н``
   (ретрофлексні зливаються з зубними): окремих літер для ретрофлексних в
   українській немає, а вигадувати їх — гірше, ніж злити.
3. **Невідомий символ — виняток.** Тихого пропуску немає (див. `iast_tokens`).

Вжиток:
    python3 scripts/iast_to_ukrainian.py 'kathaṃ jñānam avāpnoti'
    python3 scripts/iast_to_ukrainian.py --cards
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.iast_tokens import (  # noqa: E402
    UnsupportedSymbol,
    tokenize,

)

ROOT = Path(__file__).resolve().parents[1]
CARDS = ROOT / "editorial" / "cards"

# --- приголосні --------------------------------------------------------
# Три рішення тримають систему несуперечливою:
#   • g → ґ, бо українське «ґ» — проривний [g], тобто санскритське g;
#   • придих після дзвінкого приголосного пишемо через «г» (бг, ґг, дг,
#     джг): придих озвучується, і українське «г» — саме фрикативний [ɣ];
#   • придих після глухого пишемо через «х» (кх, тх, пх): там придих
#     лишається глухим [x].
# Так виходять усталені українські форми: «Бгаґавадґіта», «дгарма»,
# «Будга», «катха», «Брахман».
CONSONANTS = {
    "k": "к", "kh": "кх", "g": "ґ", "gh": "ґг", "ṅ": "н",
    "c": "ч", "ch": "чч", "j": "дж", "jh": "джг", "ñ": "нь",
    "ṭ": "т", "ṭh": "тх", "ḍ": "д", "ḍh": "дг", "ṇ": "н",
    "t": "т", "th": "тх", "d": "д", "dh": "дг", "n": "н",
    "p": "п", "ph": "пх", "b": "б", "bh": "бг", "m": "м",
    "y": "й", "r": "р", "l": "л", "v": "в",
    "ś": "ш", "ṣ": "ш", "s": "с", "h": "х",
}

# Приголосні, після яких українська вимагає апострофа перед я/є/ї/ю.
APOSTROPHE_AFTER = frozenset("бпвмфр")

# --- голосні -----------------------------------------------------------
VOWELS = {
    "a": "а", "ā": "а", "i": "і", "ī": "і", "u": "у", "ū": "у",
    "e": "е", "ai": "ай", "o": "о", "au": "ау",
    # Складотворчі плавні розв'язуються окремо (див. syllabic()).
    "ṛ": "ри", "ṝ": "ри", "ḷ": "ли", "ḹ": "ли",
}

# Голосні після м'якого приголосного (у нас — лише ñ → нь).
SOFT_VOWELS = {
    "а": "я", "е": "є", "і": "і", "у": "ю", "о": "ьо",
}

# Йотовані відповідники для y + голосний.
YOTATED = {
    "а": "я", "е": "є", "і": "ї", "у": "ю", "о": "йо",
    "ай": "яй", "ау": "яу",
}

MARKS = {"ṃ": "м", "ṁ": "м", "ḥ": "х"}
AVAGRAHA = "’"

# Символи, які переносяться без змін.
KEEP = frozenset(" .,;:!?-–—()[]{}\"«»…/*+=|\n\r\t")

SYLLABIC = frozenset({"ṛ", "ṝ", "ḷ", "ḹ"})


def syllabic(key: str, following: list[tuple[str, str]]) -> str:
    """``ṛ`` → «рі» чи «ри» за складом.

    Правило детерміноване й перевірне: дивимось, чи є в цьому слові далі
    голосний. Якщо є — склад відкритий і пишемо «рі» (kṛ-ṣṇa → крішна,
    ṛ-ṣi → ріші, kṛ-ta → кріта). Якщо складотворчий стоїть у кінці слова —
    «ри» (pi-tṛ → питри, mā-tṛ → матри). Обидві форми — усталені в
    українських передачах санскриту: «Крішна», але «матри».
    """
    base = "р" if key in ("ṛ", "ṝ") else "л"
    for kind, _ in following:
        if kind == "V":
            return base + "і"
        if kind in ("S", "D"):
            break
    return base + "и"


def _push(out: list[str], letter: str) -> None:
    """Дописати літеру, не доводячи однакові літери до трьох.

    Санскритське ``icchasi`` — це ``c`` + ``ch``, тобто за нашими правилами
    «ч» + «чч» = три «ч» поспіль. Українська такого не пише, і читач бачить
    друкарський збій, а не подвоєння. Тому серія однакових літер обрізається
    до двох — це стосується лише справжніх подвоєнь.
    """
    if (letter and len(set(letter)) == 1 and out
            and out[-1].endswith(letter[0])):
        run = 0
        tail = "".join(out)[::-1]
        while run < len(tail) and tail[run] == letter[0]:
            run += 1
        keep = max(0, 2 - run)
        out.append(letter[:keep] if keep < len(letter) else letter)
        return
    out.append(letter)


def to_ukrainian(text: str, where: str = "") -> str:
    """Перетворити IAST на українську практичну транслітерацію."""
    tokens = tokenize(text, where)
    out: list[str] = []
    last: str | None = None      # остання записана літера (для апострофа)
    soft = False                 # попередній приголосний м'який (ñ → нь)
    index = 0
    while index < len(tokens):
        kind, key = tokens[index]
        if kind == "C":
            if key == "y" and index + 1 < len(tokens) and tokens[index + 1][0] == "V":
                vowel = VOWELS[tokens[index + 1][1]]
                letter = YOTATED.get(vowel, "й" + vowel)
                if letter in ("я", "є", "ї", "ю") and last in APOSTROPHE_AFTER:
                    out.append("'")
                out.append(letter)
                last, soft = letter[-1], False
                index += 2
                continue
            letter = CONSONANTS[key]
            _push(out, letter)
            last, soft = letter[-1], letter.endswith("ь")
            index += 1
            continue
        if kind == "V":
            if key in SYLLABIC:
                piece = syllabic(key, tokens[index + 1:])
                out.append(piece)
                last, soft = piece[-1], False
                index += 1
                continue
            vowel = VOWELS[key]
            if soft:
                # «нь» + голосний = «ня», а не «нья»: ь замінюється на йотовану.
                if out and out[-1].endswith("ь"):
                    out[-1] = out[-1][:-1]
                letter = SOFT_VOWELS.get(vowel, vowel)
            else:
                letter = vowel
                if letter in ("я", "є", "ї", "ю") and last in APOSTROPHE_AFTER:
                    out.append("'")
            out.append(letter)
            last, soft = letter[-1], False
            index += 1
            continue
        if kind == "M":
            out.append(MARKS[key])
            last, soft = MARKS[key][-1], False
            index += 1
            continue
        if kind == "A":
            out.append(AVAGRAHA)
            last, soft = AVAGRAHA, False
            index += 1
            continue
        out.append(key)
        last, soft = key[-1], False
        index += 1
    return "".join(out)


def run_cards(folder: Path = CARDS) -> dict:
    """Прогін по всіх картках; перший збій — виняток."""
    cards = []
    for path in sorted(folder.glob("*.json")):
        cards.append(json.loads(path.read_text(encoding="utf-8")))
    converted = 0
    skipped: list[str] = []
    total = 0
    for card in cards:
        ident = str(card.get("id") or "?")
        iast = card.get("iast")
        if not iast:
            skipped.append(ident)
            continue
        to_ukrainian(iast, where=f"картці {ident}")
        converted += 1
        total += len(iast)
    return {
        "cards_total": len(cards),
        "cards_converted": converted,
        "cards_without_iast": skipped,
        "characters_converted": total,
        "status": "ok",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("text", nargs="*", help="рядок IAST (можна кілька)")
    parser.add_argument("--cards", action="store_true",
                        help="прогін по всіх картках editorial/cards/*.json")
    args = parser.parse_args(argv)
    try:
        if args.cards:
            print(json.dumps(run_cards(), ensure_ascii=False, indent=2))
            return 0
        if not args.text:
            parser.error("потрібен рядок IAST або --cards")
        print(to_ukrainian(" ".join(args.text)))
        return 0
    except UnsupportedSymbol as exc:
        print(f"ПОМИЛКА: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
