"""Незалежні регресії детермінізму пілотної верстки — без мережі та книжкового корпусу."""

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

from scripts import build_pilot_book as builder  # noqa: E402


class TestDeterministychnaVerstka(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.book = self.root / "book"
        card = {
            "id": "2.1",
            "status": "чернетка",
            "ukrainian_translation": "Власний тестовий переклад.",
            "literal_meaning": "Тестове дослівне значення.",
            "grammar": "Синтетична граматична примітка.",
            "commentary": "Авторський синтетичний коментар.",
            "variants": [],
            "variants_checked": False,
        }
        for patch in (
            mock.patch.object(builder, "BOOK", self.book),
            mock.patch.object(builder, "PILOT_CHAPTERS", (2,)),
            mock.patch.object(builder, "load_cards", return_value=[card]),
            mock.patch.object(builder, "load_glossary", return_value=[]),
        ):
            patch.start()
            self.addCleanup(patch.stop)

    def run_generator(self, *arguments):
        stdout, stderr = io.StringIO(), io.StringIO()
        with (
            mock.patch.object(sys, "argv", ["build_pilot_book.py", *arguments]),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            code = builder.main()
        return code, stdout.getvalue(), stderr.getvalue()

    def test_repeated_generation_is_byte_identical(self):
        code, _, error = self.run_generator()
        self.assertEqual(code, 0, error)
        directory = self.book / "generated"
        names = ("verses.tex", "glossary.tex", "manifest.json")
        before = {name: (directory / name).read_bytes() for name in names}

        code, _, error = self.run_generator()
        self.assertEqual(code, 0, error)
        after = {name: (directory / name).read_bytes() for name in names}
        self.assertEqual(before, after, "Повторне складання змінило власні артефакти")
        self.assertNotIn("outdated_before_write", json.loads(after["manifest.json"]))
        code, _, error = self.run_generator("--check")
        self.assertEqual(code, 0, error)

    def test_check_never_writes_even_when_report_requested(self):
        report = self.root / "reports" / "audit.json"
        code, _, error = self.run_generator("--check", "--report", str(report))
        self.assertNotEqual(code, 0)
        self.assertIn("generated/manifest.json", error)
        self.assertFalse((self.book / "generated").exists())
        self.assertFalse(report.exists(), "Режим --check записав файл звіту")

    def test_check_detects_manifest_drift_without_rewriting(self):
        code, _, error = self.run_generator()
        self.assertEqual(code, 0, error)
        manifest = self.book / "generated" / "manifest.json"
        manifest.write_text('{"status": "пошкоджено"}\n', encoding="utf-8")
        before = manifest.read_bytes()
        report = self.root / "report.json"

        code, _, error = self.run_generator("--check", "--report", str(report))
        self.assertNotEqual(code, 0)
        self.assertIn("generated/manifest.json", error)
        self.assertEqual(manifest.read_bytes(), before)
        self.assertFalse(report.exists())

    def test_real_generation_may_write_requested_report(self):
        report = self.root / "reports" / "audit.json"
        code, _, error = self.run_generator("--report", str(report))
        self.assertEqual(code, 0, error)
        self.assertEqual(
            report.read_bytes(),
            (self.book / "generated" / "manifest.json").read_bytes(),
        )


if __name__ == "__main__":
    unittest.main()
