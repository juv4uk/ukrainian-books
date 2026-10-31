#!/usr/bin/env python3
"""Пошук ДУБЛЮВАННЯ редакторських карток за номером вірша.

Навіщено: 31.10.2026 у `research/ashtavakra/` зявилися Двц незалежні картки
до того самого вірша 1.5 — `verse-1-5-ashrama-varna.md` і
`verse-1-5-varna-ashrama.md`. Обидві злиті в `main`, обидві коректні за
формою, і жодна перевірка цього не побачила. Дубль не є помилкою формату,
тому `check_project.py` і `check_editorial_cards.py` його пропустили.

Друга частина: до 31.10.2026 скрипт сканував ЛИШЕ `research/**.md` і на `main`
бачив 3 картки, тоді як у `editorial/cards/` лежить 18 JSON-карток. Дублі серед
JSON-карток не перевіряло ніщо. Тепер скануються обидва джерела:

  research/**.md        — markdown-картки й примітки (номер вірша з імені файлу
                          або з H1, як і раніше);
  editorial/cards/*.json — JSON-картки (номер вірша з ЯВНОГО поля `id`, а не з
                          імені файлу; ім'я — лише запасний варіант).

Формати розрізняються навмисно. Два файли того самого формату на один вірш —
це дубль і в `--strict` він валить перевірку. Картка й текстова примітка до
того самого вірша — це ПЕРЕТИН: `research/` містить дослідницьку примітку, а не
другу картку, тому такий збіг друкується окремим рядком `ДУБЛІ-ПЕРЕТИН` і не
валить збірку. Рішення «примітка чи картка» ухвалює людина окремим PR; гейт,
який червоний на власному `main`, вимикають за тиждень.

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
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research"
CARDS = ROOT / "editorial" / "cards"

# Пари, які вже відомі й чекають на консолідацію. Ключ — номер вірша,
# значення — пояснення, чому дубль лишається.
# 31.10.2026: дублі віршів 1.5 і 1.6–1.10 законсолідовано (слабші файли зведено
# до покажчиків), тому список порожній. Запис «1.6» із PR #71 тут не спрацьовував
# узагалі: після PR #69 картки-діапазони не групуються за номером вірша.
# Додавати запис сюди — лише як тимчасовий захід із поясненням; порожній список
# робить гейт суворішим, не м'якшим.
KNOWN_DUPLICATES = {}

# Номер вірша з імені файлу: verse-1-5-..., verse-1-2-...
NAME_RE = re.compile(r"verse-(\d{1,2})-(\d{1,3})(?:[-_.]|$)")
# Номер вірша із заголовка H1; відкинути фрагменти календарних дат 31.10.2026.
HEAD_RE = re.compile(r"^#\s+.*?\b(\d{1,2})\.(\d{1,3})(?!\.\d)\b")
# Діапазон у заголовку: «1.6–1.10», «1.6-1.10», «1.6 — 1.10».
HEAD_RANGE_RE = re.compile(r"\b(\d{1,2})\.(\d{1,3})\s*[-–—]\s*(\d{1,2})\.(\d{1,3})\b")
# Діапазон в імені файлу: verses-1-6-to-1-10, notes-1-6-to-1-10.
NAME_RANGE_RE = re.compile(r"-(\d{1,2})-(\d{1,3})-to-(\d{1,2})-(\d{1,3})(?:[-_.]|$)")
# Номер вірша в полі `id` JSON-картки: «2.4». Схема docs/VERSE_CARD_SCHEMA.md
# дозволяє лише один вірш на картку, тому діапазонів тут не буває.
JSON_ID_RE = re.compile(r"([1-9]\d*)\.([1-9]\d*)")


def label(path: Path) -> str:
    """Шлях для звіту: відносний до кореня репозиторію, якщо це можливо."""
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


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
        chapter, verse = int(m.group(1)), int(m.group(2))
        if 1 <= chapter <= 20 and verse >= 1:
            return f"{chapter}.{verse}"
    try:
        for line in path.read_text(encoding="utf-8").splitlines()[:5]:
            h = HEAD_RE.match(line.strip())
            if h:
                chapter, verse = int(h.group(1)), int(h.group(2))
                if 1 <= chapter <= 20 and verse >= 1:
                    return f"{chapter}.{verse}"
    except (OSError, UnicodeDecodeError):
        return None
    return None


def json_card_verse(path: Path) -> str | None:
    """Номер вірша JSON-картки: з явного поля `id`, інакше з імені файлу.

    Поле `id` — джерело істини: його звіряє з реєстром `check_editorial_cards.py`
    і воно ж вирішує, до якого вірша картка належить. Ім'я файлу лишається
    запасним варіантом, щоб картка з нестандартним `id` усе одно не зникала
    з перевірки мовчки.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if isinstance(data, dict):
        value = data.get("id")
        if isinstance(value, str):
            m = JSON_ID_RE.fullmatch(value.strip())
            if m:
                return f"{int(m.group(1))}.{int(m.group(2))}"
    return card_verse(path)


def card_kind(entry: str) -> str:
    """Формат картки за шляхом у звіті: `json` або `md`."""
    return "json" if entry.endswith(".json") else "md"


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


