#!/usr/bin/env python3
"""Синтетичні тести перевірки прогалин у нумерації карток."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from scripts.check_verse_gaps import find_gaps, present_ids
from scripts import check_verse_gaps as gaps


class GapTests(unittest.TestCase):
    def test_gap_between_present_verses(self) -> None:
        self.assertEqual(find_gaps({"1.1", "1.3"}, {"1.1", "1.2", "1.3"}), {1: ["1.2"]})

    def test_untouched_chapter_is_not_a_gap(self) -> None:
        self.assertEqual(find_gaps({"2.1"}, {"1.1", "2.1", "2.2"}), {2: ["2.2"]})

    def test_gaps_sorted_by_number_not_lexically(self) -> None:
        gaps = find_gaps({"1.10"}, {f"1.{n}" for n in range(1, 11)})
        self.assertEqual(gaps[1], [f"1.{n}" for n in range(1, 10)])

    def test_no_gaps_when_continuous(self) -> None:
        self.assertEqual(find_gaps({"1.1", "1.2"}, {"1.1", "1.2"}), {})

    def test_empty_folder_is_not_a_gap(self) -> None:
        self.assertEqual(find_gaps(set(), {"1.1"}), {})

    def test_present_ids_skips_broken_and_foreign(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "1.1.json").write_text(json.dumps({"id": "1.1"}), encoding="utf-8")
            (root / "broken.json").write_text("{", encoding="utf-8")
            (root / "other.json").write_text(json.dumps({"id": "не вірш"}), encoding="utf-8")
            self.assertEqual(present_ids(root), {"1.1"})


    def invoke(self, folder: Path, strict: bool = False) -> tuple[int, str, str]:
        """Запуск справжнього main із синтетичним реєстром без мережі."""
        stdout, stderr = io.StringIO(), io.StringIO()
        arguments = ["check_verse_gaps.py", "--cards", str(folder)]
        if strict:
            arguments.append("--strict")
        with (
            mock.patch.object(sys, "argv", arguments),
            mock.patch.object(gaps, "valid_verse_ids", return_value={"1.1", "1.2"}),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            code = gaps.main()
        return code, stdout.getvalue(), stderr.getvalue()

    def test_missing_directory_is_error_in_both_modes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            absent = Path(tmp) / "missing"
            for strict in (False, True):
                with self.subTest(strict=strict):
                    code, out, err = self.invoke(absent, strict)
                    self.assertEqual(code, 2, out + err)
                    self.assertIn("каталог карток", err)
                    self.assertNotIn("прогалин немає", out.casefold())

    def test_regular_file_is_not_a_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "cards"
            file.write_text("це не каталог", encoding="utf-8")
            code, out, err = self.invoke(file)
            self.assertEqual(code, 2, out + err)
            self.assertIn("не є каталогом", err)

    def test_directory_symlink_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            real = root / "real"
            real.mkdir()
            alias = root / "alias"
            try:
                alias.symlink_to(real, target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"платформа не підтримує символьні посилання: {exc}")
            code, out, err = self.invoke(alias)
            self.assertEqual(code, 2, out + err)
            self.assertIn("символічним посиланням", err)

    def test_dangling_directory_symlink_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            alias = root / "alias"
            try:
                alias.symlink_to(root / "missing", target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"платформа не підтримує символьні посилання: {exc}")
            code, out, err = self.invoke(alias)
            self.assertEqual(code, 2, out + err)
            self.assertIn("символічним посиланням", err)

    def test_existing_empty_directory_is_valid_not_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for strict in (False, True):
                with self.subTest(strict=strict):
                    code, out, err = self.invoke(Path(tmp), strict)
                    self.assertEqual(code, 0, err)
                    self.assertIn("ПРОГАЛИНИ: немає", out)

    def test_present_cards_preserve_report_and_strict_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "1.1.json").write_text('{"id":"1.1"}', encoding="utf-8")
            code, out, err = self.invoke(folder)
            self.assertEqual(code, 0, err)
            self.assertIn("1.2", out)
            code, out, err = self.invoke(folder, strict=True)
            self.assertEqual(code, 1, out + err)
            self.assertIn("--strict", err)



if __name__ == "__main__":
    unittest.main()
