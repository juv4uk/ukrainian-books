#!/usr/bin/env python3
"""Пошук ДУБЛЮВАННЯ редакторських карток за номером вірша.

Навіщено: 31.10.2026 у `research/ashtavakra/` зявилися Двц незалежні картки
до того самого вірша 1.5 — `verse-1-5-ashrama-varna.md` і
`verse-1-5-varna-ashrama.md`. Обидві злиті в `main`, обидві коректні за
формою, і жодна перевірка цього не побачила. Дубль не є помилкою формату,
тому `check_project.py` і `check_editorial_cards.py` його пропустили.

Режими:
  (типово)   — ЗВІТ: перелічує дублі, виходить з кодом 0;
  --strict   — ЗБІЙ на кожному дублі, крім перелічених у KNOWN_DUPLICATES.

Чому типово не падаємо: гейт, який одразу червоний на власному `main`,
вимикають за тиждень. Спершу треба побачити масштаб, потім — консолідувати,
і аж тоді вмикати суворий режим.

Не видаляє й не змінює чужі файли: рішення про консолідацію ухвалює людина
або окремий PR, у якому видно, чия робота зберігається.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research"

# Пари, які вже відомі й чекають на консолідацію. Ключ — номер вірша,
# значення — пояснення, чому дубль лишається.
# 31.10.2026: дублі віршів 1.5 і 1.6 законсолідовано (слабші файли зведено до
# покажчиків), тому список порожній. Додавати запис сюди — лише як тимчасовий
# захід із поясненням; порожній список робить гейт суворішим, не м'якшим.
KNOWN_DUPLICATES = {}

# Номер вірша з імені файлу: verse-1-5-..., verse-1-2-...
NAME_RE = re.compile(r"verse-(\d{1,2})-(\d{1,3})(?:[-_.]|$)")
# Номер вірша із заголовка H1: «Аштавакра-ґіта 1.5: ...» або «1.5 ...»
HEAD_RE = re.compile(r"^#\s+.*?\b(\d{1,2})\.(\d{1,3})\b")


def card_verse(path: Path) -> str | None:
    """Номер вірша, який картка заявляє: з імені файлу, інакше з H1."""
    m = NAME_RE.search(path.stem)
    if m:
        return f"{int(m.group(1))}.{int(m.group(2))}"
    try:
        for line in path.read_text(encoding="utf-8").splitlines()[:5]:
            h = HEAD_RE.match(line.strip())
            if h:
                return f"{int(h.group(1))}.{int(h.group(2))}"
    except (OSError, UnicodeDecodeError):
        return None
    return None


def collect() -> dict[str, list[str]]:
    by_verse: dict[str, list[str]] = {}
    if not RESEARCH.is_dir():
        return by_verse
    for path in sorted(RESEARCH.rglob("*.md")):
        verse = card_verse(path)
        if verse is None:
            continue
        by_verse.setdefault(verse, []).append(path.relative_to(ROOT).as_posix())
    return by_verse


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--strict", action="store_true",
                    help="збій на кожному дублі, крім KNOWN_DUPLICATES")
    args = ap.parse_args()

    by_verse = collect()
    duplicates = {v: files for v, files in by_verse.items() if len(files) > 1}

    if not duplicates:
        print(f"ДУБЛІ-OK карток={len(by_verse)} дублів немає")
        return 0

    strict_failures = 0
    for verse in sorted(duplicates, key=lambda s: (int(s.split(".")[0]), int(s.split(".")[1]))):
        files = duplicates[verse]
        known = verse in KNOWN_DUPLICATES
        label = "ДУБЛІ-ВІДОМО" if known else "ДУБЛІ-ЗНАЙДЕНО"
        print(f"{label} вірш {verse}: {len(files)} картки")
        for f in files:
            print(f"    {f}")
        if known:
            print(f"    причина: {KNOWN_DUPLICATES[verse]}")
        elif args.strict:
            strict_failures += 1

    if args.strict and strict_failures:
        print(
            f"ДУБЛІ-ЗБІЙ нових дублів: {strict_failures}. "
            "Консолідувати в один файл або внести до KNOWN_DUPLICATES з поясненням.",
            file=sys.stderr,
        )
        return 1

    print(f"ДУБЛІ-ПІДСУМОК карток={len(by_verse)} дублів={len(duplicates)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
