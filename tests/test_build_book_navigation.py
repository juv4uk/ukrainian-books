"""Регресійні свідки наукової навігації у згенерованому змісті.

Власні синтетичні картки; жодного запозиченого санскритського тексту.
Перевіряємо реальний виклик генератора, а не лише пошук підрядка в коді.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "scripts" / "build_book.py"
CHECK = ROOT / "scripts" / "check_book.py"


class ScientificBookNavigationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        cards = self.root / "editorial" / "cards"
        cards.mkdir(parents=True)
        (cards / "1.1.json").write_text(
            json.dumps({"id": "1.1", "ukrainian_translation": "Перший власний рядок."},
                       ensure_ascii=False),
            encoding="utf-8",
        )
        self.book = self.root / "books" / "ashtavakra-gita"
        self.book.mkdir(parents=True)

    def generate(self):
        result = subprocess.run(
            [sys.executable, str(BUILD), str(self.root)],
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return (self.book / "ZMIST.md").read_text(encoding="utf-8")

    def test_existing_scientific_chapter_has_a_link_and_legacy_audit_passes(self):
        (self.book / "rozdil-1-naukove.md").write_text(
            "# Робочий науковий макет 1.1\n", encoding="utf-8",
        )
        content = self.generate()
        self.assertIn(
            "| [1](rozdil-1.md) | 1 | повний | "
            "[Наукове читання](rozdil-1-naukove.md) |", content,
        )
        self.assertIn("Стан | Наукове читання", content)
        self.assertEqual(content.count("[Наукове читання](rozdil-"), 1)
        check = subprocess.run(
            [sys.executable, str(CHECK), str(self.root)],
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)

    def test_absent_scientific_chapter_never_creates_a_broken_link(self):
        content = self.generate()
        self.assertIn("| [1](rozdil-1.md) | 1 | повний | ще немає |", content)
        self.assertNotIn("](rozdil-1-naukove.md)", content)
        self.assertIn("| 2 | 0 | немає карток | — |", content)

    def test_poetic_catalog_link_only_when_file_exists(self):
        without = self.generate()
        self.assertNotIn("](poetychnyi/README.md)", without)
        catalog = self.book / "poetychnyi"
        catalog.mkdir()
        (catalog / "README.md").write_text("# Робочий поетичний том\n", encoding="utf-8")
        with_file = self.generate()
        self.assertIn("[каталог і стан чернеток](poetychnyi/README.md)", with_file)
        self.assertIn("ще не підтверджено як завершений", with_file)

    def test_two_builds_are_identical(self):
        (self.book / "rozdil-1-naukove.md").write_text("# Макет\n", encoding="utf-8")
        first = self.generate()
        second = self.generate()
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