def collect_ranges(research: Path = RESEARCH) -> dict[tuple[int, int], list[str]]:
    """Картки-діапазони, згруповані за однаковим охопленням.

    Два файли з тим самим діапазоном — це теж дублювання роботи (так
    сталося з 1.6–1.10). Воно не валить збірку, але має бути видним.
    """
    spans: dict[tuple[int, int], list[str]] = {}
    if not research.is_dir():
        return spans
    for path in sorted(research.rglob("*.md")):
        span = range_span(path)
        if span is None:
            continue
        spans.setdefault(span, []).append(label(path))
    return spans


def collect(research: Path = RESEARCH, cards: Path = CARDS) -> dict[str, list[str]]:
    """Картки за номером вірша: markdown у `research/` і JSON у `editorial/cards/`."""
    by_verse: dict[str, list[str]] = {}
    if research.is_dir():
        for path in sorted(research.rglob("*.md")):
            if is_range_card(path):
                continue
            verse = card_verse(path)
            if verse is None:
                continue
            by_verse.setdefault(verse, []).append(label(path))
    if cards.is_dir():
        for path in sorted(cards.glob("*.json")):
            verse = json_card_verse(path)
            if verse is None:
                print(f"ДУБЛІ-ПРОПУЩЕНО {label(path)}: немає читабельного поля id",
                      file=sys.stderr)
                continue
            by_verse.setdefault(verse, []).append(label(path))
    return by_verse


def verse_key(verse: str) -> tuple[int, int]:
    """Ключ сортування номерів віршів: 2.9 перед 2.10, а не навпаки."""
    chapter, number = verse.split(".")
    return int(chapter), int(number)


def split_duplicates(
    by_verse: dict[str, list[str]],
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Розділити збіги на дублі (той самий формат) і перетини форматів.

    Дубль — два файли одного формату на один вірш: це справжнє дублювання
    роботи, воно валить `--strict`. Перетин — картка й примітка в різних
    форматах: це привід для людського рішення, а не автоматичний збій.
    """
    duplicates: dict[str, list[str]] = {}
    overlaps: dict[str, list[str]] = {}
    for verse, files in by_verse.items():
        if len(files) < 2:
            continue
        kinds: dict[str, int] = {}
        for entry in files:
            kinds[card_kind(entry)] = kinds.get(card_kind(entry), 0) + 1
        if any(count > 1 for count in kinds.values()):
            duplicates[verse] = files
        else:
            overlaps[verse] = files
    return duplicates, overlaps


def count_kinds(by_verse: dict[str, list[str]]) -> tuple[int, int]:
    """Скільки карток кожного формату взято в перевірку."""
    markdown = sum(1 for files in by_verse.values() for entry in files
                   if card_kind(entry) == "md")
    return markdown, sum(len(files) for files in by_verse.values()) - markdown


def run(research: Path = RESEARCH, cards: Path = CARDS, strict: bool = False) -> int:
    by_verse = collect(research, cards)
    duplicates, overlaps = split_duplicates(by_verse)
    markdown, json_cards = count_kinds(by_verse)

    range_dups = {k: v for k, v in collect_ranges(research).items() if len(v) > 1}
    for (start, end), files in sorted(range_dups.items()):
        print(f"ДУБЛІ-ДІАПАЗОН {start // 1000}.{start % 1000}–{end // 1000}.{end % 1000}: {len(files)} картки")
        for f in files:
            print(f"    {f}")
        print("    це дублювання роботи, але не збій: консолідація — окремим PR")

    for verse in sorted(overlaps, key=verse_key):
        files = overlaps[verse]
        print(f"ДУБЛІ-ПЕРЕТИН вірш {verse}: картка і примітка в різних форматах")
        for f in files:
            print(f"    {f}")
        print("    не збій: у research/ лежить текстова примітка, а не друга картка;"
              " рішення — окремим PR")

    if not duplicates:
        print(f"ДУБЛІ-OK карток={len(by_verse)} (md={markdown}, json={json_cards}) дублів немає")
        return 0

    strict_failures = 0
    for verse in sorted(duplicates, key=verse_key):
        files = duplicates[verse]
        known = verse in KNOWN_DUPLICATES
        label_text = "ДУБЛІ-ВІДОМО" if known else "ДУБЛІ-ЗНАЙДЕНО"
        print(f"{label_text} вірш {verse}: {len(files)} картки")
        for f in files:
            print(f"    {f}")
        if known:
            print(f"    причина: {KNOWN_DUPLICATES[verse]}")
        elif strict:
            strict_failures += 1

    if strict and strict_failures:
        print(
            f"ДУБЛІ-ЗБІЙ нових дублів: {strict_failures}. "
            "Консолідувати в один файл або внести до KNOWN_DUPLICATES з поясненням.",
            file=sys.stderr,
        )
        return 1

    print(f"ДУБЛІ-ПІДСУМОК карток={len(by_verse)} (md={markdown}, json={json_cards}) "
          f"дублів={len(duplicates)} перетинів={len(overlaps)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--strict", action="store_true",
                    help="збій на кожному дублі, крім KNOWN_DUPLICATES")
    args = ap.parse_args()
    return run(strict=args.strict)


if __name__ == "__main__":
    sys.exit(main())
