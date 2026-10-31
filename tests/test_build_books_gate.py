"""Негативні тести видавничого шлюзу: жоден PDF без перевірки паспорта."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.check_provenance import audit


class TestVydavnychyiShliuz(unittest.TestCase):
    """Перевіряємо порядок дій, не вдаючи правової рецензії."""

    def test_manual_build_checks_provenance_before_any_pdf_actions(self):
        workflow = (ROOT / ".github/workflows/build-books.yml").read_text(
            encoding="utf-8"
        )
        markers = [
            "run: python3 scripts/check_project.py",
            "run: python3 scripts/check_provenance.py",
            "id: detect",
            "latexmk -xelatex",
            "name: ukrainski-vydannia",
        ]
        offsets = []
        for marker in markers:
            with self.subTest(marker=marker):
                self.assertEqual(
                    workflow.count(marker), 1,
                    f"Очікується рівно одне входження: {marker}",
                )
            offsets.append(workflow.index(marker))
        self.assertEqual(
            offsets, sorted(offsets),
            "Перевірка походження мусить передувати виявленню, складанню "
            "та завантаженню книг",
        )
        self.assertIn("workflow_dispatch:", workflow)

    def test_pull_requests_also_test_build_gate(self):
        workflow = (
            ROOT / ".github/workflows/provenance-audit.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("pull_request:", workflow)
        self.assertIn(
            "python3 -m unittest discover -s tests "
            "-p 'test_build_books_gate.py' -v",
            workflow,
        )

    def test_draft_book_with_main_tex_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            book = root / "books" / "not-approved"
            book.mkdir(parents=True)
            (book / "main.tex").write_text(
                "Суто синтетичне книжкове джерело",
                encoding="utf-8",
            )
            (book / "PROVENANCE.md").write_text(
                "# Синтетичний паспорт\n"
                "- **Статус:** чернетка\n",
                encoding="utf-8",
            )
            result = audit(root)
            self.assertEqual(result["status"], "failed")
            self.assertTrue(result["errors"])
            self.assertTrue(
                any("статус не дозволяє публікацію" in e for e in result["errors"]),
                result["errors"],
            )


if __name__ == "__main__":
    unittest.main()
