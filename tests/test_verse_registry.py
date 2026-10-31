"""ІНЖ-09: безмережеві регресійні тести числових підсумків власного CSV.

Не завантажує санскритські корпуси і не змінює реальний реєстр. Тести
будують тимчасові копії лише числового індексу, не перевіряють текстів.
"""

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import check_verse_registry as registry


class RegistryConsistencyTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.index = Path(temporary.name) / "реєстр.csv"
        with registry.INDEX.open(encoding="utf-8", newline="") as source:
            reader = csv.DictReader(source)
            self.columns = list(reader.fieldnames or [])
            self.rows = list(reader)

    def audit(self) -> tuple[set[str], list[str]]:
        with self.index.open("w", encoding="utf-8", newline="") as target:
            writer = csv.DictWriter(target, fieldnames=self.columns)
            writer.writeheader()
            writer.writerows(self.rows)
        errors: list[str] = []
        with mock.patch.object(registry, "INDEX", self.index):
            found = registry.expected_from_csv(errors)
        return found, errors

    def test_unchanged_registry_has_298_ids_and_no_errors(self) -> None:
        found, errors = self.audit()
        self.assertEqual(len(found), 298)
        self.assertEqual(errors, [])

    def test_single_wrong_shared_count_is_rejected(self) -> None:
        self.rows[0]["спільних"] = "18"  # було 19; сусідні колонки ті самі
        _, errors = self.audit()
        self.assertTrue(any("спільних" in error for error in errors), errors)

    def test_negative_exclusive_count_is_rejected(self) -> None:
        self.rows[0]["лише_SARIT"] = "-1"
        _, errors = self.audit()
        self.assertTrue(any("Неприпустима кількість" in error for error in errors), errors)

    def test_non_integer_count_is_rejected(self) -> None:
        self.rows[0]["лише_GRETIL"] = "один"
        _, errors = self.audit()
        self.assertTrue(any("Хибні числові поля" in error for error in errors), errors)

    def test_empty_count_is_not_silently_ignored(self) -> None:
        self.rows[0]["спільних"] = ""
        _, errors = self.audit()
        self.assertTrue(errors, "порожнє числове поле не має проходити контроль")

    def test_mismatching_summary_is_rejected(self) -> None:
        self.rows[-1]["спільних"] = "295"
        _, errors = self.audit()
        self.assertTrue(any("Підсумковий рядок CSV: спільних" in e for e in errors), errors)

    def test_balanced_row_with_wrong_total_is_rejected(self) -> None:
        # Рядок залишається арифметично правильним, але загальні суми
        # вже не відповідають збереженому підсумковому рядку.
        self.rows[0]["спільних"] = "18"
        self.rows[0]["лише_GRETIL"] = "2"
        self.rows[0]["лише_SARIT"] = "1"
        _, errors = self.audit()
        self.assertTrue(any("Підсумковий рядок CSV: спільних" in e for e in errors), errors)

    def test_bad_summary_number_is_rejected(self) -> None:
        self.rows[-1]["лише_GRETIL"] = "невідомо"
        _, errors = self.audit()
        self.assertTrue(any("некоректне поле лише_GRETIL" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
