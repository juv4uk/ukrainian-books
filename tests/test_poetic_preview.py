"""Відтворювані негативні докази ізольованої поетичної редакції."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.render_poetic_preview import check_complete, expected_ids, load, render, validate

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = json.loads((ROOT / "editorial/poetic_samples/1.2.json").read_text(encoding="utf-8"))
SCRIPT = ROOT / "scripts/render_poetic_preview.py"


class PoeticPreviewTests(unittest.TestCase):
    def test_sample_has_own_poem_and_explicit_draft(self):
        self.assertEqual(validate(SAMPLE, {"1.2"}), [])
        self.assertEqual(SAMPLE["status"], "чернетка")
        self.assertFalse(SAMPLE["rights"]["verified"])
        self.assertIsNone(SAMPLE["review"]["reviewer"])
        self.assertEqual(len(SAMPLE["lines"]), 4)
        self.assertIn("вдоволеність", " ".join(SAMPLE["lines"]))

    def test_poem_is_distinct_from_academic_book(self):
        preview = render([SAMPLE])
        self.assertIn("ОКРЕМОГО поетичного перекладу", preview)
        self.assertIn("НЕ ДЛЯ ПУБЛІКАЦІЇ", preview)
        self.assertIn("Як прагнеш звільнення", preview)
        self.assertNotIn("मुक्तिमिच्छसि", preview)

    def test_incomplete_298_verse_corpus_fails_closed(self):
        expected = {"1.1", "1.2", "1.3"}
        problems = check_complete([SAMPLE], expected)
        self.assertTrue(any("відсутні" in error for error in problems))
        self.assertTrue(any("чернетка" in error for error in problems))

    def test_unreviewed_cannot_claim_final(self):
        bad = copy.deepcopy(SAMPLE)
        bad["status"] = "рецензовано"
        self.assertTrue(any("прав" in e for e in validate(bad, {"1.2"})))
        self.assertTrue(any("рецензента" in e for e in validate(bad, {"1.2"})))

    def test_self_review_rejected_even_if_other_flags_green(self):
        bad = copy.deepcopy(SAMPLE)
        bad.update(status="рецензовано", translator="Одна особа")
        bad["rights"]["verified"] = True
        bad["review"] = {"reviewer": "одна особа", "review_url": "https://example.org/review"}
        self.assertTrue(any("Саморецензування" in e for e in validate(bad, {"1.2"})))

    def test_bad_urls_and_missing_lines_rejected(self):
        bad = copy.deepcopy(SAMPLE)
        bad["source"]["sarit"] = "file:///etc/passwd"
        bad["lines"] = ["один"]
        errors = validate(bad, {"1.2"})
        self.assertTrue(any("HTTPS" in e for e in errors))
        self.assertTrue(any("2–12" in e for e in errors))

    def test_wrong_file_name_and_duplicate_identity_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "1.2.json").write_text(json.dumps(SAMPLE, ensure_ascii=False), encoding="utf-8")
            (root / "alias.json").write_text(json.dumps(SAMPLE, ensure_ascii=False), encoding="utf-8")
            _, errors = load(root, {"1.2"})
            self.assertTrue(any("Повторений ID" in e for e in errors))
            self.assertTrue(any("Ім'я JSON" in e for e in errors))

    def test_symlink_is_not_traversed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "1.2.json").symlink_to(Path(temp) / "missing.json")
            poems, errors = load(root, {"1.2"})
            self.assertEqual(poems, [])
            self.assertTrue(any("символьні" in e for e in errors))

    def test_numeric_verse_sorting_is_stable(self):
        later = copy.deepcopy(SAMPLE)
        later["id"] = "1.10"
        text = render([later, SAMPLE])
        self.assertLess(text.index("### 1.2"), text.index("### 1.10"))

    def test_registry_is_actual_20_chapters_298_positions(self):
        expected = expected_ids(ROOT / "research/ashtavakra/registry-20-chapters.csv")
        self.assertEqual(len(expected), 298)
        self.assertIn("20.14", expected)
        self.assertIn("18.100", expected)

    def test_cli_preview_success_but_strict_rejected(self):
        preview = subprocess.run(
            [sys.executable, str(SCRIPT)], cwd=ROOT, text=True, capture_output=True
        )
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertIn("НЕ ДЛЯ ПУБЛІКАЦІЇ", preview.stdout)
        strict = subprocess.run(
            [sys.executable, str(SCRIPT), "--check-complete"],
            cwd=ROOT, text=True, capture_output=True
        )
        self.assertEqual(strict.returncode, 1)
        self.assertIn("Неповне охоплення", strict.stderr)

    def test_cli_refuses_direct_books_output(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "books" / "fake.md"
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--output", str(target)],
                cwd=ROOT, text=True, capture_output=True
            )
            self.assertEqual(result.returncode, 2)
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
