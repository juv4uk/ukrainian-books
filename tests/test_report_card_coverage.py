"""Синтетичні тести незалежного, суто формального підрахунку карток."""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from report_card_coverage import count_coverage  # noqa: E402


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name) / "cards"
        self.expected = {"1.1", "1.2", "2.1"}
        self.template = json.loads(
            (ROOT / "docs" / "VERSE_CARD_TEMPLATE.json").read_text(encoding="utf-8")
        )

    def card(self, verse="1.1", status="чернетка"):
        card = copy.deepcopy(self.template)
        card["id"] = verse
        card["sources"]["gretil"]["locator"] = f"Avg_{verse}"
        card["sources"]["sarit"]["locator"] = f"verse_{verse}"
        card["status"] = status
        if status in ("перевірено", "рецензовано"):
            card["author"] = "Умовний автор тесту"
            for key in ("sanskrit", "iast", "grammar", "literal_meaning",
                        "ukrainian_translation", "commentary"):
                card[key] = "Синтетичне тестове значення"
            for source in ("gretil", "sarit"):
                card["sources"][source]["checked_on"] = "2026-10-30"
            card["variants_checked"] = True
            card["rights"].update(
                basis="Умовна підстава у синтетичному тесті",
                evidence_url="https://example.org/test-only",
                verified=True, own_ukrainian_text=True
            )
        if status == "рецензовано":
            card["review"] = {
                "reviewer": "Умовний інший рецензент",
                "reviewed_on": "2026-10-31",
                "review_url": "https://example.org/test-review"
            }
        return card

    def put(self, card, subdir=""):
        folder = self.folder / subdir
        folder.mkdir(parents=True, exist_ok=True)
        filename = folder / f"{card['id']}.json"
        filename.write_text(json.dumps(card, ensure_ascii=False), encoding="utf-8")
        return filename

    def test_absent_cards_are_missing_not_errors(self):
        report = count_coverage(self.expected, self.folder)
        self.assertEqual(report["стан"], "гаразд")
        self.assertEqual(report["підсумок"]["відсутні"], 3)
        self.assertEqual(report["підсумок"]["карток"], 0)

    def test_draft_does_not_imply_review(self):
        card = self.card()
        card["ukrainian_translation"] = "Власний текст у тесті"
        self.put(card)
        report = count_coverage(self.expected, self.folder)
        self.assertEqual(report["підсумок"]["статуси"],
                         {"чернетка": 1, "перевірено": 0, "рецензовано": 0})
        self.assertEqual(report["глави"][0]["відсутні"], 1)

    def test_counts_all_three_declared_statuses(self):
        self.put(self.card("1.1", "чернетка"))
        self.put(self.card("1.2", "перевірено"))
        self.put(self.card("2.1", "рецензовано"))
        report = count_coverage(self.expected, self.folder)
        self.assertEqual(report["стан"], "гаразд", report["помилки"])
        self.assertEqual(report["підсумок"]["відсутні"], 0)
        self.assertEqual(report["підсумок"]["статуси"],
                         {"чернетка": 1, "перевірено": 1, "рецензовано": 1})
        self.assertEqual(report["глави"][0]["карток"], 2)
        self.assertEqual(report["глави"][1]["карток"], 1)
        self.assertEqual(len(report["глави"]), 20)
        self.assertIn("не встановлює незалежності рецензій", report["застереження"])

    def test_invalid_json_fails_closed(self):
        self.folder.mkdir()
        (self.folder / "1.1.json").write_text("{", encoding="utf-8")
        report = count_coverage(self.expected, self.folder)
        self.assertEqual(report["стан"], "помилка")
        self.assertEqual(report["підсумок"]["карток"], 0)

    def test_outside_registry_fails(self):
        self.put(self.card("3.1"))
        result = count_coverage(self.expected, self.folder)
        self.assertEqual(result["стан"], "помилка")
        self.assertEqual(result["підсумок"]["карток"], 0)

    def test_duplicate_identifiers_fail(self):
        self.put(self.card("1.1"))
        self.put(self.card("1.1"), subdir="duplicate")
        report = count_coverage(self.expected, self.folder)
        self.assertEqual(report["стан"], "помилка")
        self.assertTrue(any("Повторний ID" in e for e in report["помилки"]))
        self.assertEqual(report["підсумок"]["карток"], 1)

    def test_invalid_claimed_review_does_not_count(self):
        card = self.card("1.1", "рецензовано")
        card["review"]["reviewer"] = card["author"]
        self.put(card)
        report = count_coverage(self.expected, self.folder)
        self.assertEqual(report["стан"], "помилка")
        self.assertEqual(report["підсумок"]["статуси"]["рецензовано"], 0)

    def test_symlinked_card_is_rejected(self):
        self.folder.mkdir()
        target = self.put(self.card("1.1"))
        (self.folder / "1.2.json").symlink_to(target)
        report = count_coverage(self.expected, self.folder)
        self.assertEqual(report["стан"], "помилка")
        self.assertTrue(any("Символьне посилання" in e for e in report["помилки"]))

    def test_symlinked_directory_is_rejected(self):
        target = Path(self.tmp.name) / "real-cards"
        target.mkdir()
        self.folder.symlink_to(target, target_is_directory=True)
        self.assertEqual(count_coverage(self.expected, self.folder)["стан"], "помилка")

    def test_template_outside_cards_is_not_counted(self):
        self.put(self.card("2.1"))
        (Path(self.tmp.name) / "docs").mkdir()
        (Path(self.tmp.name) / "docs" / "VERSE_CARD_TEMPLATE.json").write_text(
            "{}", encoding="utf-8"
        )
        report = count_coverage(self.expected, self.folder)
        self.assertEqual(report["підсумок"]["карток"], 1)

    def test_deterministic_report(self):
        self.put(self.card("2.1"))
        self.put(self.card("1.2"))
        first = count_coverage(self.expected, self.folder)
        second = count_coverage(self.expected, self.folder)
        self.assertEqual(first, second)
        self.assertEqual(first["глави"][0]["глава"], 1)
        self.assertEqual(first["глави"][-1]["глава"], 20)


if __name__ == "__main__":
    unittest.main()
