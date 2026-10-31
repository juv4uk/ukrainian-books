"""Синтетичні тести редакторських карток; ніяких текстів сторонніх видань."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.check_editorial_cards import (
    TEMPLATE, check_directory, valid_verse_ids, validate_card,
)


class CardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ids = valid_verse_ids()
        cls.template = json.loads(TEMPLATE.read_text(encoding="utf-8"))

    def draft(self) -> dict:
        return copy.deepcopy(self.template)

    def verified(self) -> dict:
        card = self.draft()
        card.update({
            "status": "перевірено",
            "author": "Редактор А",
            "sanskrit": "Власний тестовий вміст",
            "iast": "Власний тестовий вміст",
            "grammar": "Власна тестова граматика",
            "literal_meaning": "Власне тестове пояснення",
            "ukrainian_translation": "Власний тестовий переклад",
            "commentary": "Власний тестовий коментар",
            "variants_checked": True,
        })
        for source in card["sources"].values():
            source["checked_on"] = "2026-10-31"
        card["rights"] = {
            "basis": "Власна синтетична робота",
            "evidence_url": "https://github.com/juv4uk/ukrainian-books/issues/20",
            "verified": True,
            "own_ukrainian_text": True,
        }
        return card

    def reviewed(self) -> dict:
        card = self.verified()
        card["status"] = "рецензовано"
        card["review"] = {
            "reviewer": "Редактор Б",
            "reviewed_on": "2026-10-31",
            "review_url": "https://github.com/juv4uk/ukrainian-books/issues/20",
        }
        return card

    def assert_invalid(self, card: dict, part: str) -> None:
        errors = validate_card(card, self.ids)
        self.assertTrue(any(part in e for e in errors), errors)

    def test_index_298(self) -> None:
        self.assertEqual(len(self.ids), 298)
        self.assertIn("18.95", self.ids)
        self.assertIn("20.14", self.ids)
        self.assertNotIn("20.15", self.ids)

    def test_template_is_valid_draft(self) -> None:
        self.assertEqual(validate_card(self.draft(), self.ids, "1.1.json"), [])

    def test_verified_passes_synthetic_fields(self) -> None:
        self.assertEqual(validate_card(self.verified(), self.ids), [])

    def test_reviewed_passes_synthetic_fields(self) -> None:
        self.assertEqual(validate_card(self.reviewed(), self.ids), [])

    def test_unknown_verse(self) -> None:
        card = self.draft()
        card["id"] = "20.15"
        self.assert_invalid(card, "Невідомий")

    def test_filename_mismatch(self) -> None:
        self.assertTrue(validate_card(self.draft(), self.ids, "1.2.json"))

    def test_missing_source(self) -> None:
        card = self.draft()
        del card["sources"]["sarit"]
        self.assert_invalid(card, "свідок sarit")

    def test_not_https(self) -> None:
        card = self.draft()
        card["sources"]["gretil"]["url"] = "http://example.com"
        self.assert_invalid(card, "HTTPS")

    def test_unchecked_sources(self) -> None:
        card = self.verified()
        card["sources"]["gretil"]["checked_on"] = None
        self.assert_invalid(card, "дати звірення")

    def test_unverified_rights(self) -> None:
        card = self.verified()
        card["rights"]["verified"] = False
        self.assert_invalid(card, "права")

    def test_lost_translation(self) -> None:
        card = self.verified()
        card["ukrainian_translation"] = None
        self.assert_invalid(card, "ukrainian_translation")

    def test_missing_variants_review(self) -> None:
        card = self.verified()
        card["variants_checked"] = False
        self.assert_invalid(card, "різночитання")

    def test_self_review_forbidden(self) -> None:
        card = self.reviewed()
        card["review"]["reviewer"] = card["author"]
        self.assert_invalid(card, "власним незалежним")

    def test_review_proof_required(self) -> None:
        card = self.reviewed()
        card["review"]["review_url"] = None
        self.assert_invalid(card, "зафіксовану рецензію")

    def test_special_locator_18_95(self) -> None:
        card = self.draft()
        card["id"] = "18.95"
        card["sources"]["gretil"]["locator"] = "Avg_18.95"
        card["sources"]["sarit"]["locator"] = "verse_18.96#18.95"
        self.assertEqual(validate_card(card, self.ids), [])
        card["sources"]["sarit"]["locator"] = "verse_18.95"
        self.assert_invalid(card, "локатор")

    def test_duplicate_files_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a").mkdir()
            (root / "b").mkdir()
            payload = json.dumps(self.draft(), ensure_ascii=False)
            (root / "a/1.1.json").write_text(payload, encoding="utf-8")
            (root / "b/1.1.json").write_text(payload, encoding="utf-8")
            count, errors = check_directory(root, self.ids)
            self.assertEqual(count, 2)
            self.assertTrue(any("повторна картка" in e for e in errors), errors)

    def test_malformed_status_does_not_crash(self) -> None:
        card = self.draft()
        card["status"] = ["рецензовано"]
        self.assert_invalid(card, "Невідомий статус")

    def test_boolean_schema_version_rejected(self) -> None:
        card = self.draft()
        card["schema_version"] = True
        self.assert_invalid(card, "версія схеми")

    def test_unhashable_id_does_not_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            card = self.draft()
            card["id"] = {"зламана": "структура"}
            (Path(tmp) / "broken.json").write_text(
                json.dumps(card, ensure_ascii=False), encoding="utf-8"
            )
            count, errors = check_directory(Path(tmp), self.ids)
            self.assertEqual(count, 1)
            self.assertTrue(any("Невідомий ідентифікатор" in e for e in errors), errors)

    def test_invalid_json_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "1.1.json").write_text("{", encoding="utf-8")
            count, errors = check_directory(Path(tmp), self.ids)
            self.assertEqual(count, 1)
            self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
