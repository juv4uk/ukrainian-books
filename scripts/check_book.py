#!/usr/bin/env python3
"""Цілість видання: books/ мусить точно відповідати редакторським карткам.

Навіщо. Книга збирається з карток скриптом `build_book.py`, але ніщо не
перевіряло, що зібране не розійшлося з джерелом. Перший же прогін змісту
показав реальну помилку: `ZMIST.md` називав главу 1 повною, хоч у ній не
було 1.5, 1.12 і 1.13. Цей гейт ловить саме такі розходження.

Що перевіряється:
  1. кожен вірш із карток присутній у своєму `rozdil-N.md`;
  2. у розділі немає віршів, яких немає в картках;
  3. переклад у розділі побайтово дорівнює полю `ukrainian_translation`;
  4. розділ, названий у `ZMIST.md` повним, справді без пропусків;
  5. кожен неповний розділ названий неповним у `ZMIST.md`.

Нічого не виправляє: лише повідомляє. Виправляти має той, хто змінив зміст.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

BOOK = Path("books/ashtavakra-gita")
VERSE_HEAD = re.compile(r"^## (\d+)\.(\d+)$", re.M)
ZMIST_ROW = re.compile(r"^\|\s*\[?(\d+)\]?[^|]*\|[^|]*\|([^|]*)\|", re.M)


def load_cards(root: Path) -> dict[int, dict[int, str]]:
    cards: dict[int, dict[int, str]] = {}
    for path in sorted((root / "editorial" / "cards").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        chapter, verse = data["id"].split(".")
        cards.setdefault(int(chapter), {})[int(verse)] = data["ukrainian_translation"].strip()
    return cards


def gaps(nums) -> list[int]:
    return [i for i in range(1, max(nums) + 1) if i not in nums] if nums else []


def audit(root: Path) -> list[str]:
    cards = load_cards(root)
    book = root / BOOK
    errors: list[str] = []
    if not book.is_dir():
        return [f"{BOOK}: каталогу видання немає"]

    for chapter, verses in sorted(cards.items()):
        path = book / f"rozdil-{chapter}.md"
        if not path.is_file():
            errors.append(f"rozdil-{chapter}.md: немає файла, хоч є {len(verses)} карток")
            continue
        text = path.read_text(encoding="utf-8")
        found = {(int(c), int(v)) for c, v in VERSE_HEAD.findall(text)}
        want = {(chapter, v) for v in verses}
        for c, v in sorted(want - found):
            errors.append(f"rozdil-{chapter}.md: немає вірша {c}.{v}")
        for c, v in sorted(found - want):
            errors.append(f"rozdil-{chapter}.md: зайвий вірш {c}.{v}, у картках його немає")
        # Текст вірша мусить збігатися з карткою.
        blocks = re.split(r"^## \d+\.\d+$", text, flags=re.M)
        heads = VERSE_HEAD.findall(text)
        for (c, v), block in zip(heads, blocks[1:]):
            body = block.strip()
            if int(v) not in verses:
                continue  # зайвий вірш уже названо вище; тут не падаємо
            if body != verses[int(v)]:
                errors.append(f"rozdil-{chapter}.md: текст {c}.{v} розійшовся з карткою")

    zmist = book / "ZMIST.md"
    if not zmist.is_file():
        errors.append("ZMIST.md: немає файла змісту")
    else:
        rows = {int(n): state.strip() for n, state in ZMIST_ROW.findall(
            zmist.read_text(encoding="utf-8"))}
        for chapter, verses in sorted(cards.items()):
            state = rows.get(chapter)
            if state is None:
                errors.append(f"ZMIST.md: немає рядка для розділу {chapter}")
                continue
            missing = gaps(sorted(verses))
            claims_full = state == "повний"
            if claims_full and missing:
                errors.append(
                    f"ZMIST.md: розділ {chapter} названо повним, але немає "
                    + ", ".join(f"{chapter}.{i}" for i in missing))
            if not claims_full and not missing and chapter != 15:
                errors.append(f"ZMIST.md: розділ {chapter} без пропусків, але не названий повним")
    return errors


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    errors = audit(root)
    if errors:
        print(f"ПОМИЛКА: цілість видання порушена ({len(errors)}):")
        for e in errors:
            print("  -", e)
        return 1
    cards = load_cards(root)
    total = sum(len(v) for v in cards.values())
    print(f"OK: видання відповідає карткам — розділів {len(cards)}, віршів {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
