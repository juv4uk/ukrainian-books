"""Пілотне видання: верстка з власних карток, без чужих транскрипцій."""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import build_pilot_book as builder  # noqa: E402
from scripts.check_provenance import audit  # noqa: E402

BOOK = ROOT / "books" / "ashtavakra-hita-pilot"


class TestVerstalnaMashyna(unittest.TestCase):
    """Машина мусить верстати лише те, на що ми маємо право."""

    def test_generator_output_is_up_to_date(self):
        """Згенерована верстка не має відставати від карток."""
        cards = builder.load_cards(builder.PILOT_CHAPTERS)
        glossary = builder.load_glossary()
        verses = builder.render(cards, glossary)
        words = builder.render_glossary(glossary)
        self.assertFalse(
            builder.stale(BOOK / "generated" / "verses.tex", verses),
            "generated/verses.tex застарів: запустіть python3 scripts/build_pilot_book.py",
        )
        self.assertFalse(
            builder.stale(BOOK / "generated" / "glossary.tex", words),
            "generated/glossary.tex застарів: запустіть python3 scripts/build_pilot_book.py",
        )

    def test_witness_transcriptions_never_reach_the_pdf(self):
        """Жодне читання GRETIL/SARIT не потрапляє у верстку."""
        text = (BOOK / "generated" / "verses.tex").read_text(encoding="utf-8")
        for card in builder.load_cards(builder.PILOT_CHAPTERS):
            for field in builder.WITNESS_FIELDS:
                value = card.get(field)
                if not value:
                    continue
                with self.subTest(card=card["id"], field=field):
                    self.assertNotIn(
                        builder.esc(value), text,
                        f"Транскрипція свідка з картки {card['id']} потрапила в PDF",
                    )

    def test_pilot_covers_complete_chapters_only(self):
        """Пілот складається з глав, покритих картками без пропусків."""
        cards = builder.load_cards(builder.PILOT_CHAPTERS)
        numbers: dict[int, list[int]] = {}
        for card in cards:
            chapter, verse = card["id"].split(".")
            numbers.setdefault(int(chapter), []).append(int(verse))
        self.assertEqual(sorted(numbers), sorted(builder.PILOT_CHAPTERS))
        for chapter, verses in numbers.items():
            with self.subTest(chapter=chapter):
                self.assertEqual(
                    sorted(verses), list(range(1, len(verses) + 1)),
                    f"У главі {chapter} є пропуски в нумерації карток",
                )

    def test_every_typeset_card_is_still_a_draft(self):
        """Пілот чесно називає картки чернетками — і це має бути правдою."""
        for card in builder.load_cards(builder.PILOT_CHAPTERS):
            with self.subTest(card=card["id"]):
                self.assertEqual(card["status"], "чернетка")

    def test_title_page_declares_working_pilot(self):
        tex = (BOOK / "main.tex").read_text(encoding="utf-8")
        for marker in (
            "РОБОЧЕ ПІЛОТНЕ ВИДАННЯ",
            "Це не завершена книга",
            "«чернетка»",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, tex)

    def test_latex_escaping_handles_control_characters(self):
        cases = {
            "50% і $5": r"50\% і \$5",
            "a_b & c#d": r"a\_b \& c\#d",
            "x{y}z": r"x\{y\}z",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(builder.esc(raw), expected)

    def test_glossary_rows_are_parsed(self):
        glossary = builder.load_glossary()
        self.assertTrue(glossary, "Словник редакції не прочитано")
        terms = [row[0] for row in glossary]
        self.assertIn("ātman", terms)
        for row in glossary:
            with self.subTest(term=row[0]):
                self.assertEqual(len(row), 3)
                self.assertTrue(row[1])

    def test_index_entries_carry_sort_keys(self):
        """makeindex не знає IAST: ключ сортування мусить бути латинський."""
        entry = builder.index_entry("āśrama")
        self.assertIn(r"\index{asrama@", entry)

    def test_pilot_book_passes_provenance_gate(self):
        """Паспорт походження пілота мусить проходити машинний шлюз."""
        result = audit(ROOT)
        self.assertEqual(result["status"], "ok", result["errors"])
        states = {record["book"]: record["state"] for record in result["books"]}
        self.assertEqual(states.get("ashtavakra-hita-pilot"), "metadata-complete")

    def test_build_workflow_stays_manual_only(self):
        """Збірка не запускається на кожен push."""
        workflow = (ROOT / ".github/workflows/build-books.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("push:", workflow)
        self.assertNotIn("pull_request:", workflow)

    def test_manifest_matches_generated_content(self):
        manifest = json.loads(
            (BOOK / "generated" / "manifest.json").read_text(encoding="utf-8")
        )
        cards = builder.load_cards(builder.PILOT_CHAPTERS)
        self.assertEqual(manifest["verses"], len(cards))
        self.assertEqual(manifest["cards"], [card["id"] for card in cards])
        self.assertEqual(manifest["statuses"], ["чернетка"])
        self.assertEqual(
            sorted(manifest["witness_fields_excluded"]),
            sorted(builder.WITNESS_FIELDS),
        )

    def test_generated_files_carry_no_manual_edit_banner(self):
        text = (BOOK / "generated" / "verses.tex").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("% ЗГЕНЕРОВАНО"))
        self.assertIsNone(
            re.search(r"[^\x00-\x7f]\[\s*cite:", text),
            "У згенерованому файлі не має бути сторонніх маркерів цитування",
        )


if __name__ == "__main__":
    unittest.main()
