"""Негативні/позитивні синтетичні тести РЕД-05 без сторонніх залежностей."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.check_book_text_integrity import audit, scan_text


class UnicodeBookIntegrityTests(unittest.TestCase):
    def test_ukrainian_iast_and_devanagari_valid(self):
        text = "Пізнай Атман: ātman, sākṣin, śānti, āśrama; देवनागरी.\nУкраї\u0301нський наголос.\n"
        self.assertEqual(scan_text(text), [])

    def test_replacement_character_rejected(self):
        errors = scan_text("Український св\uFFFDдок")
        self.assertEqual([e["codepoint"] for e in errors], ["U+FFFD"])

    def test_hebrew_mark_attached_to_cyrillic_rejected(self):
        self.assertIn("U+0596", [e["codepoint"] for e in scan_text("т\u0596лі")])

    def test_arabic_mark_attached_to_latin_rejected(self):
        self.assertIn("U+0654", [e["codepoint"] for e in scan_text("a\u0654")])

    def test_genuine_hebrew_and_arabic_text_not_automatically_rejected(self):
        self.assertEqual(scan_text("שָׁלוֹם، عَرَبِيّ"), [])

    def test_bidi_controls_rejected(self):
        self.assertIn("U+202E", [e["codepoint"] for e in scan_text("текст\u202E")])

    def test_invisible_word_joiner_rejected(self):
        self.assertIn("U+2060", [e["codepoint"] for e in scan_text("сло\u2060во")])

    def test_nul_character_rejected(self):
        self.assertIn("U+0000", [e["codepoint"] for e in scan_text("текст\u0000")])

    def test_tab_and_crlf_allowed(self):
        self.assertEqual(scan_text("Текст\tпримітка\r\nНовий рядок"), [])

    def test_ordinary_spelling_errors_are_out_of_scope(self):
        self.assertEqual(scan_text("двадчять Чк"), [])

    def test_empty_repository_is_valid_but_explicit(self):
        with tempfile.TemporaryDirectory() as temp:
            result = audit(Path(temp))
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["scanned_files"], 0)

    def test_nested_book_and_passport_scanned(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "books" / "ashtavakra" / "chapters"
            target.mkdir(parents=True)
            (target / "first.tex").write_text("Глава 1\uFFFD", encoding="utf-8")
            (root / "books" / "ashtavakra" / "PROVENANCE.md").write_text("т\u0596лі", encoding="utf-8")
            output = audit(root)
            self.assertEqual(output["scanned_files"], 2)
            self.assertEqual(output["status"], "failed")
            self.assertEqual({e["codepoint"] for e in output["errors"]}, {"U+FFFD", "U+0596"})

    def test_invalid_utf8_bytes_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "books" / "work"
            path.mkdir(parents=True)
            (path / "main.tex").write_bytes(b"\xff not utf-8")
            output = audit(Path(temp))
            self.assertEqual(output["scanned_files"], 1)
            self.assertEqual(output["errors"][0]["codepoint"], "UTF-8")

    def test_non_book_and_binary_files_ignored(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "docs").mkdir()
            (root / "docs" / "bad.md").write_text("\uFFFD", encoding="utf-8")
            folder = root / "books" / "work"
            folder.mkdir(parents=True)
            (folder / "output.pdf").write_bytes(b"\x00\xff")
            (folder / "main.tex").write_text("Текст чистий", encoding="utf-8")
            output = audit(root)
            self.assertEqual(output["status"], "ok")
            self.assertEqual(output["scanned_files"], 1)

    def test_maximum_findings_limit(self):
        self.assertEqual(len(scan_text("\uFFFD" * 70)), 25)


class CardsAndResearchScopeTests(unittest.TestCase):
    """РЕД-05, розширення 31.10.2026: картки й примітки теж перевіряються.

    Історичний дефект `editorial/cards/2.2.json` («свіЂ», «Аштавакрааёіти»,
    «надбанні.Ритання») проходив повз CI, бо перевірка дивилася лише в
    `books/`. Тести нижче фіксують і те, що такі дефекти ловляться, і те, що
    законні IAST, деванагарі та латинські терміни не валяться.
    """

    def test_historical_card_2_2_defects_detected(self):
        self.assertEqual([e["codepoint"] for e in scan_text("свіЂ")], ["U+0402"])
        self.assertEqual([e["codepoint"] for e in scan_text("Аштавакрааёіти")], ["U+0451"])
        errors = scan_text("надбанні.Ритання", prose=True)
        self.assertEqual([e["reason"] for e in errors], ["втрачений пробіл після крапки"])

    def test_cyrillic_letters_outside_ukrainian_alphabet(self):
        for broken in ("ы", "э", "ъ", "ё", "Ђ", "Ў", "Џ", "Я\u0451"):
            self.assertTrue(scan_text(f"текст{broken}"), broken)

    def test_latin_letter_inside_cyrillic_word(self):
        errors = scan_text("Українське свiтло")  # латинська «i»
        self.assertEqual([e["codepoint"] for e in errors], ["U+0069"])
        self.assertIn("латиниця", errors[0]["reason"])

    def test_legitimate_card_text_passes(self):
        card = (
            '{\n'
            '  "id": "1.2",\n'
            '  "grammar": "kṣamā-ārjava-dayā-toṣa-satyaṃ (dvandva-складений іменник, '
            'n. acc. sg.); bahuvrīhi-складник — ātman, sākṣin, ṛṣi, ṃ, ḥ, ś, ṣ, ṭ, ḍ, ṇ, ñ.",\n'
            '  "sanskrit": "देवनागरी नमः | yatra viśvam idaṃ bhāti",\n'
            '  "ukrainian_translation": "«Звільнення бажаєш якщо, сину» — питальна форма."\n'
            '}\n'
        )
        self.assertEqual(scan_text(card, prose=True), [])

    def test_devanagari_and_iast_never_flagged(self):
        self.assertEqual(scan_text("ā ī ū ṛ ṃ ḥ ś ṣ ṭ ḍ ṇ ñ Ā Ī Ū Ṛ Ṃ Ḥ Ś Ṣ Ṭ Ḍ Ṇ Ñ", prose=True), [])
        self.assertEqual(scan_text("अष्टावक्रगीता १.२", prose=True), [])

    def test_double_space_in_prose_flagged_but_indent_and_line_end_allowed(self):
        self.assertEqual([e["reason"] for e in scan_text("Слово  два", prose=True)],
                         ["подвійний пробіл усередині тексту"])
        self.assertEqual(scan_text("    відступ рядка", prose=True), [])
        self.assertEqual(scan_text("кінець рядка  \nдалі", prose=True), [])

    def test_markdown_table_and_code_fence_not_flagged(self):
        text = "| Колонка |  Значення |\n| --- | --- |\n\n```\nx  =  1\n```\n"
        self.assertEqual(scan_text(text, prose=True), [])

    def test_books_tex_not_subject_to_prose_rules(self):
        # Верстка `.tex` законно містить вирівнювання — «прозові» правила
        # до `books/**` не застосовуються, щоб не валити чужі видання.
        self.assertEqual(scan_text("\\begin{tabular}{l  l}текст.Текст\\end{tabular}"), [])

    def test_cards_and_research_are_in_scope(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cards = root / "editorial" / "cards"
            cards.mkdir(parents=True)
            (cards / "2.2.json").write_text('{"id": "2.2", "text": "свіЂ"}', encoding="utf-8")
            (cards / "2.3.json").write_text('{"id": "2.3", "text": "світ"}', encoding="utf-8")
            research = root / "research" / "ashtavakra"
            research.mkdir(parents=True)
            (research / "notes.md").write_text("надбанні.Ритання", encoding="utf-8")
            output = audit(root)
            self.assertEqual(output["scanned_files"], 3)
            self.assertEqual(output["scanned_by_scope"]["cards"], 2)
            self.assertEqual(output["scanned_by_scope"]["research"], 1)
            self.assertEqual(output["status"], "failed")
            self.assertEqual({e["path"] for e in output["errors"]},
                             {"editorial/cards/2.2.json", "research/ashtavakra/notes.md"})

    def test_clean_cards_and_research_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cards = root / "editorial" / "cards"
            cards.mkdir(parents=True)
            (cards / "1.2.json").write_text('{"id": "1.2", "text": "dvandva-складений, ātman"}',
                                            encoding="utf-8")
            output = audit(root)
            self.assertEqual(output["status"], "ok")
            self.assertEqual(output["scanned_files"], 1)


if __name__ == "__main__":
    unittest.main()
