#!/usr/bin/env python3
"""Офлайнові негативні й позитивні приклади Markdown-якорів."""

from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote

from scripts.check_markdown_fragments import (
    check_file, check_tree, heading_anchors, main, slug,
)


class MarkdownFragmentsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "docs").mkdir()
        self.source = self.root / "README.md"
        self.target = self.root / "docs" / "український текст.md"

    def write(self, source, target="# Зміст\n"):
        self.source.write_text(source, encoding="utf-8")
        self.target.write_text(target, encoding="utf-8")
        return check_file(self.source, self.root)

    def test_ukrainian_same_file_anchor(self):
        self.assertEqual(
            self.write("# Бібліотека\n## Мета й джерела\n[Далі](#мета-й-джерела)\n"),
            [],
        )

    def test_relative_encoded_path_and_fragment(self):
        anchor = quote("наукова-редакція")
        path = quote("український текст.md")
        self.assertEqual(
            self.write(
                f"[Деталі](docs/{path}#{anchor})\n",
                "## Наукова редакція\n",
            ),
            [],
        )

    def test_missing_anchor_is_reported(self):
        errors = self.write("[Помилка](docs/український%20текст.md#помилка)\n")
        self.assertEqual(len(errors), 1)
        self.assertIn("невідомий Markdown-якір #помилка", errors[0])
        self.assertIn("README.md:1:", errors[0])

    def test_repeated_headings_get_suffix(self):
        self.assertEqual(
            self.write(
                "[Третій](docs/український%20текст.md#розділ-1)\n",
                "## Розділ\n## Розділ\n",
            ),
            [],
        )
        self.assertEqual(heading_anchors(self.target), {"розділ", "розділ-1"})

    def test_setext_heading(self):
        self.assertEqual(
            self.write("[Розділ](docs/український%20текст.md#примітки)\n",
                       "Примітки\n========\n"),
            [],
        )

    def test_reference_style_link(self):
        self.assertEqual(
            self.write(
                "[Подивитися][ЗМІСТ]\n\n"
                "[зміст]: <docs/український%20текст.md#джерела>\n",
                "# Джерела\n",
            ),
            [],
        )

    def test_undefined_reference_is_for_another_validator(self):
        self.assertEqual(self.write("[Текст][невідомо]\n"), [])

    def test_fenced_code_does_not_create_anchor_or_link(self):
        fence = chr(96) * 3
        errors = self.write(
            f"{fence}md\n[Хиба](#відсутній)\n{fence}\n"
            "[Перевірити](#заголовок-із-коду)\n"
            f"{fence}md\n# Заголовок із коду\n{fence}\n"
        )
        self.assertEqual(len(errors), 1)

    def test_inline_code_link_is_ignored(self):
        tick = chr(96)
        self.assertEqual(self.write(f"{tick}[Хиба](#ні){tick}\n"), [])

    def test_external_links_are_not_checked(self):
        self.assertEqual(
            self.write("[GRETIL](https://example.org/a.md#нескінченний)\n"
                       "[Лист](mailto:test@example.org)\n"),
            [],
        )

    def test_missing_file_and_nonmarkdown_target_are_out_of_scope(self):
        self.assertEqual(
            self.write("[Немає](docs/no.md#невідомий)\n"
                       "[Зображення](img.png#невідомий)\n"),
            [],
        )

    def test_heading_markup_and_punctuation(self):
        self.assertEqual(slug("**Атман**: досвід (Я)"), "атман-досвід-я")
        self.assertEqual(slug("Назва проєкту! ###"), "назва-проєкту")

    def test_tree_result(self):
        self.write("[А](docs/український%20текст.md#немає)\n")
        count, errors = check_tree(self.root)
        self.assertEqual(count, 2)
        self.assertEqual(len(errors), 1)

    def test_default_mode_is_observational_but_strict_fails(self):
        self.write("[А](#немає)\n")
        stream = io.StringIO()
        with patch.object(sys, "argv", ["audit", "--root", str(self.root)]), (
            contextlib.redirect_stdout(stream)
        ):
            self.assertEqual(main(), 0)
        self.assertIn("спостережний", stream.getvalue())
        with patch.object(sys, "argv", ["audit", "--root", str(self.root),
                                        "--strict"]), (
            contextlib.redirect_stdout(io.StringIO())
        ):
            self.assertEqual(main(), 1)


if __name__ == "__main__":
    unittest.main()
