"""Офлайнові позитивні й негативні тести JSON у загальному гейті якості."""
from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import check_project


class EditorialCardSyntaxTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for rel in check_project.REQUIRED:
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("Тестовий документ\n", encoding="utf-8")
        license_text = "ВОЛЬНІСТЬ\n\nСинтетичний текст для тесту\n"
        (self.root / "LICENSE").write_text(license_text, encoding="utf-8")
        (self.root / "VOLNOST.md").write_text(license_text, encoding="utf-8")
        (self.root / "tasks" / "ISSUES.json").write_text("[]\n", encoding="utf-8")

    def card(self, name: str = "7.1.json") -> Path:
        folder = self.root / "editorial" / "cards"
        folder.mkdir(parents=True, exist_ok=True)
        return folder / name

    def check(self) -> tuple[int, dict]:
        with mock.patch.object(check_project, "ROOT", self.root):
            with contextlib.redirect_stdout(io.StringIO()):
                return_code = check_project.run()
        report = json.loads((self.root / "reports" / "checks.json").read_text(encoding="utf-8"))
        return return_code, report

    def test_no_cards_keeps_minimal_fixture_valid(self):
        code, report = self.check()
        self.assertEqual(code, 0)
        self.assertEqual(report["errors"], [])

    def test_valid_json_card_passes_general_gate(self):
        self.card().write_text('{"id": "7.1", "commentary": "Це лише тест."}\n', encoding="utf-8")
        code, report = self.check()
        self.assertEqual(code, 0)
        self.assertEqual(report["status"], "ok")

    def test_broken_quotation_marks_fail_with_card_path(self):
        self.card().write_text('{"commentary": "Сенс, а не «спокій"."}\n', encoding="utf-8")
        code, report = self.check()
        self.assertEqual(code, 1)
        self.assertEqual(report["status"], "failed")
        self.assertTrue(any("editorial/cards/7.1.json" in e and "JSON" in e
                            for e in report["errors"]))
        self.assertTrue(any("line 1" in e for e in report["errors"]))

    def test_invalid_utf8_fails(self):
        self.card().write_bytes(b'{"commentary":"\xff"}')
        code, report = self.check()
        self.assertEqual(code, 1)
        self.assertTrue(any("7.1.json" in e and "UTF-8" in e
                            for e in report["errors"]))

    def test_symlink_card_rejected(self):
        card = self.card()
        target = self.root / "elsewhere.json"
        target.write_text('{"valid": true}\n', encoding="utf-8")
        try:
            card.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("Символічні посилання тут не підтримуються")
        code, report = self.check()
        self.assertEqual(code, 1)
        self.assertTrue(any("символічне посилання" in e
                            for e in report["errors"]))

    def test_json_named_directory_rejected(self):
        self.card().mkdir()
        code, report = self.check()
        self.assertEqual(code, 1)
        self.assertTrue(any("7.1.json" in e and "очікується JSON-файл" in e
                            for e in report["errors"]))

    def test_existing_reports_keep_other_errors(self):
        self.card().write_text("{broken", encoding="utf-8")
        (self.root / "README.md").write_text("[хибне](missing.md)\n", encoding="utf-8")
        code, report = self.check()
        self.assertEqual(code, 1)
        self.assertTrue(any("Некоректне посилання" in e for e in report["errors"]))
        self.assertTrue(any("7.1.json" in e for e in report["errors"]))


if __name__ == "__main__":
    unittest.main()
