"""Негативні й позитивні випробування точних відомих дублікатів."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/check_duplicate_cards.py"
spec = importlib.util.spec_from_file_location("check_duplicate_cards", SCRIPT)
if spec is None or spec.loader is None:
    raise RuntimeError("Не вдалось завантажити перевіряльник дублікатів")
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)

FIVE = [
    "research/ashtavakra/verse-1-5-ashrama-varna.md",
    "research/ashtavakra/verse-1-5-varna-ashrama.md",
]
SIX = [
    "research/ashtavakra/notes-1-6-to-1-10.md",
    "research/ashtavakra/verses-1-6-to-1-10.md",
]


class KnownDuplicateTests(unittest.TestCase):
    def test_exact_five(self):
        self.assertTrue(checker.is_known_duplicate("1.5", FIVE))

    def test_exact_six(self):
        self.assertTrue(checker.is_known_duplicate("1.6", SIX))

    def test_order_does_not_matter(self):
        self.assertTrue(checker.is_known_duplicate("1.6", list(reversed(SIX))))

    def test_third_file_must_fail(self):
        self.assertFalse(checker.is_known_duplicate("1.6", SIX + ["research/other.md"]))

    def test_changed_path_must_fail(self):
        self.assertFalse(checker.is_known_duplicate("1.6", [SIX[0], "research/renamed.md"]))

    def test_third_five_must_fail(self):
        self.assertFalse(checker.is_known_duplicate("1.5", FIVE + ["research/other.md"]))

    def test_unknown_verse_must_fail(self):
        self.assertFalse(checker.is_known_duplicate("1.7", SIX))

    def test_repeated_same_path_must_fail(self):
        self.assertFalse(checker.is_known_duplicate("1.6", SIX + [SIX[0]]))


class StrictCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.research = self.root / "research"
        self.research.mkdir()
        self.patches = [
            mock.patch.object(checker, "ROOT", self.root),
            mock.patch.object(checker, "RESEARCH", self.research),
        ]
        for patch in self.patches:
            patch.start()
            self.addCleanup(patch.stop)

    def add(self, path, number):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"# Аштавакра-ґіта {number}: синтетичний тест\n", encoding="utf-8")

    def cli(self):
        output, errors = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "argv", ["checker", "--strict"]), \
                contextlib.redirect_stdout(output), \
                contextlib.redirect_stderr(errors):
            result = checker.main()
        return result, output.getvalue(), errors.getvalue()

    def test_exact_pair_reported_and_accepted(self):
        for f in SIX:
            self.add(f, "1.6")
        code, stdout, stderr = self.cli()
        self.assertEqual(code, 0, stderr)
        self.assertIn("ДУБЛІ-ВІДОМО вірш 1.6", stdout)
        self.assertIn("консолідація", stdout)

    def test_third_card_rejected(self):
        for f in SIX:
            self.add(f, "1.6")
        self.add("research/ashtavakra/another-1-6.md", "1.6")
        code, stdout, stderr = self.cli()
        self.assertEqual(code, 1)
        self.assertIn("ДУБЛІ-ЗНАЙДЕНО вірш 1.6", stdout)
        self.assertIn("ДУБЛІ-ЗБІЙ", stderr)

    def test_unlisted_pair_rejected(self):
        self.add("research/a.md", "1.8")
        self.add("research/b.md", "1.8")
        code, stdout, stderr = self.cli()
        self.assertEqual(code, 1)
        self.assertIn("ДУБЛІ-ЗБІЙ", stderr)


if __name__ == "__main__":
    unittest.main()
