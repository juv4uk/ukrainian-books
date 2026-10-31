#!/usr/bin/env python3
"""Спільний лексер IAST для конвертерів у деванагарі та в українську кирилицю.

Лексер навмисно **не знає** нічого про вихідне письмо: він лише розкладає
рядок IAST на класи символів. Так обидва конвертери читають той самий потік
і не розходяться в тому, що вважати приголосним, а що — голосним.

Головна вимога власника: на невідомому символі конвертер мусить **впасти
голосно**, а не пропустити його тихо. Тому тут немає «м'якого» режиму: усе,
чого немає в таблицях, піднімає `UnsupportedSymbol`.

Класи токенів:
  ``C`` — приголосний (k, kh, … ś, ṣ, h);
  ``V`` — голосний (a, ā, … ai, au) і складотворчі ṛ ṝ ḷ;
  ``M`` — надрядковий/підрядковий знак (ṃ ṁ ḥ);
  ``A`` — аваґраха (ʼ ’ '), тобто «випалий» a;
  ``D`` — данда (| або ||);
  ``P`` — розділовий знак, який переноситься без змін;
  ``S`` — пробільний символ.

Лексер — власний технічний внесок під «ВОЛЬНІСТЮ»; він не містить текстів
чужих видань і не робить мережевих запитів.
"""

from __future__ import annotations

CONSONANTS: tuple[str, ...] = (
    # Найдовші ключі — першими: лексер бере найдовший збіг, але порядок
    # у кортежі потрібен лише для читача таблиці.
    "kh", "gh", "ch", "jh", "ṭh", "ḍh", "th", "dh", "ph", "bh",
    "k", "g", "ṅ", "c", "j", "ñ", "ṭ", "ḍ", "ṇ", "t", "d", "n",
    "p", "b", "m", "y", "r", "l", "v", "ś", "ṣ", "s", "h",
)

VOWELS: tuple[str, ...] = (
    "ai", "au",
    "a", "ā", "i", "ī", "u", "ū", "ṛ", "ṝ", "ḷ", "ḹ", "e", "o",
)

MARKS: tuple[str, ...] = ("ṃ", "ṁ", "ḥ")

# Аваґраха в різних редакціях IAST: прямий апостроф, модифікатор і типографський.
AVAGRAHA = ("'", "ʼ", "’")

DANDA = ("||", "|")

# Розділові знаки й цифри переносяться без змін: цифри в тексті — це
# нумерація вірша (``||1|1||``), а не санскритське слово.
PUNCTUATION = frozenset(" .,;:!?-–—()[]{}\"«»…/*+=0123456789")

WHITESPACE = frozenset(" \n\r\t")

# Деванагарі на вході теж приймаємо як «уже готове» — це потрібно, щоб
# конвертер не ламався на картках, де поле вже переписано деванагарі.
DEVANAGARI_RANGE = (0x0900, 0x097F)
DEVANAGARI_DANDA = frozenset("।॥ऽ॰")


class UnsupportedSymbol(ValueError):
    """Символ IAST, для якого немає відповідника. Завжди — виняток, не пропуск."""

    def __init__(self, char: str, index: int, text: str, where: str = "") -> None:
        self.char = char
        self.index = index
        self.text = text
        self.where = where
        start = max(0, index - 12)
        stop = min(len(text), index + 12)
        context = text[start:stop]
        place = f" у {where}" if where else ""
        super().__init__(
            f"невідомий символ {char!r} (U+{ord(char):04X}) на позиції {index}"
            f"{place}; контекст: …{context}…"
        )


def _key_table() -> dict[str, str]:
    """Ключ → клас. Довші ключі мають пріоритет при збігу."""
    table: dict[str, str] = {}
    for key in CONSONANTS:
        table[key] = "C"
    for key in VOWELS:
        table[key] = "V"
    for key in MARKS:
        table[key] = "M"
    return table


KEYS = _key_table()
MAX_KEY = max(len(k) for k in list(KEYS) + list(DANDA))


def tokenize(text: str, where: str = "") -> list[tuple[str, str]]:
    """Розкласти IAST на токени ``(клас, ключ)``; на невідомому — виняток.

    ``where`` лише потрапляє в текст помилки (наприклад, ``картка 1.1``).
    """
    tokens: list[tuple[str, str]] = []
    i = 0
    length = len(text)
    while i < length:
        char = text[i]
        if char in WHITESPACE:
            tokens.append(("S", char))
            i += 1
            continue
        if char in DANDA:
            # || — одна данда-пара, | — одна данда.
            if text.startswith("||", i):
                tokens.append(("D", "||"))
                i += 2
            else:
                tokens.append(("D", "|"))
                i += 1
            continue
        if char in AVAGRAHA:
            tokens.append(("A", char))
            i += 1
            continue
        if char in PUNCTUATION:
            tokens.append(("P", char))
            i += 1
            continue
        low, high = DEVANAGARI_RANGE
        if low <= ord(char) <= high:
            tokens.append(("DV", char))
            i += 1
            continue
        matched = None
        for size in range(MAX_KEY, 0, -1):
            candidate = text[i:i + size]
            if candidate in KEYS:
                matched = candidate
                break
        if matched is None:
            raise UnsupportedSymbol(char, i, text, where)
        tokens.append((KEYS[matched], matched))
        i += len(matched)
    return tokens


def words(tokens: list[tuple[str, str]]) -> list[list[tuple[str, str]]]:
    """Розбити токени на слова (роздільники — пробіли й данди)."""
    out: list[list[tuple[str, str]]] = []
    current: list[tuple[str, str]] = []
    for kind, key in tokens:
        if kind in ("S", "D"):
            if current:
                out.append(current)
                current = []
        else:
            current.append((kind, key))
    if current:
        out.append(current)
    return out
