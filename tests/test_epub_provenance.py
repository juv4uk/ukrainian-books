#!/usr/bin/env python3
"""Негативні тести структурного контролю EPUB без сторонніх книжкових даних."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.check_epub_provenance import audit


class EpubProvenanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def add(self, name: str, data: bytes = b"synthetic EPUB") -> Path:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def problems(self) -> list[str]:
        return audit(self.root)["errors"]

    def test_no_epub_does_not_claim_any_publication(self) -> None:
        result = audit(self.root)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["checked_epub"], 0)
        self.assertIn("не є підтвердженням прав", result["notice"])

    def test_epub_in_repository_root_is_rejected(self) -> None:
        self.add("neperevirena.epub")
        self.assertTrue(any("лише у books/" in e for e in self.problems()))

    def test_epub_in_unrelated_folder_is_rejected(self) -> None:
        self.add("research/novyi.EPUB")
        self.assertTrue(any("лише у books/" in e for e in self.problems()))

    def test_epub_directly_under_books_is_rejected(self) -> None:
        self.add("books/bez-papky.epub")
        self.assertTrue(any("лише у books/" in e for e in self.problems()))

    def test_missing_provenance_is_rejected(self) -> None:
        self.add("books/vydannia/chytannia.epub")
        self.assertTrue(any("PROVENANCE.md" in e for e in self.problems()))

    def test_passport_only_structurally_suffices(self) -> None:
        self.add("books/vydannia/PROVENANCE.md", "Структурний зразок, НЕ дозвіл на друк\n".encode("utf-8"))
        self.add("books/vydannia/versions/book.EPUB")
        result = audit(self.root)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["checked_epub"], 1)
        self.assertIn("не є підтвердженням прав", result["notice"])

    def test_symlink_epub_is_rejected(self) -> None:
        target = self.add("books/vydannia/source.txt")
        path = self.root / "books/vydannia/book.epub"
        try:
            path.symlink_to(target)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"Створення посилань недоступне: {exc}")
        self.assertTrue(any("символічним посиланням" in e for e in self.problems()))

    def test_symlink_passport_is_rejected(self) -> None:
        target = self.add("outside.txt")
        self.add("books/vydannia/book.epub")
        path = self.root / "books/vydannia/PROVENANCE.md"
        try:
            path.symlink_to(target)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"Створення посилань недоступне: {exc}")
        self.assertTrue(any("символічне посилання" in e for e in self.problems()))

    def test_books_directory_symlink_is_rejected(self) -> None:
        target = self.root / "elsewhere"
        target.mkdir()
        try:
            (self.root / "books").symlink_to(target, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"Створення посилань недоступне: {exc}")
        self.assertTrue(any("books/: символічне посилання" in e for e in self.problems()))


if __name__ == "__main__":
    unittest.main()
