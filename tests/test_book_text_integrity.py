"""Негативні/позитивні синтетичні тести РЕД-05 без сторонніх залежностей."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.check_book_text_integrity import audit, scan_text


class UnicodeBookIntegrityTests(unittest.TestCase):
    def test_ukrainian_iast_and_devanagari_valid(self):
        text = "Пізнай Атман: ātman, sākṣin, śānti, āśrama; देवनागरी.\nУкраї\u0301нський наголос.\n"
        self.assertEqual(scan_text(text), [])

    def test_replacement_character_rejected(self):
        errors = scan_text("Український св\uFFFDдок")
        self.assertEqual([e["codepoint"] for e in errors], ["U+FFFD"])

    def test_hebrew_mark_attached_to_cyrillic_rejected(self):
        self.assertIn("U+0596", [e["codepoint"] for e in scan_text("т\u0596лі")])

    def test_arabic_mark_attached_to_latin_rejected(self):
        self.assertIn("U+0654", [e["codepoint"] for e in scan_text("a\u0654")])

    def test_genuine_hebrew_and_arabic_text_not_automatically_rejected(self):
        self.assertEqual(scan_text("שָׁלוֹם، عَرَبِيّ"), [])

    def test_bidi_controls_rejected(self):
        self.assertIn("U+202E", [e["codepoint"] for e in scan_text("текст\u202E")])

    def test_invisible_word_joiner_rejected(self):
        self.assertIn("U+2060", [e["codepoint"] for e in scan_text("сло\u2060во")])

    def test_nul_character_rejected(self):
        self.assertIn("U+0000", [e["codepoint"] for e in scan_text("текст\u0000")])

    def test_tab_and_crlf_allowed(self):
        self.assertEqual(scan_text("Текст\tпримітка\r\nНовий рядок"), [])

    def test_ordinary_spelling_errors_are_out_of_scope(self):
        self.assertEqual(scan_text("двадчять Чк"), [])

    def test_empty_repository_is_valid_but_explicit(self):
        with tempfile.TemporaryDirectory() as temp:
            result = audit(Path(temp))
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["scanned_files"], 0)

    def test_nested_book_and_passport_scanned(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "books" / "ashtavakra" / "chapters"
            target.mkdir(parents=True)
            (target / "first.tex").write_text("Глава 1\uFFFD", encoding="utf-8")
            (root / "books" / "ashtavakra" / "PROVENANCE.md").write_text("т\u0596лі", encoding="utf-8")
            output = audit(root)
            self.assertEqual(output["scanned_files"], 2)
            self.assertEqual(output["status"], "failed")
            self.assertEqual({e["codepoint"] for e in output["errors"]}, {"U+FFFD", "U+0596"})

    def test_invalid_utf8_bytes_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "books" / "work"
            path.mkdir(parents=True)
            (path / "main.tex").write_bytes(b"\xff not utf-8")
            output = audit(Path(temp))
            self.assertEqual(output["scanned_files"], 1)
            self.assertEqual(output["errors"][0]["codepoint"], "UTF-8")

    def test_non_book_and_binary_files_ignored(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "docs").mkdir()
            (root / "docs" / "bad.md").write_text("\uFFFD", encoding="utf-8")
            folder = root / "books" / "work"
            folder.mkdir(parents=True)
            (folder / "output.pdf").write_bytes(b"\x00\xff")
            (folder / "main.tex").write_text("Текст чистий", encoding="utf-8")
            output = audit(root)
            self.assertEqual(output["status"], "ok")
            self.assertEqual(output["scanned_files"], 1)

    def test_maximum_findings_limit(self):
        self.assertEqual(len(scan_text("\uFFFD" * 70)), 25)


if __name__ == "__main__":
    unittest.main()
