#!/usr/bin/env python3
"""Тести механічної транслітерації IAST → деванагарі.

Покриття: кожен клас символів (приголосні, приголосні з придихом, носові,
голосні, матрі, вірама, анусвара, вісарґа, аваґраха, данда), падіння на
невідомому символі, оборотність на реальних віршах.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.iast_to_devanagari import (  # noqa: E402
    to_devanagari,
    to_iast,
)
from scripts.iast_tokens import UnsupportedSymbol, tokenize  # noqa: E402

CARDS = ROOT / "editorial" / "cards"


class DevanagariTests(unittest.TestCase):
    """Базові відповідності, успадковані з попередньої версії скрипта."""

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


class ConsonantClassesTests(unittest.TestCase):
    """Кожен приголосний клас — окремо, щоб таблиця не «з'їхала» тихо."""

    def test_velars(self) -> None:
        self.assertEqual(to_devanagari("ka kha ga gha ṅa"), "क ख ग घ ङ")

    def test_palatals(self) -> None:
        self.assertEqual(to_devanagari("ca cha ja jha ña"), "च छ ज झ ञ")

    def test_retroflexes(self) -> None:
        self.assertEqual(to_devanagari("ṭa ṭha ḍa ḍha ṇa"), "ट ठ ड ढ ण")

    def test_dentals(self) -> None:
        self.assertEqual(to_devanagari("ta tha da dha na"), "त थ द ध न")

    def test_labials(self) -> None:
        self.assertEqual(to_devanagari("pa pha ba bha ma"), "प फ ब भ म")

    def test_semivowels_and_sibilants(self) -> None:
        self.assertEqual(to_devanagari("ya ra la va"), "य र ल व")
        self.assertEqual(to_devanagari("śa ṣa sa ha"), "श ष स ह")

    def test_longest_match_wins(self) -> None:
        """``th`` — це थ, а не त + ह."""
        self.assertEqual(to_devanagari("tha"), "थ")
        self.assertEqual(to_devanagari("t" + "ha"), "थ")


class VowelClassesTests(unittest.TestCase):
    """Голосні: самостійна форма і матрі — дві різні таблиці."""

    def test_independent_vowels(self) -> None:
        self.assertEqual(
            to_devanagari("a ā i ī u ū ṛ ṝ ḷ ḹ e ai o au"),
            "अ आ इ ई उ ऊ ऋ ॠ ऌ ॡ ए ऐ ओ औ",
        )

    def test_matras(self) -> None:
        self.assertEqual(
            to_devanagari("kā ki kī ku kū kṛ kṝ kḷ ke kai ko kau"),
            "का कि की कु कू कृ कॄ कॢ के कै को कौ",
        )

    def test_diphthongs_are_single_tokens(self) -> None:
        self.assertEqual(to_devanagari("kai"), "कै")
        self.assertEqual(to_devanagari("kau"), "कौ")
        self.assertEqual(to_devanagari("ko"), "को")

    def test_virama_between_consonants(self) -> None:
        self.assertEqual(to_devanagari("kṣṇa"), "क्ष्ण")


class MarkAndPunctuationTests(unittest.TestCase):
    def test_anusvara_variants(self) -> None:
        self.assertEqual(to_devanagari("saṃ"), "सं")
        self.assertEqual(to_devanagari("saṁ"), "सं")

    def test_visarga(self) -> None:
        self.assertEqual(to_devanagari("rāmaḥ"), "रामः")

    def test_danda_single_and_double(self) -> None:
        # Кінцевий приголосний без голосного закривається вірамою: ब → ब्.
        self.assertEqual(to_devanagari("a | b ||"), "अ । ब् ॥")

    def test_avagraha_variants(self) -> None:
        for mark in ("'", "ʼ", "’"):
            with self.subTest(mark=mark):
                self.assertEqual(to_devanagari(f"so {mark}ham"), "सो ऽहम्")

    def test_punctuation_and_digits_pass_through(self) -> None:
        self.assertEqual(to_devanagari("a, b. 1"), "अ, ब्. 1")

    def test_whitespace_is_preserved(self) -> None:
        self.assertEqual(to_devanagari("a  b\nc"), "अ  ब्\nच्")


class FailLoudTests(unittest.TestCase):
    """Головна вимога: на невідомому символі — падіння, а не пропуск."""

    def test_unknown_latin_letter_raises(self) -> None:
        for char in ("q", "w", "x", "f", "z"):
            with self.subTest(char=char):
                with self.assertRaises(UnsupportedSymbol):
                    to_devanagari(f"ka{char}a")

    def test_unknown_diacritic_raises(self) -> None:
        with self.assertRaises(UnsupportedSymbol):
            to_devanagari("kë")

    def test_error_names_position_and_context(self) -> None:
        with self.assertRaises(UnsupportedSymbol) as caught:
            to_devanagari("katham q jñānam", where="картці 9.9")
        message = str(caught.exception)
        self.assertIn("q", message)
        self.assertIn("U+0071", message)
        self.assertIn("позиції 7", message)
        self.assertIn("картці 9.9", message)
        self.assertIn("контекст", message)

    def test_tokenize_raises_not_skips(self) -> None:
        with self.assertRaises(UnsupportedSymbol):
            tokenize("kath@m")

    def test_empty_string(self) -> None:
        self.assertEqual(to_devanagari(""), "")


class RoundTripTests(unittest.TestCase):
    """Оборотність на реальних віршах — доказ, що таблиця не «залипла»."""

    def test_roundtrip_on_all_cards(self) -> None:
        failures = []
        checked = 0
        for path in sorted(CARDS.glob("*.json")):
            card = json.loads(path.read_text(encoding="utf-8"))
            iast = card.get("iast")
            if not iast:
                continue
            checked += 1
            back = to_iast(to_devanagari(iast))
            if back != iast:
                failures.append((card["id"], iast, back))
        self.assertGreater(checked, 200, "очікується понад 200 карток з IAST")
        self.assertEqual(failures, [], f"оборотність зламана: {failures[:3]}")

    def test_known_verse_1_1(self) -> None:
        iast = ("kathaṃ jñānam avāpnoti kathaṃ muktir bhaviṣyati | "
                "vairāgyaṃ ca kathaṃ prāptam etad brūhi mama prabho ||")
        self.assertEqual(
            to_devanagari(iast),
            "कथं ज्ञानम् अवाप्नोति कथं मुक्तिर् भविष्यति । "
            "वैराग्यं च कथं प्राप्तम् एतद् ब्रूहि मम प्रभो ॥",
        )

    def test_no_silent_drop_on_every_card(self) -> None:
        """Довжина входу й виходу не може розійтися «на око»."""
        for path in sorted(CARDS.glob("*.json")):
            card = json.loads(path.read_text(encoding="utf-8"))
            iast = card.get("iast")
            if not iast:
                continue
            with self.subTest(card=card["id"]):
                deva = to_devanagari(iast)
                self.assertTrue(deva)
                # Кожен пробіл входу має пробіл у виході: жодного слова не зникло.
                self.assertEqual(deva.count(" "), iast.count(" "))


if __name__ == "__main__":
    unittest.main()
