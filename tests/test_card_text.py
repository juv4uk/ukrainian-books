#!/usr/bin/env python3
"""Синтетичні тести перевірки цілісності текстових полів картки."""

from __future__ import annotations

import unittest

from scripts.check_card_text import check_card

CLEAN = {
    "id": "1.1",
    "sanskrit": "kathaṃ jñānamavāpnoti||1|1||",
    "iast": "kathaṃ jñānam avāpnoti ||",
    "literal_meaning": "«Як знання здобувається?»",
    "ukrainian_translation": "Як здобувається знання?",
    "commentary": "Питання, а не твердження.",
}


class CardTextTests(unittest.TestCase):
    def test_clean_card_passes(self) -> None:
        self.assertEqual(check_card(CLEAN, "1.1.json"), [])

    def test_sanskrit_without_danda_is_flagged(self) -> None:
        broken = dict(CLEAN, sanskrit="kathaṃ jñānamavāpnoti kathaṃ muktirbhavi")
        self.assertTrue(any("sanskrit" in p for p in check_card(broken, "1.1.json")))

    def test_translation_without_sentence_end_is_flagged(self) -> None:
        broken = dict(CLEAN, ukrainian_translation="Як здобувається")
        self.assertTrue(any("ukrainian_translation" in p for p in check_card(broken, "1.1.json")))

    def test_commentary_cut_mid_word_is_flagged(self) -> None:
        broken = dict(CLEAN, commentary="Питання, а не тверд")
        self.assertTrue(any("commentary" in p for p in check_card(broken, "1.1.json")))

    def test_cyrillic_in_iast_is_flagged(self) -> None:
        broken = dict(CLEAN, iast="kathaṃ jñānam авāpnoti ||")
        self.assertTrue(any("iast" in p for p in check_card(broken, "1.1.json")))

    def test_translation_without_cyrillic_is_flagged(self) -> None:
        broken = dict(CLEAN, ukrainian_translation="katham jnanam?")
        self.assertTrue(any("кирилиці" in p for p in check_card(broken, "1.1.json")))

    def test_non_dict_does_not_crash(self) -> None:
        self.assertTrue(check_card([], "x.json"))


if __name__ == "__main__":
    unittest.main()
