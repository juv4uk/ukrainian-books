#!/usr/bin/env python3
"""Позитивні й негативні офлайнові тести наукових сторінок."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.check_scholarly_pages import check_page

VERSE = """# Пробне наукове видання

## 6.1

**Деванагарі.** आकाशम् । जगत् ॥

**IAST.** ākāśam | jagat ||

**Українська транслітерація.** акашам | джаґат ||

**Переклад.** Простір і світ.

**Коментар.** Це пробна редакторська інтерпретація, а не джерельна цитата.

*Українська паралель (наша асоціація).* [Наркіс Сковороди](https://example.org/dzherelo) — лише порівняння, не вплив.

**Ілюстрація.** ![Схема глечика](ilustratsii/hn.svg) — власний задум.
"""
SVG = '<svg xmlns="http://www.w3.org/2000/svg"><circle cx="10" cy="10" r="5"/></svg>'


class ScientificPageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "ilustratsii").mkdir()
        (self.root / "ilustratsii/hn.svg").write_text(SVG, encoding="utf-8")
        self.page = self.root / "rozdil-6-naukove.md"
        self.page.write_text(VERSE, encoding="utf-8")

    def run_check(self, content: str) -> list[str]:
        self.page.write_text(content, encoding="utf-8")
        return check_page(self.page, self.root)

    def test_good_page(self) -> None:
        self.assertEqual(self.run_check(VERSE), [])

    def test_no_verse_headings(self) -> None:
        self.assertTrue(self.run_check("# Лише заголовок"))

    def test_missing_field(self) -> None:
        self.assertTrue(any("шари" in e for e in self.run_check(VERSE.replace("**Коментар.**", "**Примітка.**"))))

    def test_duplicate_field(self) -> None:
        altered = VERSE.replace("**Коментар.**", "**IAST.** roman\n\n**Коментар.**")
        self.assertTrue(any("шари" in e for e in self.run_check(altered)))

    def test_wrong_field_order(self) -> None:
        altered = VERSE.replace("**IAST.** ākāśam | jagat ||", "**Українська транслітерація.** акашам | джаґат ||", 1).replace("**Українська транслітерація.** акашам | джаґат ||\n\n**Українська транслітерація.** акашам | джаґат ||", "**Українська транслітерація.** акашам | джаґат ||\n\n**IAST.** ākāśam | jagat ||")
        self.assertTrue(any("шари" in e for e in self.run_check(altered)))

    def test_empty_translation(self) -> None:
        self.assertTrue(any("порожній" in e for e in self.run_check(VERSE.replace("**Переклад.** Простір і світ.", "**Переклад.**"))))

    def test_latin_in_ukrainian_transliteration(self) -> None:
        self.assertTrue(any("латинських" in e for e in self.run_check(VERSE.replace("акашам", "ākāśam"))))

    def test_unmarked_parallel(self) -> None:
        self.assertTrue(any("авторською" in e for e in self.run_check(VERSE.replace("наша асоціація", "науковий доказ"))))

    def test_parallel_without_source_link(self) -> None:
        self.assertTrue(any("посиланням" in e for e in self.run_check(VERSE.replace("[Наркіс Сковороди](https://example.org/dzherelo)", "Наркіс Сковороди"))))

    def test_missing_svg(self) -> None:
        self.assertTrue(any("локальним SVG" in e for e in self.run_check(VERSE.replace("hn.svg", "znik.svg"))))

    def test_svg_with_remote_image(self) -> None:
        (self.root / "ilustratsii/hn.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"><image href="https://example.org/photo.png"/></svg>', encoding="utf-8")
        self.assertTrue(any("заборонений елемент" in e for e in self.run_check(VERSE)))

    def test_svg_with_script(self) -> None:
        (self.root / "ilustratsii/hn.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"><script>evil()</script></svg>', encoding="utf-8")
        self.assertTrue(any("заборонений елемент" in e for e in self.run_check(VERSE)))

    def test_path_traversal(self) -> None:
        self.assertTrue(any("за межі" in e for e in self.run_check(VERSE.replace("ilustratsii/hn.svg", "../../outside.svg"))))

    def test_illustration_optional(self) -> None:
        line = "**Ілюстрація.** ![Схема глечика](ilustratsii/hn.svg) — власний задум."
        self.assertEqual(self.run_check(VERSE.replace(line, "")), [])

    def test_duplicate_verse_number(self) -> None:
        self.assertTrue(any("повторений" in e for e in self.run_check(VERSE + VERSE.split("## 6.1", 1)[1].join(["## 6.1", ""]))))


if __name__ == "__main__":
    unittest.main()
