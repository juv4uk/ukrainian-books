#!/usr/bin/env python3
"""Контракт між генератором глав і структурною перевіркою наукових сторінок.

Дефект, який цей файл закриває: `scripts/check_scholarly_pages.py` шукав
маркер `**Коментар.**`, а `scripts/build_format_v2_chapter.py` писав
`**Науковий коментар.**` (і не писав шару `**IAST.**`). Через це перевірка
падала на кожній книжковій сторінці, її не внесли до обовʼязкових, і вона
нічого не перевіряла.

Тому тут перевіряються три речі, і кожна мусить падати, якщо боки розійдуться:

1. канон (`docs/FORMAT_V2.md`) = перелік шарів, який вимагає перевірка;
2. генератор на реальних даних дає саме цей перелік шарів і саме в цьому
   порядку;
3. усі 20 книжкових сторінок проходять перевірку без жодної діагностики.

Тест не доводить наукової якості сторінок — лише те, що перевірка справді
перевіряє те, що генерується.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import build_format_v2_chapter as builder  # noqa: E402
from scripts import check_scholarly_pages as checker  # noqa: E402

BOOK = ROOT / "books" / "ashtavakra-gita"
SPEC = ROOT / "docs" / "FORMAT_V2.md"
TABLE_HEADING = "## Блок одного вірша"


def spec_layers() -> list[str]:
    """Шари з таблиці канону `docs/FORMAT_V2.md`, у тому ж порядку."""
    text = SPEC.read_text(encoding="utf-8")
    start = text.index(TABLE_HEADING)
    rows: list[str] = []
    for line in text[start:].splitlines()[1:]:
        if line.startswith("## "):
            break
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not cells or set(cells[0]) <= {"-", ":", " "} or cells[0] == "Шар":
            continue
        rows.append(cells[0])
    return rows


def emitted_labels(markdown: str) -> list[str]:
    """Підписи шарів, які реально є в тексті, — очима тієї ж перевірки."""
    return [match.group(1) for match in checker.FIELD.finditer(markdown)]


class CanonTests(unittest.TestCase):
    def test_spec_table_lists_the_layers(self) -> None:
        layers = spec_layers()
        self.assertIn("IAST", layers)
        self.assertIn("Коментар", layers)

    def test_checker_requires_exactly_the_spec_layers(self) -> None:
        """Якщо канон зміниться, а перевірка ні — тут буде розбіжність."""
        layers = spec_layers()
        self.assertEqual(
            layers[:len(checker.LABELS)], checker.LABELS,
            "перевірка й docs/FORMAT_V2.md розійшлися в переліку шарів")
        self.assertEqual(
            [label for label in layers if label in checker.LABELS], checker.LABELS,
            "порядок шарів у перевірці не збігається з каноном")

    def test_checker_field_pattern_matches_every_required_label(self) -> None:
        """Кожен обовʼязковий шар мусить ловитися регуляркою перевірки."""
        for label in checker.LABELS:
            with self.subTest(label=label):
                self.assertIsNotNone(
                    checker.FIELD.search(f"**{label}.** пробний текст\n"),
                    f"перевірка не бачить шару «{label}»")


class GeneratorMatchesCheckerTests(unittest.TestCase):
    """Генератор мусить писати саме ті маркери, які шукає перевірка."""

    def test_generated_verses_use_the_required_markers(self) -> None:
        parallels = builder.load_parallels()
        scenes = builder.load_scenes()
        for chapter in builder.chapters_with_cards():
            extra = builder.load_extra(chapter)
            for card in builder.load_cards(chapter):
                data = builder.layers(card, extra, parallels, scenes)
                markdown = builder.render_markdown_verse(data)
                with self.subTest(verse=data["id"]):
                    self.assertEqual(emitted_labels(markdown), checker.LABELS)

    def test_commentary_marker_is_not_the_orphan_one(self) -> None:
        """Саме ця розбіжність і зробила перевірку мертвою."""
        extra = builder.load_extra(1)
        data = builder.layers(builder.load_cards(1)[0], extra,
                              builder.load_parallels(), builder.load_scenes())
        markdown = builder.render_markdown_verse(data)
        self.assertIn("**Коментар.**", markdown)
        self.assertNotIn("**Науковий коментар.**", markdown)


class RealPagesTests(unittest.TestCase):
    """Перевірка мусить проходити на всіх 20 книжкових главах."""

    def setUp(self) -> None:
        self.pages = sorted(BOOK.glob("rozdil-*-naukove.md"))

    def test_twenty_pages_exist(self) -> None:
        self.assertEqual(len(self.pages), 20)

    def test_every_page_passes_the_check(self) -> None:
        for page in self.pages:
            with self.subTest(page=page.name):
                self.assertEqual(checker.check_page(page, ROOT), [])

    def test_every_page_has_all_five_required_layers(self) -> None:
        for page in self.pages:
            text = page.read_text(encoding="utf-8")
            headings = list(checker.VERSE.finditer(text))
            self.assertTrue(headings, page.name)
            for index, heading in enumerate(headings):
                end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
                chunk = text[heading.end():end]
                with self.subTest(page=page.name, verse=heading.group(1)):
                    self.assertEqual(emitted_labels(chunk), checker.LABELS)


class DriftIsCaughtTests(unittest.TestCase):
    """Довести, що тести вище не порожні: штучна розбіжність мусить ловитися."""

    def setUp(self) -> None:
        self.page = BOOK / "rozdil-1-naukove.md"
        self.original = self.page.read_text(encoding="utf-8")

    def labels_after(self, markdown: str) -> list[str]:
        first = checker.VERSE.search(markdown)
        self.assertIsNotNone(first)
        return emitted_labels(markdown[first.end():])

    def test_old_commentary_marker_breaks_the_check(self) -> None:
        drifted = self.original.replace("**Коментар.**", "**Науковий коментар.**")
        self.assertNotEqual(drifted, self.original)
        self.assertNotEqual(self.labels_after(drifted), checker.LABELS)

    def test_missing_iast_layer_breaks_the_check(self) -> None:
        drifted = re.sub(r"^\*\*IAST\.\*\*.*\n\n", "", self.original, flags=re.MULTILINE)
        self.assertNotEqual(drifted, self.original)
        self.assertNotEqual(self.labels_after(drifted), checker.LABELS)


if __name__ == "__main__":
    unittest.main()
