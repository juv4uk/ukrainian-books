#!/usr/bin/env python3
"""Незалежні офлайнові тести довідкових посилань на тимчасовому дереві."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.check_reference_links import check_file, check_tree, normalized


class ReferenceLinksTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "docs").mkdir()
        (self.root / "docs" / "файл з пробілом.md").write_text("Зміст\n", encoding="utf-8")
        self.document = self.root / "README.md"

    def check(self, value: str) -> list[str]:
        self.document.write_text(value, encoding="utf-8")
        return check_file(self.document, self.root)

    def test_existing_link_and_ukrainian_label(self):
        self.assertEqual(self.check("[Читати][  НАШ   ФАЙЛ ]\n\n[наш файл]: <docs/файл%20з%20пробілом.md> \"Назва\"\n"), [])

    def test_implicit_reference_label(self):
        self.assertEqual(self.check("[Джерело][]\n[джерело]: docs/файл%20з%20пробілом.md\n"), [])

    def test_image_reference(self):
        self.assertEqual(self.check("![Обкладинка][малюнок]\n[малюнок]: https://example.org/image.png\n"), [])

    def test_missing_definition(self):
        self.assertTrue(any("невизначена" in x for x in self.check("[Джерело][відсутнє]\n")))

    def test_missing_file(self):
        self.assertTrue(any("відсутня локальна ціль" in x for x in self.check("[Джерело][x]\n[x]: docs/немає.md\n")))

    def test_duplicate_labels(self):
        self.assertTrue(any("повторена мітка" in x for x in self.check("[a]: https://example.org\n[A]: https://example.com\n")))

    def test_escape_out_of_root(self):
        self.assertTrue(any("поза репозиторій" in x for x in self.check("[x]: ../../outside.md\n")))

    def test_empty_destination(self):
        self.assertTrue(any("порожня ціль" in x for x in self.check("[x]: \n")))

    def test_fenced_and_inline_code_not_interpreted(self):
        self.assertEqual(self.check(chr(96)*3 + "md\n[я][неіснуюче]\n[я]: missing.md\n" + chr(96)*3 + "\n" + chr(96) + "[тест][нічого]" + chr(96) + "\n"), [])

    def test_tilde_fence(self):
        self.assertEqual(self.check("~~~\n[x][bad]\n~~~\n"), [])

    def test_external_link_and_anchor(self):
        self.assertEqual(self.check("[a][x] [b][y]\n[x]: https://doi.org/10.123/example\n[y]: #примітки\n"), [])

    def test_only_definitions_are_validated(self):
        self.assertEqual(self.check("[x]: docs/файл%20з%20пробілом.md\n"), [])

    def test_footnote_syntax_not_mistaken_for_link(self):
        self.assertEqual(self.check("Речення[^a].\n[^a]: Примітка\n"), [])

    def test_tree_counts_files(self):
        self.document.write_text("[x][no]\n", encoding="utf-8")
        count, errors = check_tree(self.root)
        self.assertEqual(count, 2)
        self.assertEqual(len(errors), 1)

    def test_normalization(self):
        self.assertEqual(normalized("  ЦЕ   Джерело "), "це джерело")


if __name__ == "__main__":
    unittest.main()
