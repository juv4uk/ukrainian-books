"""Негативні тести генератора: ніяких удаваних свідчень та перезаписів."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "create_verse_card.py"
SPEC = importlib.util.spec_from_file_location("create_verse_card", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class GeneratorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "docs").mkdir()
        registry = self.root / "research" / "ashtavakra" / "registry-20-chapters.csv"
        registry.parent.mkdir(parents=True)
        registry.write_text(
            "глава,GRETIL_віршів,SARIT_віршів\n"
            "1,20,19\n18,100,99\n20,14,14\n", encoding="utf-8"
        )
        self.template = {
            "schema_version": 1, "id": "1.1", "work": "Аштавакра-ґіта",
            "status": "чернетка", "author": None,
            "sources": {
                "gretil": {"url": "https://example.org/gretil", "locator": "Avg_1.1", "checked_on": None},
                "sarit": {"url": "https://example.org/sarit", "locator": "verse_1.1", "checked_on": None}
            },
            "sanskrit": None, "iast": None, "grammar": None,
            "literal_meaning": None, "ukrainian_translation": None, "commentary": None,
            "variants": [], "variants_checked": False,
            "rights": {"basis": None, "evidence_url": None, "verified": False,
                       "own_ukrainian_text": False},
            "review": {"reviewer": None, "reviewed_on": None, "review_url": None}
        }
        self.write_template()

    def write_template(self):
        (self.root / "docs" / "VERSE_CARD_TEMPLATE.json").write_text(
            json.dumps(self.template, ensure_ascii=False), encoding="utf-8"
        )

    def test_regular_verse_is_only_draft(self):
        path = Path(MODULE.create_card(self.root, "1.20"))
        card = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(card["id"], "1.20")
        self.assertEqual(card["sources"]["gretil"]["locator"], "Avg_1.20")
        self.assertEqual(card["sources"]["sarit"]["locator"], "verse_1.20")
        self.assertEqual(card["status"], "чернетка")
        self.assertIsNone(card["sanskrit"])
        self.assertIsNone(card["sources"]["gretil"]["checked_on"])
        self.assertFalse(card["variants_checked"])
        self.assertFalse(card["rights"]["verified"])
        self.assertIsNone(card["review"]["reviewer"])

    def test_sarit_xml_exception_18_95(self):
        card = MODULE.build_card(self.root, "18.95")
        self.assertEqual(card["sources"]["sarit"]["locator"], "verse_18.96#18.95")
        self.assertEqual(MODULE.build_card(self.root, "18.96")["sources"]["sarit"]["locator"], "verse_18.96")

    def test_reject_chapter_out_of_range_path_traversal_and_leading_zeroes(self):
        for invalid in ("0.1", "21.1", "1.0", "01.1", "1.01", "1.21", "18.101",
                        "20.15", "../1.1", "1.1/../../LICENSE", "1.1.json"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                MODULE.create_card(self.root, invalid)
        self.assertFalse((self.root / "editorial").exists())

    def test_preexisting_file_is_not_overwritten(self):
        path = self.root / "editorial" / "cards" / "1.1.json"
        path.parent.mkdir(parents=True)
        path.write_text("ЧУЖА РОБОТА\n", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            MODULE.create_card(self.root, "1.1")
        self.assertEqual(path.read_text(encoding="utf-8"), "ЧУЖА РОБОТА\n")

    def test_preview_writes_nothing(self):
        data = json.loads(MODULE.create_card(self.root, "20.14", preview=True))
        self.assertEqual(data["id"], "20.14")
        self.assertFalse((self.root / "editorial").exists())

    def test_reject_template_with_false_verification(self):
        self.template["sources"]["gretil"]["checked_on"] = "2026-10-31"
        self.write_template()
        with self.assertRaisesRegex(ValueError, "дату перевірки"):
            MODULE.build_card(self.root, "1.1")

    def test_reject_template_with_asserted_rights(self):
        self.template["rights"]["verified"] = True
        self.write_template()
        with self.assertRaisesRegex(ValueError, "прав і рецензії"):
            MODULE.build_card(self.root, "1.1")

    def test_reject_symlinked_cards_directory(self):
        (self.root / "editorial").mkdir()
        (self.root / "editorial" / "cards").symlink_to(self.root / "docs", target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "символьного"):
            MODULE.create_card(self.root, "1.1")
        self.assertFalse((self.root / "docs" / "1.1.json").exists())

    def test_reject_symlinked_editorial_directory(self):
        (self.root / "editorial").symlink_to(self.root / "docs", target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "символьного"):
            MODULE.create_card(self.root, "1.1")
        self.assertFalse((self.root / "docs" / "cards" / "1.1.json").exists())


if __name__ == "__main__":
    unittest.main()
