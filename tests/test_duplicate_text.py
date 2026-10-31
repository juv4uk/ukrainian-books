#!/usr/bin/env python3
"""Синтетичні тести пошуку однакового санскритського читання."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.check_duplicate_text import find_duplicates, normalize


class DuplicateTextTests(unittest.TestCase):
    def test_same_text_different_verses_is_reported(self) -> None:
        cards = [("1.1", "kathaṃ jñānam avāpnoti ||1|1||"),
                 ("1.2", "kathaṃ jñānam avāpnoti ||1|2||")]
        self.assertEqual(len(find_duplicates(cards)), 1)

    def test_marker_and_spacing_ignored(self) -> None:
        cards = [("1.1", "kathaṃ jñānam||1|1||"),
                 ("1.2", "kathaṃ   jñānam ||1|2||")]
        self.assertEqual(len(find_duplicates(cards)), 1)

    def test_different_text_not_reported(self) -> None:
        cards = [("1.1", "kathaṃ jñānam||1|1||"),
                 ("1.2", "kathaṃ muktirbhaviṣyati||1|2||")]
        self.assertEqual(find_duplicates(cards), {})

    def test_empty_text_ignored(self) -> None:
        cards = [("1.1", ""), ("1.2", "  "), ("1.3", "||1|3||")]
        self.assertEqual(find_duplicates(cards), {})

    def test_normalize_removes_danda_and_marker(self) -> None:
        self.assertEqual(normalize("a b||1|1|| |"), "ab")

    def test_group_lists_all_ids_sorted(self) -> None:
        cards = [("2.2", "x"), ("1.1", "x"), ("1.10", "x")]
        self.assertEqual(list(find_duplicates(cards).values())[0], ["1.1", "1.10", "2.2"])


class DuplicateTextCliTests(unittest.TestCase):
    """Незалежний офлайновий запуск CLI тільки на синтетичних картках."""

    def run_cli(self, folder: Path, *, strict: bool = False) -> subprocess.CompletedProcess[str]:
        command = [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "scripts/check_duplicate_text.py"),
            "--cards", str(folder),
        ]
        if strict:
            command.append("--strict")
        return subprocess.run(command, capture_output=True, text=True, check=False)

    def write_card(self, folder: Path, name: str, verse: str, sanskrit: str) -> None:
        (folder / name).write_text(
            json.dumps({"id": verse, "sanskrit": sanskrit}, ensure_ascii=False),
            encoding="utf-8",
        )

    def test_missing_directory_never_reports_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_cli(Path(tmp) / "зниклі-картки")
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("каталог карток", result.stderr)

    def test_empty_directory_never_reports_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_cli(Path(tmp), strict=True)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("немає JSON", result.stderr)

    def test_non_directory_never_reports_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "картки"
            file.write_text("не каталог", encoding="utf-8")
            result = self.run_cli(file)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)

    def test_single_valid_card_still_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.write_card(folder, "1.1.json", "1.1", "kathaṃ jñānam ||1|1||")
            result = self.run_cli(folder, strict=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("повторів немає", result.stdout)

    def test_duplicate_report_and_strict_behavior_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.write_card(folder, "1.1.json", "1.1", "kathaṃ jñānam ||1|1||")
            self.write_card(folder, "1.2.json", "1.2", "kathaṃ jñānam ||1|2||")
            report = self.run_cli(folder)
            strict = self.run_cli(folder, strict=True)
            self.assertEqual(report.returncode, 0, report.stdout + report.stderr)
            self.assertIn("однакове читання: 1.1, 1.2", report.stdout)
            self.assertEqual(strict.returncode, 1, strict.stdout + strict.stderr)


if __name__ == "__main__":
    unittest.main()
