#!/usr/bin/env python3
"""Регресії початкового y у власній українській читацькій передачі IAST.

Тестуємо внутрішню узгодженість чинного генератора, а не нормативну
філологічну правильність усієї української транскрипції санскриту.
"""

from __future__ import annotations

import unittest

from scripts.iast_to_ukrainska import transliterate


class PochatkoveY(unittest.TestCase):
    def test_yatha_at_start(self) -> None:
        self.assertEqual(transliterate("yathā"), "ятха")

    def test_yad_at_start(self) -> None:
        self.assertEqual(transliterate("yad"), "яд")

    def test_yatra_at_start(self) -> None:
        self.assertEqual(transliterate("yatra"), "ятра")

    def test_after_space(self) -> None:
        self.assertEqual(transliterate("yathā yad"), "ятха яд")

    def test_after_verse_pause(self) -> None:
        self.assertEqual(transliterate("eva | yathā"), "ева | ятха")

    def test_initial_yo(self) -> None:
        self.assertEqual(transliterate("yo"), "йо")

    def test_initial_yu(self) -> None:
        self.assertEqual(transliterate("yu"), "ю")

    def test_initial_yi(self) -> None:
        self.assertEqual(transliterate("yi"), "ї")

    def test_standalone_y_not_soft_sign(self) -> None:
        self.assertEqual(transliterate("y"), "й")

    def test_after_apostrophe(self) -> None:
        self.assertEqual(transliterate("'yathā"), "’ятха")

    def test_consonant_cluster_is_unchanged(self) -> None:
        self.assertEqual(transliterate("tya"), "тья")

    def test_between_vowels_is_unchanged(self) -> None:
        self.assertEqual(transliterate("layam"), "лаям")

    def test_chapter_two_witness_is_no_longer_broken(self) -> None:
        result = transliterate("yathā prakāśayāmy eko deham enaṃ tathā jagat")
        self.assertTrue(result.startswith("ятха "), result)
        self.assertNotIn("ьятха", result)

    def test_no_initial_soft_sign_after_whitespace(self) -> None:
        result = transliterate("yathā yad | yatra")
        self.assertTrue(all(not token.startswith("ь") for token in result.split()), result)


if __name__ == "__main__":
    unittest.main()
