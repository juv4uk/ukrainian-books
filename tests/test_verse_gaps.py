#!/usr/bin/env python3
"""Синтетичні тести перевірки прогалин у нумерації карток."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.check_verse_gaps import find_gaps, present_ids, untouched_chapters


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

    def test_untouched_chapters_are_named_with_verse_counts(self) -> None:
        expected = {"1.1", "1.2", "2.1", "3.1", "3.2", "3.3"}
        self.assertEqual(untouched_chapters({"1.1"}, expected), {2: 1, 3: 3})

    def test_untouched_chapters_empty_when_every_chapter_started(self) -> None:
        expected = {"1.1", "1.2", "2.1"}
        self.assertEqual(untouched_chapters({"1.1", "2.1"}, expected), {})

    def test_present_ids_skips_broken_and_foreign(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "1.1.json").write_text(json.dumps({"id": "1.1"}), encoding="utf-8")
            (root / "broken.json").write_text("{", encoding="utf-8")
            (root / "other.json").write_text(json.dumps({"id": "не вірш"}), encoding="utf-8")
            self.assertEqual(present_ids(root), {"1.1"})


if __name__ == "__main__":
    unittest.main()
