#!/usr/bin/env python3
"""Тести генератора власних схем до віршів."""

from __future__ import annotations

import re
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_verse_schemas import (  # noqa: E402
    HONEST,
    MOTIFS,
    OUT,
    SPECS,
    check,
    filename,
    index_document,
    render,
)


class SpecsTests(unittest.TestCase):
    def test_chapter_one_is_complete(self) -> None:
        """Глава 1 — 20 віршів, і кожен має схему."""
        verses = sorted(SPECS, key=lambda v: int(v.split(".")[1]))
        self.assertEqual(verses, [f"1.{n}" for n in range(1, 21)])

    def test_every_motif_exists(self) -> None:
        for verse, (motif, _params, _alt) in SPECS.items():
            with self.subTest(verse=verse):
                self.assertIn(motif, MOTIFS)

    def test_motif_library_is_parametric(self) -> None:
        """Один мотив обслуговує кілька віршів — інакше це не машина."""
        used: dict[str, int] = {}
        for motif, _p, _a in SPECS.values():
            used[motif] = used.get(motif, 0) + 1
        self.assertGreaterEqual(len(MOTIFS), 8)
        self.assertTrue(any(count > 1 for count in used.values()), used)

    def test_alt_text_present(self) -> None:
        for verse, (_m, _p, alt) in SPECS.items():
            with self.subTest(verse=verse):
                self.assertTrue(alt.strip())


class RenderTests(unittest.TestCase):
    def test_every_schema_is_valid_xml(self) -> None:
        for verse in SPECS:
            with self.subTest(verse=verse):
                ET.fromstring(render(verse))

    def test_honest_label_is_inside_every_schema(self) -> None:
        """Схему не можна видати за історичну ілюстрацію, навіть вирвавши її."""
        for verse in SPECS:
            with self.subTest(verse=verse):
                self.assertIn(HONEST, render(verse))

    def test_no_external_references(self) -> None:
        """Жодних чужих зображень, шрифтів чи посилань."""
        for verse in SPECS:
            svg = render(verse)
            with self.subTest(verse=verse):
                self.assertNotIn("http", svg.replace("http://www.w3.org/2000/svg", ""))
                self.assertNotIn("<image", svg)
                self.assertNotIn("xlink:href", svg)
                self.assertNotIn("@font-face", svg)

    def test_no_photographic_or_embedded_assets(self) -> None:
        for verse in SPECS:
            svg = render(verse)
            with self.subTest(verse=verse):
                self.assertNotIn("base64", svg)

    def test_has_title_and_description(self) -> None:
        for verse in SPECS:
            svg = render(verse)
            with self.subTest(verse=verse):
                self.assertIn("<title", svg)
                self.assertIn("<desc", svg)
                self.assertIn('role="img"', svg)

    def test_deterministic(self) -> None:
        for verse in SPECS:
            with self.subTest(verse=verse):
                self.assertEqual(render(verse), render(verse))

    def test_filename_is_ascii_and_verse_numbered(self) -> None:
        for verse in SPECS:
            name = filename(verse)
            with self.subTest(verse=verse):
                self.assertRegex(name, r"^[0-9a-z\-]+\.svg$")
                self.assertTrue(name.startswith(verse.replace(".", "-")))


class FilesTests(unittest.TestCase):
    def test_generated_files_are_up_to_date(self) -> None:
        self.assertEqual(check(), [], "запустіть python3 scripts/build_verse_schemas.py")

    def test_svg_files_exist_on_disk(self) -> None:
        for verse in SPECS:
            with self.subTest(verse=verse):
                self.assertTrue((OUT / filename(verse)).is_file())

    def test_index_document_exists(self) -> None:
        path = OUT / "README.md"
        self.assertTrue(path.is_file())
        self.assertEqual(path.read_text(encoding="utf-8"), index_document())

    def test_index_says_they_are_not_historical(self) -> None:
        text = index_document()
        self.assertIn("не є історичними ілюстраціями", text)
        self.assertIn("Схема наша", text)

    def test_index_lists_every_schema(self) -> None:
        text = index_document()
        for verse in SPECS:
            with self.subTest(verse=verse):
                self.assertIn(filename(verse), text)

    def test_no_orphan_svg_for_chapter_one(self) -> None:
        """Серед схем глави 1 не має лежати файл, якого немає в SPECS.

        Схеми інших глав (напр. `6-1-hlechyk.svg` з пілота) тут не
        перевіряються: вони зроблені іншим заходом і мають свої записи,
        коли дійде черга до тієї глави.
        """
        expected = {filename(v) for v in SPECS}
        actual = {p.name for p in OUT.iterdir()
                  if p.suffix == ".svg" and p.name.startswith("1-")}
        self.assertEqual(actual - expected, set())
        self.assertEqual(expected - actual, set())


if __name__ == "__main__":
    unittest.main()
