#!/usr/bin/env python3
"""Синтетичні регресії ГЕН-01: построкові дані не змінюють канон."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import build_format_v2_chapter as builder  # noqa: E402


class PostrokoviTests(unittest.TestCase):
    def setUp(self) -> None:
        self.card = {
            "id": "5.1",
            "iast": "na te saṅgo 'sti kenāpi kiṃ śuddhas tyaktum icchasi | "
                    "saṅghātavilayaṃ kurvann evam eva layaṃ vraja ||",
            "ukrainian_translation": (
                "У тебе немає зв'язку ні з чим — то чого ж ти, чистий, хочеш відкинути? "
                "Здійснюючи розчинення скупчення, так само йди до розчинення."
            ),
            "commentary": "Тестова українська примітка.",
        }
        self.alignment = {
            "status": "чернетка",
            "lines": [
                {
                    "iast": "na te saṅgo 'sti kenāpi kiṃ śuddhas tyaktum icchasi",
                    "ukrainian_translation": (
                        "У тебе немає зв'язку ні з чим — то чого ж ти, чистий, хочеш відкинути?"
                    ),
                    "commentary": "Питання про неприв'язаність.",
                },
                {
                    "iast": "saṅghātavilayaṃ kurvann evam eva layaṃ vraja",
                    "ukrainian_translation": (
                        "Здійснюючи розчинення скупчення, так само йди до розчинення."
                    ),
                    "commentary": "Імператив та повторюваний рефрен.",
                },
            ],
        }

    def _get(self, alignment: dict) -> dict:
        return builder.layers(self.card, {"verses": {"5.1": {"postrokovo": alignment}}}, {})

    def test_two_lines_and_both_output_formats(self) -> None:
        record = self._get(self.alignment)
        self.assertEqual(len(record["postrokovo"]["lines"]), 2)
        md = builder.render_markdown_verse(record)
        tex = builder.render_latex_verse(record)
        self.assertIn("### Рядок а", md)
        self.assertIn("### Рядок б", md)
        self.assertIn("механічно з IAST", md)
        self.assertIn("не рецензовано", md)
        self.assertIn(self.card["ukrainian_translation"], md)
        self.assertIn(r"\vsec{5.1}", tex)
        self.assertEqual(tex.count(r"\vdeva{"), 3)  # повний вірш + два рядки
        self.assertEqual(tex.count(r"\viast{"), 3)  # IAST є в обох форматах
        self.assertEqual(tex.count(r"\vperek{"), 3)
        for line in record["postrokovo"]["lines"]:
            self.assertIn(line["translation"], md)
            self.assertIn(line["transliteration"], md)

    def test_missing_alignment_preserves_existing_rendering(self) -> None:
        item = builder.layers(self.card, {"verses": {}}, {})
        self.assertIsNone(item["postrokovo"])
        self.assertNotIn("Построкове зіставлення", builder.render_markdown_verse(item))
        self.assertEqual(builder.render_latex_verse(item).count(r"\vdeva{"), 1)
        self.assertEqual(builder.render_latex_verse(item).count(r"\viast{"), 1)

    def test_wrong_iast_is_rejected(self) -> None:
        bad = copy.deepcopy(self.alignment)
        bad["lines"][0]["iast"] = "na te saṅgo"
        with self.assertRaisesRegex(ValueError, "IAST"):
            self._get(bad)

    def test_translation_must_reconstruct_card(self) -> None:
        bad = copy.deepcopy(self.alignment)
        bad["lines"][1]["ukrainian_translation"] = "Інший текст."
        with self.assertRaisesRegex(ValueError, "не відтворюють"):
            self._get(bad)

    def test_missing_comment_is_rejected(self) -> None:
        bad = copy.deepcopy(self.alignment)
        bad["lines"][0]["commentary"] = ""
        with self.assertRaisesRegex(ValueError, "коментаря"):
            self._get(bad)

    def test_reviewer_claim_cannot_be_manufactured(self) -> None:
        bad = copy.deepcopy(self.alignment)
        bad["status"] = "рецензовано"
        with self.assertRaisesRegex(ValueError, "status=чернетка"):
            self._get(bad)

    def test_no_implicit_pada_split(self) -> None:
        bad = copy.deepcopy(self.alignment)
        bad["lines"].append(copy.deepcopy(bad["lines"][1]))
        with self.assertRaisesRegex(ValueError, "два"):
            self._get(bad)


    def test_four_explicit_padas_group_into_two_printed_lines(self) -> None:
        card = copy.deepcopy(self.card)
        card["id"] = "16.3"
        card["iast"] = (
            "āyāsāt sakalo duḥkhī | nainaṃ jānāti kaścana | "
            "anenaivopadeśena | dhanyaḥ prāpnoti nirvṛtim ||"
        )
        card["ukrainian_translation"] = (
            "Від натуги всі нещасні, і ніхто з них цього не бачить. "
            "Блаженний же досягає вгамування самим лише цим настановленням."
        )
        entry = {
            "postrokovo": {
                "status": "чернетка",
                "lines": [
                    {
                        "iast": "āyāsāt sakalo duḥkhī nainaṃ jānāti kaścana",
                        "ukrainian_translation": "Від натуги всі нещасні, і ніхто з них цього не бачить.",
                        "commentary": "Перша друкована половина, дві пади.",
                    },
                    {
                        "iast": "anenaivopadeśena dhanyaḥ prāpnoti nirvṛtim",
                        "ukrainian_translation": (
                            "Блаженний же досягає вгамування самим лише цим настановленням."
                        ),
                        "commentary": "Друга друкована половина, дві пади.",
                    },
                ],
            }
        }
        result = builder.layers(card, {"verses": {"16.3": entry}}, {})
        rows = result["postrokovo"]["lines"]
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["iast"], entry["postrokovo"]["lines"][0]["iast"])
        self.assertEqual(rows[1]["iast"], entry["postrokovo"]["lines"][1]["iast"])
        self.assertIn("### Рядок а", builder.render_markdown_verse(result))
        self.assertEqual(builder.render_latex_verse(result).count(r"\vdeva{"), 3)
        self.assertEqual(builder.render_latex_verse(result).count(r"\viast{"), 3)

    def test_three_explicit_padas_are_not_silently_grouped(self) -> None:
        card = copy.deepcopy(self.card)
        card["iast"] = "āyāsāt | sakalo duḥkhī | nainaṃ jānāti kaścana ||"
        from scripts.postrokove import prepare_alignment
        with self.assertRaisesRegex(ValueError, "двох"):
            prepare_alignment(card, {"postrokovo": self.alignment})

    def test_four_padas_with_mismatched_printed_halfline_rejected(self) -> None:
        card = copy.deepcopy(self.card)
        card["iast"] = "āyāsāt | sakalo duḥkhī | nainaṃ jānāti | kaścana ||"
        from scripts.postrokove import prepare_alignment
        with self.assertRaisesRegex(ValueError, "IAST"):
            prepare_alignment(card, {"postrokovo": self.alignment})


if __name__ == "__main__":
    unittest.main()
