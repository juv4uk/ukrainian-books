"""Офлайнові тести локальних Markdown-зображень у загальному гейті якості.

Лише штучне тимчасове дерево: ліцензійний та книжковий корпус не змінюємо.
"""
from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import check_project


class LocalImageLinkTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

        # Мінімальна імітація обов'язкової структури для перевірки run().
        for name in check_project.REQUIRED:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("Тестова фікстура\n", encoding="utf-8")
        license_text = "ВОЛЬНІСТЬ\n\nКонтрольний тестовий текст\n"
        for name in ("LICENSE", "VOLNOST.md"):
            (self.root / name).write_text(license_text, encoding="utf-8")
        (self.root / "tasks/ISSUES.json").write_text("[]\n", encoding="utf-8")

    def check(self, markdown: str):
        (self.root / "README.md").write_text(markdown, encoding="utf-8")
        with mock.patch.object(check_project, "ROOT", self.root):
            with contextlib.redirect_stdout(io.StringIO()):
                exit_code = check_project.run()
        report = json.loads((self.root / "reports/checks.json").read_text(encoding="utf-8"))
        return exit_code, report

    def test_missing_local_image_is_error(self):
        code, report = self.check("![Малюнок](docs/missing.png)\n")
        self.assertEqual(code, 1)
        self.assertEqual(report["status"], "failed")
        self.assertTrue(any("README.md → docs/missing.png" in e for e in report["errors"]))

    def test_existing_local_image_is_allowed(self):
        image = self.root / "docs/figure.png"
        image.write_bytes(b"synthetic")
        code, report = self.check("![Малюнок](docs/figure.png)\n")
        self.assertEqual(code, 0)
        self.assertEqual(report["errors"], [])

    def test_remote_image_is_not_local_file(self):
        code, report = self.check("![Приклад](https://example.org/figure.png)\n")
        self.assertEqual(code, 0)
        self.assertEqual(report["errors"], [])

    def test_percent_encoded_path_and_fragment(self):
        (self.root / "docs/назва пробіл.png").write_bytes(b"synthetic")
        code, report = self.check("![Зображення](docs/назва%20пробіл.png#фрагмент)\n")
        self.assertEqual(code, 0)
        self.assertEqual(report["errors"], [])

    def test_escape_outside_repository_is_rejected(self):
        code, report = self.check("![Схема](../../outside.png)\n")
        self.assertEqual(code, 1)
        self.assertTrue(any("Некоректне посилання" in e for e in report["errors"]))

    def test_existing_markdown_link_rule_remains(self):
        code, report = self.check("[Документ](docs/неіснує.md)\n")
        self.assertEqual(code, 1)
        self.assertTrue(any("docs/неіснує.md" in e for e in report["errors"]))

    def test_internal_anchor_is_allowed(self):
        code, report = self.check("![Умовна схема](#схема)\n")
        self.assertEqual(code, 0)
        self.assertEqual(report["errors"], [])


if __name__ == "__main__":
    unittest.main()
