"""Офлайнові позитивні й негативні свідки чернеткової IAST-передачі."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

from scripts.iast_to_ukrainian_draft import draft_reading

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "iast_to_ukrainian_draft.py"


class UkrainianIastDraftTests(unittest.TestCase):
    def reading(self, text):
        lines = draft_reading(text)["lines"]
        self.assertEqual(len(lines), 1)
        return lines[0]["ukrainian_candidate"]

    def test_basic_akasha_uses_ukrainian_letters(self):
        self.assertEqual(self.reading("ākāśa"), "акаша")

    def test_distinguishes_g_from_breathy_gh_in_candidate(self):
        self.assertEqual(self.reading("gati"), "ґаті")
        self.assertEqual(self.reading("ghaṭa"), "гата")

    def test_jna_and_word_final_anusvara(self):
        self.assertEqual(self.reading("jñānaṃ"), "джнянам")

    def test_contextual_anusvara_before_s(self):
        self.assertEqual(self.reading("saṃsāra"), "сансара")

    def test_y_vowel_after_consonant(self):
        self.assertEqual(self.reading("tyāgaḥ"), "тьяґах")

    def test_half_verse_separator_preserves_line_order(self):
        result = draft_reading("tat tvam asi | iti jñānaṃ ||")
        self.assertEqual(len(result["lines"]), 2)
        self.assertEqual(result["lines"][0]["iast"], "tat tvam asi")
        self.assertEqual(result["lines"][1]["ukrainian_candidate"], "іті джнянам")

    def test_unicode_nfc_input_is_accepted(self):
        self.assertEqual(self.reading("a\u0304ka\u0304s\u0301a"), "акаша")

    def test_unrecognised_latin_must_not_be_copied(self):
        for text in ("xyz", "kṣa@", "śānti🧪", "कर्म"):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    draft_reading(text)

    def test_empty_input_is_refused(self):
        for text in ("", "  ", "|||"):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    draft_reading(text)

    def test_metadata_never_claims_approval(self):
        result = draft_reading("ātman | jñānaṃ")
        self.assertEqual(result["status"], "потребує-ручної-звірки")
        self.assertIn("НЕ затверджена", result["purpose"])
        self.assertTrue(result["warnings"])
        self.assertTrue(all("iast" in line and "ukrainian_candidate" in line
                            for line in result["lines"]))

    def test_cli_json_and_manual_review_label(self):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "ākāśa | jñānaṃ"],
            check=False, capture_output=True, text=True
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(len(payload["lines"]), 2)
        self.assertEqual(payload["status"], "потребує-ручної-звірки")

    def test_cli_refuses_invalid_script(self):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "abc@"],
            check=False, capture_output=True, text=True
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("Непідтримуваний", proc.stderr)


if __name__ == "__main__":
    unittest.main()
