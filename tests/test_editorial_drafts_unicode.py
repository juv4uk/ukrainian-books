"""ІНЖ-12: синтетичні позитивні й негативні тести редакторських чернеток."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.check_editorial_drafts_unicode import audit


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_editorial_drafts_unicode.py"


class EditorialDraftsUnicodeTests(unittest.TestCase):
    def test_missing_directory_reported_without_false_publication_claim(self):
        with tempfile.TemporaryDirectory() as temp:
            result = audit(Path(temp))
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["scanned_files"], 0)
            self.assertIn("не підтверджує готовності", result["warning"])

    def test_clean_ukrainian_and_iast_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / "editorial" / "drafts"
            directory.mkdir(parents=True)
            (directory / "rozdil-15.md").write_text(
                "# Аштавакра-ґіта\n\nТи — свідомість. ātman, sākṣin.\n",
                encoding="utf-8",
            )
            result = audit(Path(temp))
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["scanned_files"], 1)

    def test_nested_draft_detects_latin_substitution(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / "editorial" / "drafts" / "glava"
            directory.mkdir(parents=True)
            (directory / "chapter.md").write_text("Українське свiтло", encoding="utf-8")
            result = audit(Path(temp))
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["scanned_files"], 1)
            self.assertEqual(result["errors"][0]["path"], "editorial/drafts/glava/chapter.md")
            self.assertEqual(result["errors"][0]["codepoint"], "U+0069")

    def test_invalid_utf8_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / "editorial" / "drafts"
            directory.mkdir(parents=True)
            (directory / "text.md").write_bytes(b"\xff")
            result = audit(Path(temp))
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["errors"][0]["codepoint"], "UTF-8")

    def test_invisible_control_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / "editorial" / "drafts"
            directory.mkdir(parents=True)
            (directory / "text.md").write_text("текст\u2060далі", encoding="utf-8")
            result = audit(Path(temp))
            self.assertEqual(result["status"], "failed")
            self.assertIn("U+2060", [entry["codepoint"] for entry in result["errors"]])

    def test_symlink_to_file_rejected_without_following(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / "editorial" / "drafts"
            directory.mkdir(parents=True)
            (directory / "broken.md").symlink_to(directory / "nonexistent.md")
            result = audit(Path(temp))
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["scanned_files"], 0)
            self.assertIn("символьне посилання", result["errors"][0]["reason"])

    def test_symlink_to_directory_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / "editorial"
            directory.mkdir()
            (directory / "drafts").symlink_to(Path(temp) / "elsewhere", target_is_directory=True)
            result = audit(Path(temp))
            self.assertEqual(result["status"], "failed")

    def test_non_markdown_not_scanned(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / "editorial" / "drafts"
            directory.mkdir(parents=True)
            (directory / "binary.pdf").write_bytes(b"\xff")
            result = audit(Path(temp))
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["scanned_files"], 0)

    def test_cli_fails_and_writes_json_report(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            directory = root / "editorial" / "drafts"
            directory.mkdir(parents=True)
            (directory / "draft.md").write_text("Зіпсований \ufffd текст", encoding="utf-8")
            report = root / "reports" / "drafts.json"
            completed = subprocess.run(
                [sys.executable, str(SCRIPT), "--root", str(root), "--report", str(report)],
                cwd=SCRIPT.parents[1], capture_output=True, text=True, check=False,
            )
            self.assertEqual(completed.returncode, 1)
            self.assertTrue(report.is_file())
            data = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(data["status"], "failed")
            self.assertEqual(data["errors"][0]["codepoint"], "U+FFFD")


if __name__ == "__main__":
    unittest.main()
