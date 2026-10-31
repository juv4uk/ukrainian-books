#!/usr/bin/env python3
"""Офлайнові регресії аудиту построковості без мережі та записів."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import audit_postrokovosti as audit  # noqa: E402

OLD = """## 1.1

**Деванагарі.** प्रथमः । द्वितीयः ॥

**Українська транслітерація.** перший | другий ||

**Переклад.** Перший, другий.

**Науковий коментар.** Наш коментар.
"""
GOOD = """## 1.1

### Рядок а
**Деванагарі.** प्रथमः ।
**IAST.** prathamaḥ |
**Українська транслітерація.** пратхамах |
**Переклад.** Перший.

### Рядок б
**Деванагарі.** द्वितीयः ॥
**IAST.** dvitīyaḥ ||
**Українська транслітерація.** двітіях ||
**Переклад.** Другий.

**Науковий коментар.** Наш коментар.
"""


class VerseTests(unittest.TestCase):
    def test_old_verse_layers_are_not_line_alignment(self):
        row = audit.audit_text(OLD)[0]
        self.assertEqual(row["стан"], "пошарово_за_віршем")
        self.assertEqual(row["очікувано_санскритських_рядків"], 2)
        self.assertEqual(row["наявно_позначених_рядків"], 0)

    def test_existing_book_comment_label_is_accepted(self):
        """Чинна книга використовує **Коментар.**, а не лише майбутню назву."""
        existing = OLD.replace("**Науковий коментар.**", "**Коментар.**")
        row = audit.audit_text(existing)[0]
        self.assertFalse(row["немає_коментаря"])
        self.assertEqual(row["стан"], "пошарово_за_віршем")

    def test_line_layout_accepts_existing_comment_label(self):
        """Визначення построковості не має залежати від назви коментаря."""
        existing = GOOD.replace("**Науковий коментар.**", "**Коментар.**")
        row = audit.audit_text(existing)[0]
        self.assertFalse(row["немає_коментаря"])
        self.assertEqual(row["стан"], "построково_за_формою")

    def test_two_complete_half_lines(self):
        row = audit.audit_text(GOOD)[0]
        self.assertEqual(row["стан"], "построково_за_формою")
        self.assertEqual(row["наявно_позначених_рядків"], 2)

    def test_second_line_without_translation_fails(self):
        content = GOOD.replace("**Переклад.** Другий.", "")
        row = audit.audit_text(content)[0]
        self.assertEqual(row["стан"], "неповно_або_неузгоджено")
        self.assertIn("Переклад", row["деталі_рядків"][1]["пропущено"])

    def test_missing_comment_fails(self):
        content = GOOD.replace("**Науковий коментар.** Наш коментар.", "")
        self.assertTrue(audit.audit_text(content)[0]["немає_коментаря"])
        self.assertEqual(audit.audit_text(content)[0]["стан"], "неповно_або_неузгоджено")

    def test_reversed_lines_are_not_accepted(self):
        content = GOOD.replace("Рядок а", "Рядок тимчасово").replace("Рядок б", "Рядок а").replace("Рядок тимчасово", "Рядок б")
        self.assertEqual(audit.audit_text(content)[0]["стан"], "неповно_або_неузгоджено")

    def test_verse_wide_duplicate_layer_cannot_fake_alignment(self):
        content = GOOD.replace("### Рядок а", "**Деванагарі.** Широкий блок.\n### Рядок а")
        self.assertEqual(audit.audit_text(content)[0]["стан"], "неповно_або_неузгоджено")

    def test_no_missing_sources_produces_unknown_count(self):
        self.assertIsNone(audit.count_source_lines({}))

    def test_ignores_non_verse_headings(self):
        content = "## Глава 1\nВступ\n" + OLD + "\n## Поетичний переклад\nОкремий том"
        self.assertEqual(len(audit.audit_text(content)), 1)


class CommandLineTests(unittest.TestCase):
    def test_report_does_not_fail_for_verse_level_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            book = Path(tmp)
            (book / "rozdil-1-naukove.md").write_text(OLD, encoding="utf-8")
            with mock.patch.object(audit, "BOOK", book), contextlib.redirect_stdout(io.StringIO()) as stdout:
                code = audit.main([])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(stdout.getvalue())["построково_за_формою"], 0)

    def test_strict_returns_failure_for_verse_level_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            book = Path(tmp)
            (book / "rozdil-1-naukove.md").write_text(OLD, encoding="utf-8")
            with mock.patch.object(audit, "BOOK", book), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(audit.main(["--strict"]), 1)

    def test_strict_returns_success_for_complete_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            book = Path(tmp)
            (book / "rozdil-1-naukove.md").write_text(GOOD, encoding="utf-8")
            with mock.patch.object(audit, "BOOK", book), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(audit.main(["--strict"]), 0)

    def test_empty_input_fails_clearly(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(audit, "BOOK", Path(tmp)), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(audit.main(["--all"]), 2)


if __name__ == "__main__":
    unittest.main()
