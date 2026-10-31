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
KNOWN_DUPLICATES = {
    "1.5": "дві незалежні картки злиті 31.10.2026; консолідація — окремим PR",
}

# Номер вірша з імені файлу: verse-1-5-..., verse-1-2-...
NAME_RE = re.compile(r"verse-(\d{1,2})-(\d{1,3})(?:[-_.]|$)")
# Номер вірша із заголовка H1: «Аштавакра-ґіта 1.5: ...» або «1.5 ...»
HEAD_RE = re.compile(r"^#\s+.*?\b(\d{1,2})\.(\d{1,3})\b")
# Діапазон у заголовку: «1.6–1.10», «1.6-1.10», «1.6 — 1.10».
HEAD_RANGE_RE = re.compile(r"\b(\d{1,2})\.(\d{1,3})\s*[-–—]\s*(\d{1,2})\.(\d{1,3})\b")
# Діапазон в імені файлу: verses-1-6-to-1-10, notes-1-6-to-1-10.
NAME_RANGE_RE = re.compile(r"-(\d{1,2})-(\d{1,3})-to-(\d{1,2})-(\d{1,3})(?:[-_.]|$)")


def is_range_card(path: Path) -> bool:
    """Чи картка охоплює ДІАПАЗОН віршів, а не один вірш.

    Файл «1.6–1.10» законно покриває п'ять віршів; вважати його карткою
    вірша 1.6 — хибне спрацювання. Саме так гейт уперше почервонів на
    власному `main` (31.10.2026): verses-1-6-to-1-10.md і
    notes-1-6-to-1-10.md обидва починаються з «1.6–1.10».
    """
    if NAME_RANGE_RE.search(path.stem):
        return True
    try:
        first = path.read_text(encoding="utf-8").splitlines()[0]
    except (OSError, UnicodeDecodeError, IndexError):
        return False
    return bool(HEAD_RANGE_RE.search(first))


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


def range_span(path: Path) -> tuple[int, int] | None:
    """Межі діапазону, якщо картка його заявляє: (початок, кінець)."""
    m = NAME_RANGE_RE.search(path.stem)
    if m:
        return int(m.group(1)) * 1000 + int(m.group(2)), int(m.group(3)) * 1000 + int(m.group(4))
    try:
        first = path.read_text(encoding="utf-8").splitlines()[0]
    except (OSError, UnicodeDecodeError, IndexError):
        return None
    m = HEAD_RANGE_RE.search(first)
    if m:
        return int(m.group(1)) * 1000 + int(m.group(2)), int(m.group(3)) * 1000 + int(m.group(4))
    return None


def collect_ranges() -> dict[tuple[int, int], list[str]]:
    """Картки-діапазони, згруповані за однаковим охопленням.

    Два файли з тим самим діапазоном — це теж дублювання роботи (так
    сталося з 1.6–1.10). Воно не валить збірку, але має бути видним.
    """
    spans: dict[tuple[int, int], list[str]] = {}
    if not RESEARCH.is_dir():
        return spans
    for path in sorted(RESEARCH.rglob("*.md")):
        span = range_span(path)
        if span is None:
            continue
        spans.setdefault(span, []).append(path.relative_to(ROOT).as_posix())
    return spans


def collect() -> dict[str, list[str]]:
    by_verse: dict[str, list[str]] = {}
    if not RESEARCH.is_dir():
        return by_verse
    for path in sorted(RESEARCH.rglob("*.md")):
        if is_range_card(path):
            continue
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

    range_dups = {k: v for k, v in collect_ranges().items() if len(v) > 1}
    for (start, end), files in sorted(range_dups.items()):
        print(f"ДУБЛІ-ДІАПАЗОН {start // 1000}.{start % 1000}–{end // 1000}.{end % 1000}: {len(files)} картки")
        for f in files:
            print(f"    {f}")
        print("    це дублювання роботи, але не збій: консолідація — окремим PR")

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
