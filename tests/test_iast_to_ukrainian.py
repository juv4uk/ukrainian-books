#!/usr/bin/env python3
"""Тести української практичної транслітерації IAST.

Кожне правило з `docs/TRANSLITERATSIIA.md` має тут свій тест: якщо документ
і код розійдуться, тест упаде й покаже, де саме.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.iast_to_ukrainian import KEEP, to_ukrainian  # noqa: E402
from scripts.iast_tokens import UnsupportedSymbol  # noqa: E402

CARDS = ROOT / "editorial" / "cards"
# Дозволений вихід: українська абетка, типографський апостроф і ті
# розділові знаки, які транслітерація переносить без змін.
UKRAINIAN = (frozenset("абвгґдеєжзиіїйклмнопрстуфхцчшщьюя’'") | KEEP
             | frozenset("|"))


class ConsonantTests(unittest.TestCase):
    def test_owner_mandated_mappings(self) -> None:
        """Правила власника: ś/ṣ→ш, ṭ/ḍ/ṇ→т/д/н, c→ч, ch→чч, j→дж,
        ñ→нь, ṅ→н."""
        cases = {
            "śa": "ша", "ṣa": "ша", "ṭa": "та", "ḍa": "да", "ṇa": "на",
            "ca": "ча", "cha": "чча", "ja": "джа", "ña": "ня", "ṅa": "на",
        }
        for iast, expected in cases.items():
            with self.subTest(iast=iast):
                self.assertEqual(to_ukrainian(iast), expected)

    def test_g_and_h_do_not_collide(self) -> None:
        """g → ґ, h → х: інакше graha і hara писалися б однаково."""
        self.assertEqual(to_ukrainian("graha"), "ґраха")
        self.assertEqual(to_ukrainian("hara"), "хара")

    def test_aspirates_after_voiceless_take_kh(self) -> None:
        self.assertEqual(to_ukrainian("khaga"), "кхаґа")
        self.assertEqual(to_ukrainian("phala"), "пхала")
        self.assertEqual(to_ukrainian("thala"), "тхала")

    def test_aspirates_after_voiced_take_h(self) -> None:
        self.assertEqual(to_ukrainian("ghaṭa"), "ґгата")
        self.assertEqual(to_ukrainian("dha"), "дга")
        self.assertEqual(to_ukrainian("bha"), "бга")
        self.assertEqual(to_ukrainian("jha"), "джга")

    def test_established_ukrainian_forms(self) -> None:
        self.assertEqual(to_ukrainian("brahma"), "брахма")
        self.assertEqual(to_ukrainian("dharma"), "дгарма")
        self.assertEqual(to_ukrainian("buddha"), "буддга")
        self.assertEqual(to_ukrainian("kathā"), "катха")
        self.assertEqual(to_ukrainian("bhagavadgītā"), "бгаґавадґіта")

    def test_triple_letters_collapse_to_double(self) -> None:
        """``icchasi`` — це c + ch; трьох «ч» поспіль українська не пише."""
        self.assertEqual(to_ukrainian("icchasi"), "іччасі")
        self.assertEqual(to_ukrainian("buddha"), "буддга")
        self.assertEqual(to_ukrainian("tattva"), "таттва")


class VowelTests(unittest.TestCase):
    def test_long_vowels_lose_length(self) -> None:
        self.assertEqual(to_ukrainian("ā ī ū"), "а і у")
        self.assertEqual(to_ukrainian("a i u"), "а і у")

    def test_diphthongs(self) -> None:
        self.assertEqual(to_ukrainian("vairāgya"), "вайраґя")
        self.assertEqual(to_ukrainian("kau"), "кау")

    def test_syllabic_r_open_syllable(self) -> None:
        self.assertEqual(to_ukrainian("kṛta"), "кріта")
        self.assertEqual(to_ukrainian("ṛṣi"), "ріші")
        self.assertEqual(to_ukrainian("kṛṣṇa"), "крішна")

    def test_syllabic_r_closed_syllable(self) -> None:
        self.assertEqual(to_ukrainian("pitṛ"), "пітри")
        self.assertEqual(to_ukrainian("mātṛ"), "матри")

    def test_syllabic_does_not_look_past_word_boundary(self) -> None:
        """``pitṛ putraḥ`` — огляд не має переходити на наступне слово."""
        self.assertEqual(to_ukrainian("pitṛ putraḥ"), "пітри путрах")


class UkrainianOrthographyTests(unittest.TestCase):
    def test_soft_ny_replaces_soft_sign(self) -> None:
        """«нь» + голосний = «ня», а не «нья»."""
        self.assertEqual(to_ukrainian("jñāna"), "джняна")
        self.assertEqual(to_ukrainian("jñeya"), "джнєя")

    def test_yotated_y(self) -> None:
        self.assertEqual(to_ukrainian("yathā"), "ятха")
        self.assertEqual(to_ukrainian("yoga"), "йоґа")
        self.assertEqual(to_ukrainian("satya"), "сатя")

    def test_apostrophe_after_labials_and_r(self) -> None:
        self.assertEqual(to_ukrainian("rūpya"), "руп'я")
        self.assertEqual(to_ukrainian("kāvya"), "кав'я")


class MarkAndPunctuationTests(unittest.TestCase):
    def test_anusvara_and_visarga(self) -> None:
        self.assertEqual(to_ukrainian("ahaṃ"), "ахам")
        self.assertEqual(to_ukrainian("rāmaḥ"), "рамах")

    def test_avagraha_becomes_typographic_apostrophe(self) -> None:
        self.assertEqual(to_ukrainian("ananto 'haṃ"), "ананто ’хам")

    def test_dandas_and_spaces_are_preserved(self) -> None:
        source = "iti jñānaṃ | na tyāgo ||"
        result = to_ukrainian(source)
        self.assertEqual(result, "іті джнянам | на тяґо ||")

    def test_output_is_ukrainian_cyrillic_only(self) -> None:
        """У виході не має лишитися латиниці чи IAST-діакритики."""
        result = to_ukrainian("kathaṃ jñānam avāpnoti | muktir bhaviṣyati ||")
        stray = {ch for ch in result if ch not in UKRAINIAN}
        self.assertEqual(stray, set(), f"зайві символи у виході: {stray}")


class FailLoudTests(unittest.TestCase):
    def test_unknown_symbol_raises(self) -> None:
        with self.assertRaises(UnsupportedSymbol):
            to_ukrainian("kaq")

    def test_error_mentions_card(self) -> None:
        with self.assertRaises(UnsupportedSymbol) as caught:
            to_ukrainian("kaq", where="картці 3.4")
        self.assertIn("картці 3.4", str(caught.exception))


class CorpusTests(unittest.TestCase):
    def test_every_card_converts_without_stray_latin(self) -> None:
        converted = 0
        for path in sorted(CARDS.glob("*.json")):
            card = json.loads(path.read_text(encoding="utf-8"))
            iast = card.get("iast")
            if not iast:
                continue
            converted += 1
            with self.subTest(card=card["id"]):
                result = to_ukrainian(iast)
                stray = {ch for ch in result if ch not in UKRAINIAN}
                self.assertEqual(stray, set(), f"{card['id']}: {stray}")
                self.assertEqual(result.count("|"), iast.count("|"))
        self.assertGreater(converted, 200)

    def test_verse_1_1(self) -> None:
        iast = ("kathaṃ jñānam avāpnoti kathaṃ muktir bhaviṣyati | "
                "vairāgyaṃ ca kathaṃ prāptam etad brūhi mama prabho ||")
        self.assertEqual(
            to_ukrainian(iast),
            "катхам джнянам авапноті катхам муктір бгавішяті | "
            "вайраґям ча катхам праптам етад брухі мама прабго ||",
        )


if __name__ == "__main__":
    unittest.main()
