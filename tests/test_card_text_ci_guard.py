#!/usr/bin/env python3
"""РЕД-11: суворий режим має зупиняти CI на обірваній картці.

Використовує лише синтетичний текст у тимчасовому каталозі.
Не завантажує сторонніх корпусів і не перевіряє філологічний зміст.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_card_text.py"

VALID = {
    "id": "1.1",
    "sanskrit": "kathaṃ jñānam avāpnoti ||",
    "iast": "kathaṃ jñānam avāpnoti ||",
    "literal_meaning": "«Як здобувають знання?»",
    "ukrainian_translation": "Як здобувають знання?",
    "commentary": "Це синтетичне запитання.",
}


class CardTextStrictCliTests(unittest.TestCase):
    def run_checker(self, card: dict, *, strict: bool) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "1.1.json"
            file.write_text(json.dumps(card, ensure_ascii=False) + "\n", encoding="utf-8")
            command = [sys.executable, str(SCRIPT), "--cards", tmp]
            if strict:
                command.append("--strict")
            return subprocess.run(
                command,
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

    def test_valid_synthetic_card_passes_strict(self) -> None:
        result = self.run_checker(VALID, strict=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("обірваних полів немає", result.stdout)

    def test_cut_translation_blocks_strict(self) -> None:
        broken = dict(VALID, ukrainian_translation="Як здобувають")
        result = self.run_checker(broken, strict=True)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("ukrainian_translation", result.stdout)

    def test_cut_translation_is_only_report_without_strict(self) -> None:
        broken = dict(VALID, ukrainian_translation="Як здобувають")
        result = self.run_checker(broken, strict=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("ukrainian_translation", result.stdout)


if __name__ == "__main__":
    unittest.main()
