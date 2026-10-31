"""Позитивні та негативні тести аудиту буквалізованих тверджень паспорта."""
from __future__ import annotations

import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "scripts/audit_book_source_claims.py"
SPEC = importlib.util.spec_from_file_location("audit_book_source_claims", SOURCE)
audit_tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit_tool)

DENIAL = "- **Чужі матеріали:** деванагарі й IAST у \x60rozdil-*.md\x60 відсутні\n"


class AuditBookSourceClaimsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "books/ashtavakra-gita").mkdir(parents=True)

    def put(self, relpath: str, content: str) -> None:
        path = self.root / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def report(self) -> dict:
        return audit_tool.audit(self.root)

    def test_detects_nonempty_layers_against_explicit_denial(self):
        self.put("books/ashtavakra-gita/PROVENANCE.md", DENIAL)
        self.put("books/ashtavakra-gita/rozdil-1-naukove.md",
                 "## 1.1\n**Деванагарі.** ज्ञानम्\n**IAST.** jñānam\n")
        result = self.report()
        self.assertEqual(result["status"], "inconsistent")
        self.assertEqual(result["contradictions"][0]["evidence"][0]["layers"],
                         {"Деванагарі": 1, "IAST": 1})

    def test_empty_layers_do_not_prove_presence(self):
        self.put("books/ashtavakra-gita/PROVENANCE.md", DENIAL)
        self.put("books/ashtavakra-gita/rozdil-15-naukove.md",
                 "**Деванагарі.** \n**IAST.** \n")
        self.assertEqual(self.report()["status"], "no_detected_conflict")

    def test_narrative_mention_does_not_count_as_content(self):
        self.put("books/ashtavakra-gita/PROVENANCE.md", DENIAL)
        self.put("books/ashtavakra-gita/rozdil-1.md",
                 "Деванагарі й IAST згадані тільки в поясненні.\n")
        self.assertEqual(self.report()["status"], "no_detected_conflict")

    def test_no_denial_no_legal_inference(self):
        self.put("books/ashtavakra-gita/PROVENANCE.md",
                 "Умови використання свідка ще вивчають.\n")
        self.put("books/ashtavakra-gita/rozdil-1-naukove.md",
                 "**IAST.** jñānam\n")
        result = self.report()
        self.assertEqual(result["status"], "no_detected_conflict")
        self.assertEqual(result["books_with_explicit_denial"], 0)
        self.assertIn("НЕ підтверджує права", result["limitation"])

    def test_different_book_not_conflated(self):
        self.put("books/ashtavakra-gita/PROVENANCE.md", DENIAL)
        self.put("books/other-work/PROVENANCE.md", "Тут текст джерела дозволено.\n")
        self.put("books/other-work/rozdil-1.md", "**Деванагарі.** धिः\n")
        self.assertEqual(self.report()["contradictions"], [])

    def test_nested_path_deterministic(self):
        self.put("books/ashtavakra-gita/PROVENANCE.md", DENIAL)
        self.put("books/ashtavakra-gita/chapter/rozdil-2.md",
                 "**IAST.** ātmā\n")
        result = self.report()
        self.assertEqual(result["contradictions"][0]["evidence"][0]["path"],
                         "books/ashtavakra-gita/chapter/rozdil-2.md")

    def test_cli_strict_returns_nonzero_without_writing(self):
        self.put("books/ashtavakra-gita/PROVENANCE.md", DENIAL)
        self.put("books/ashtavakra-gita/rozdil-1.md", "**IAST.** ātmā\n")
        before = sorted(p.relative_to(self.root).as_posix()
                        for p in self.root.rglob("*") if p.is_file())
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(audit_tool.main(["--root", str(self.root), "--strict"]), 1)
        self.assertEqual(json.loads(buf.getvalue())["status"], "inconsistent")
        after = sorted(p.relative_to(self.root).as_posix()
                       for p in self.root.rglob("*") if p.is_file())
        self.assertEqual(before, after)

    def test_cli_informational_is_machine_readable(self):
        self.put("books/ashtavakra-gita/PROVENANCE.md", DENIAL)
        self.put("books/ashtavakra-gita/rozdil-1.md", "**Деванагарі.** आत्मन्\n")
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(audit_tool.main(["--root", str(self.root)]), 0)
        self.assertEqual(json.loads(buf.getvalue())["status"], "inconsistent")


if __name__ == "__main__":
    unittest.main()
