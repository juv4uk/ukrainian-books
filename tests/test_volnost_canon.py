"""Позитивні та негативні тести незмінності ліцензії «ВОЛЬНІСТЬ»."""

from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.check_volnost_canon import (  # noqa: E402
    CANONICAL_BYTES,
    CANONICAL_SHA256,
    check_volnost,
)


class VolnostIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.canonical = (ROOT / "LICENSE").read_bytes()
        if hashlib.sha256(cls.canonical).hexdigest() != CANONICAL_SHA256:
            raise AssertionError("Тестовий зразок не відповідає зафіксованому канону")
        if len(cls.canonical) != CANONICAL_BYTES:
            raise AssertionError("Некоректна довжина тестового зразка")

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name)

    def save(self, left: bytes | None, right: bytes | None) -> None:
        if left is not None:
            (self.path / "LICENSE").write_bytes(left)
        if right is not None:
            (self.path / "VOLNOST.md").write_bytes(right)

    def test_kanonichni_kopii_prokhodiat(self) -> None:
        self.save(self.canonical, self.canonical)
        self.assertEqual(check_volnost(self.path), [])

    def test_obydvi_odnakovo_zmineni_kopii_vidkhyleno(self) -> None:
        changed = self.canonical.replace("ВОЛЬНІСТЬ".encode(), "ВОЛЬНІСТЬ!".encode(), 1)
        self.save(changed, changed)
        errors = check_volnost(self.path)
        self.assertTrue(any("контрольна сума" in e for e in errors))

    def test_odna_zminena_kopiia_vidkhyleno(self) -> None:
        self.save(self.canonical, self.canonical + b"x")
        errors = check_volnost(self.path)
        self.assertTrue(any("не збігаються побайтово" in e for e in errors))

    def test_vidsutnii_fayl_vidkhyleno(self) -> None:
        self.save(self.canonical, None)
        errors = check_volnost(self.path)
        self.assertTrue(any("VOLNOST.md" in e for e in errors))

    def test_zaivyi_perevod_riadka_vidkhyleno(self) -> None:
        changed = self.canonical + b"\n"
        self.save(changed, changed)
        errors = check_volnost(self.path)
        self.assertTrue(any("контрольна сума" in e for e in errors))
        self.assertTrue(any("довжина" in e for e in errors))

    def test_bez_fayliv_ne_prokhodyt(self) -> None:
        self.assertEqual(len(check_volnost(self.path)), 2)


if __name__ == "__main__":
    unittest.main()
