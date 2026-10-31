#!/usr/bin/env python3
"""Тести механічної транслітерації IAST → деванагарі."""

from __future__ import annotations

import unittest

from scripts.iast_to_devanagari import to_devanagari


class DevanagariTests(unittest.TestCase):
    def test_simple_word(self) -> None:
        self.assertEqual(to_devanagari("ātman"), "आत्मन्")

    def test_inherent_a_after_consonant(self) -> None:
        self.assertEqual(to_devanagari("ka"), "क")

    def test_matra_replaces_inherent_a(self) -> None:
        self.assertEqual(to_devanagari("kā"), "का")

    def test_consonant_cluster_uses_virama(self) -> None:
        self.assertEqual(to_devanagari("tmā"), "त्मा")

    def test_anusvara_and_visarga(self) -> None:
        self.assertEqual(to_devanagari("aṃ aḥ"), "अं अः")

    def test_final_consonant_gets_virama(self) -> None:
        self.assertEqual(to_devanagari("rām"), "राम्")

    def test_avagraha_is_kept(self) -> None:
        self.assertEqual(to_devanagari("so 'ham"), "सो ऽहम्")

    def test_verse_line(self) -> None:
        self.assertEqual(
            to_devanagari("kūṭasthaṃ bodham advaitam ātmānaṃ paribhāvaya"),
            "कूटस्थं बोधम् अद्वैतम् आत्मानं परिभावय",
        )


if __name__ == "__main__":
    unittest.main()
