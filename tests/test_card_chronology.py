"""Синтетичні офлайнові перевірки календарних дат без мережі й зміни канону."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from check_card_chronology import check_directory, inspect_date, inspect_review_order

TODAY = date(2026, 10, 31)


def example(gretil=None, sarit=None, reviewed=None):
    return {
        "sources": {
            "gretil": {"checked_on": gretil},
            "sarit": {"checked_on": sarit},
        },
        "review": {"reviewed_on": reviewed},
    }


class ChronologyTests(unittest.TestCase):
    def test_yesterday_accepted(self):
        self.assertEqual(inspect_date(example(sarit="2026-10-30"),
                                      ("sources", "sarit", "checked_on"), TODAY), [])

    def test_today_accepted(self):
        self.assertEqual(inspect_date(example(gretil="2026-10-31"),
                                      ("sources", "gretil", "checked_on"), TODAY), [])

    def test_future_sarit_rejected(self):
        errors = inspect_date(example(sarit="2026-11-01"),
                              ("sources", "sarit", "checked_on"), TODAY)
        self.assertTrue(any("майбутня дата" in e for e in errors))

    def test_future_gretil_rejected(self):
        errors = inspect_date(example(gretil="2027-01-01"),
                              ("sources", "gretil", "checked_on"), TODAY)
        self.assertTrue(any("майбутня дата" in e for e in errors))

    def test_future_review_rejected_even_for_draft(self):
        errors = inspect_date(example(reviewed="2026-11-01"),
                              ("review", "reviewed_on"), TODAY)
        self.assertTrue(any("майбутня дата" in e for e in errors))

    def test_null_and_missing_allowed(self):
        self.assertEqual(inspect_date(example(), ("review", "reviewed_on"), TODAY), [])
        self.assertEqual(inspect_date({}, ("sources", "sarit", "checked_on"), TODAY), [])

    def test_impossible_date_rejected(self):
        self.assertTrue(inspect_date(example(reviewed="2026-02-30"),
                                     ("review", "reviewed_on"), TODAY))

    def test_non_string_rejected(self):
        self.assertTrue(inspect_date(example(sarit=20261031),
                                     ("sources", "sarit", "checked_on"), TODAY))

    def test_review_precedes_sarit_check_rejected(self):
        problems = inspect_review_order(example(
            sarit="2026-10-31", reviewed="2026-10-30"))
        self.assertEqual(len(problems), 1)
        self.assertIn("sources.sarit.checked_on", problems[0])

    def test_review_precedes_gretil_check_rejected(self):
        problems = inspect_review_order(example(
            gretil="2026-10-31", sarit="2026-10-29",
            reviewed="2026-10-30"))
        self.assertEqual(len(problems), 1)
        self.assertIn("sources.gretil.checked_on", problems[0])

    def test_both_later_sources_reported_separately(self):
        problems = inspect_review_order(example(
            gretil="2026-10-31", sarit="2026-10-31",
            reviewed="2026-10-29"))
        self.assertEqual(len(problems), 2)

    def test_same_day_and_later_review_allowed(self):
        self.assertEqual(inspect_review_order(example(
            gretil="2026-10-30", sarit="2026-10-31",
            reviewed="2026-10-31")), [])
        self.assertEqual(inspect_review_order(example(
            gretil="2026-10-29", sarit="2026-10-30",
            reviewed="2026-10-31")), [])

    def test_unfilled_and_malformed_dates_not_double_reported(self):
        self.assertEqual(inspect_review_order(example(
            gretil="2026-10-31", reviewed=None)), [])
        self.assertEqual(inspect_review_order(example(
            gretil="невідома дата", reviewed="2026-10-30")), [])
        self.assertEqual(inspect_review_order(example(
            gretil="2026-10-31", reviewed="не дата")), [])
        self.assertEqual(inspect_review_order({"review": [], "sources": {} }), [])

    def test_directory_rejects_review_before_sarit_witness(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "1.1.json").write_text(
                json.dumps(example(
                    gretil="2026-10-29", sarit="2026-10-31",
                    reviewed="2026-10-30"), ensure_ascii=False),
                encoding="utf-8")
            count, errors = check_directory(folder, TODAY)
            self.assertEqual(count, 1)
            self.assertEqual(len(errors), 1)
            self.assertIn("sources.sarit.checked_on", errors[0])

    def test_missing_folder_is_error(self):
        with tempfile.TemporaryDirectory() as directory:
            count, errors = check_directory(Path(directory) / "cards", TODAY)
            self.assertEqual(count, 0)
            self.assertTrue(any("відсутній" in error for error in errors))

    def test_empty_folder_is_error(self):
        with tempfile.TemporaryDirectory() as directory:
            count, errors = check_directory(Path(directory), TODAY)
            self.assertEqual(count, 0)
            self.assertTrue(any("не знайдено JSON-карток" in error for error in errors))

    def test_files_scan_rejects_future_date(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "1.1.json").write_text(
                json.dumps(example(sarit="2026-10-31"), ensure_ascii=False),
                encoding="utf-8")
            (folder / "1.2.json").write_text(
                json.dumps(example(reviewed="2026-11-01"), ensure_ascii=False),
                encoding="utf-8")
            count, errors = check_directory(folder, TODAY)
            self.assertEqual(count, 2)
            self.assertEqual(len(errors), 1)
            self.assertIn("1.2.json", errors[0])

    def test_invalid_json_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "1.1.json").write_text("{невірно}", encoding="utf-8")
            count, errors = check_directory(folder, TODAY)
            self.assertEqual(count, 1)
            self.assertTrue(errors)

    def test_symlinked_card_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "original.txt").write_text("{}", encoding="utf-8")
            (folder / "1.1.json").symlink_to(folder / "original.txt")
            count, errors = check_directory(folder, TODAY)
            self.assertEqual(count, 1)
            self.assertTrue(any("посилання" in err for err in errors))


if __name__ == "__main__":
    unittest.main()
