#!/usr/bin/env python3
"""Тести складальної машини ФОРМАТ-02 і поетичного перекладу."""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import build_format_v2_chapter as builder  # noqa: E402
from scripts.build_verse_schemas import SPECS  # noqa: E402

BOOK = ROOT / "books" / "ashtavakra-gita"
CHAPTER = 1
LAYER_LABELS = ("Деванагарі.", "Українська транслітерація.", "Переклад.",
                "Науковий коментар.", "Ілюстрація.")


class LayerTests(unittest.TestCase):
    """Пʼять шарів мусять бути на кожному з 20 віршів."""

    def setUp(self) -> None:
        self.cards = builder.load_cards(CHAPTER)
        self.extra = builder.load_extra(CHAPTER)
        self.parallels = builder.load_parallels()
        self.data = [builder.layers(c, self.extra, self.parallels)
                     for c in self.cards]

    def test_twenty_verses(self) -> None:
        self.assertEqual(len(self.cards), 20)

    def test_all_five_layers_present_on_every_verse(self) -> None:
        for data in self.data:
            with self.subTest(verse=data["id"]):
                self.assertTrue(data["devanagari"], "немає деванагарі")
                self.assertTrue(data["transliteration"], "немає транслітерації")
                self.assertTrue(data["translation"], "немає перекладу")
                self.assertTrue(data["commentary"], "немає коментаря")
                self.assertTrue(data["parallel"], "немає української паралелі")
                self.assertTrue(data["illustration"], "немає ілюстрації")

    def test_devanagari_is_really_devanagari(self) -> None:
        for data in self.data:
            with self.subTest(verse=data["id"]):
                letters = [c for c in data["devanagari"] if c.isalpha()]
                self.assertTrue(letters)
                self.assertTrue(all(0x0900 <= ord(c) <= 0x097F for c in letters))

    def test_transliteration_has_no_latin(self) -> None:
        for data in self.data:
            with self.subTest(verse=data["id"]):
                self.assertIsNone(
                    re.search(r"[A-Za-z]", data["transliteration"]),
                    data["transliteration"])

    def test_illustration_file_exists(self) -> None:
        for data in self.data:
            with self.subTest(verse=data["id"]):
                path = BOOK / "ilustratsii" / data["illustration"]["file"]
                self.assertTrue(path.is_file(), path)

    def test_every_illustration_is_registered_in_specs(self) -> None:
        for data in self.data:
            with self.subTest(verse=data["id"]):
                self.assertIn(data["id"], SPECS)

    def test_parallel_belongs_to_its_verse(self) -> None:
        for data in self.data:
            with self.subTest(verse=data["id"]):
                self.assertEqual(data["parallel"]["verse"], data["id"])

    def test_machine_works_without_extra_data(self) -> None:
        """Для глави без паралелей і схем машина все одно дає шари 1–4."""
        card = self.cards[0]
        bare = builder.layers(card, {"verses": {}}, {})
        self.assertTrue(bare["devanagari"])
        self.assertTrue(bare["transliteration"])
        self.assertTrue(bare["translation"])
        self.assertTrue(bare["commentary"])
        self.assertIsNone(bare["parallel"])
        self.assertIsNone(bare["illustration"])


class MarkdownTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = (BOOK / "rozdil-1-naukove.md").read_text(encoding="utf-8")

    def test_file_exists_and_is_current(self) -> None:
        self.assertFalse(
            builder.stale(BOOK / "rozdil-1-naukove.md", builder.build_markdown(CHAPTER)),
            "rozdil-1-naukove.md застарів: запустіть "
            "python3 scripts/build_format_v2_chapter.py --chapter 1")

    def test_every_layer_label_appears(self) -> None:
        for label in LAYER_LABELS:
            with self.subTest(label=label):
                self.assertIn(f"**{label}**", self.text)

    def test_twenty_verse_headings(self) -> None:
        headings = re.findall(r"^## (1\.\d+)$", self.text, flags=re.M)
        self.assertEqual(headings, [f"1.{n}" for n in range(1, 21)])

    def test_honest_caption_on_every_illustration(self) -> None:
        count = self.text.count("Схема наша, не історична ілюстрація.")
        self.assertEqual(count, 20)

    def test_says_devanagari_is_mechanical(self) -> None:
        self.assertIn("механічна", self.text)
        self.assertIn("iast_to_devanagari.py", self.text)

    def test_says_parallels_are_ours(self) -> None:
        self.assertIn("наша інтерпретація, не твердження про вплив", self.text)

    def test_unverified_parallels_are_labelled(self) -> None:
        # 4 записи: позначка стоїть і в підписі шару, і в тексті паралелі.
        self.assertEqual(self.text.count("ПОТРЕБУЄ ПЕРЕВІРКИ"), 8)

    def test_no_citation_markers_leak_into_the_file(self) -> None:
        self.assertNotIn("[cite:", self.text)


class LatexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tex = (BOOK / "generated" / "rozdil-1.tex").read_text(encoding="utf-8")

    def test_generated_tex_is_current(self) -> None:
        self.assertFalse(
            builder.stale(BOOK / "generated" / "rozdil-1.tex", builder.build_latex(CHAPTER)),
            "generated/rozdil-1.tex застарів")

    def test_every_verse_has_all_macros(self) -> None:
        for verse in range(1, 21):
            with self.subTest(verse=verse):
                self.assertIn(r"\vsec{1.%d}" % verse, self.tex)
        # \vfig несе і схему, і наративну сцену, тому в главі 1 його більше,
        # ніж віршів: 20 схем + стільки сцен, скільки зареєстровано на главу 1.
        scenes = sum(1 for verse in builder.load_scenes() if verse.startswith("1."))
        expected = {r"\vdeva": 20, r"\vtranslit": 20, r"\vperek": 20, r"\vcom": 20,
                    r"\vpar": 20, r"\vfig": 20 + scenes}
        for macro, count in expected.items():
            with self.subTest(macro=macro):
                self.assertEqual(self.tex.count(macro + "{"), count)

    def test_braces_are_balanced(self) -> None:
        for number, line in enumerate(self.tex.splitlines(), 1):
            if line.startswith("%") or not line:
                continue
            depth = 0
            escaped = False
            for char in line:
                if escaped:
                    escaped = False
                    continue
                if char == "\\":
                    escaped = True
                elif char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
            self.assertEqual(depth, 0, f"рядок {number}: незбалансовані дужки")

    def test_no_citation_markers_in_tex(self) -> None:
        self.assertNotIn("[cite:", self.tex)


class PoeticTests(unittest.TestCase):
    def setUp(self) -> None:
        self.poems = builder.load_poetic(CHAPTER)
        self.tex = (BOOK / "generated" / "poetychnyi-1.tex").read_text(encoding="utf-8")

    def test_twenty_poems(self) -> None:
        ordered = sorted(self.poems, key=lambda v: int(v.split(".")[1]))
        self.assertEqual(ordered, [f"1.{n}" for n in range(1, 21)])

    def test_every_poem_has_lines(self) -> None:
        for verse, lines in self.poems.items():
            with self.subTest(verse=verse):
                self.assertGreaterEqual(len(lines), 1)

    def test_poems_are_ukrainian_not_latin(self) -> None:
        """Латиниця допустима лише в санскритських термінах, названих у тексті."""
        allowed = {"cit"}
        for verse, lines in self.poems.items():
            with self.subTest(verse=verse):
                stray = {w for w in re.findall(r"[A-Za-z]+", " ".join(lines))
                         if w not in allowed}
                self.assertEqual(stray, set(), f"{verse}: {stray}")

    def test_poetic_is_labelled_as_ours(self) -> None:
        readme = (BOOK / "poetychnyi" / "README.md").read_text(encoding="utf-8")
        self.assertIn("наш поетичний переклад", readme)
        self.assertIn("не канонічний", readme)

    def test_tex_is_current(self) -> None:
        self.assertFalse(
            builder.stale(BOOK / "generated" / "poetychnyi-1.tex",
                          builder.build_poetic_latex(CHAPTER)),
            "generated/poetychnyi-1.tex застарів")

    def test_tex_has_all_verses(self) -> None:
        for verse in range(1, 21):
            with self.subTest(verse=verse):
                self.assertIn(r"\poemverse{1.%d}" % verse, self.tex)

    def test_poetic_does_not_replace_translation(self) -> None:
        """Обидва переклади мусять бути в книзі, а не один замість одного."""
        main = (BOOK / "main.tex").read_text(encoding="utf-8")
        self.assertIn("generated/rozdil-1.tex", main)
        self.assertIn("generated/poetychnyi-1.tex", main)
        self.assertIn("наш поетичний переклад", main)


class BookTests(unittest.TestCase):
    def test_main_tex_declares_working_edition(self) -> None:
        main = (BOOK / "main.tex").read_text(encoding="utf-8")
        self.assertIn("РОБОЧЕ ПІЛОТНЕ ВИДАННЯ", main)
        self.assertIn("Aṣṭāvakragītā", main)

    def test_main_tex_has_devanagari_font(self) -> None:
        main = (BOOK / "main.tex").read_text(encoding="utf-8")
        self.assertIn("Devanagari", main)
        self.assertIn("Script=Devanagari", main)

    def test_provenance_exists(self) -> None:
        self.assertTrue((BOOK / "PROVENANCE.md").is_file())

    def test_format_v2_data_matches_cards(self) -> None:
        extra = json.loads((BOOK / "format-v2" / "rozdil-1.json").read_text(
            encoding="utf-8"))
        ids = {c["id"] for c in builder.load_cards(CHAPTER)}
        self.assertEqual(set(extra["verses"]), ids)


if __name__ == "__main__":
    unittest.main()
