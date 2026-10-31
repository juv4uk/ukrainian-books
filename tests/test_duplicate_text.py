#!/usr/bin/env python3
"""Синтетичні тести пошуку однакового санскритського читання."""

from __future__ import annotations

import unittest

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


if __name__ == "__main__":
    unittest.main()
