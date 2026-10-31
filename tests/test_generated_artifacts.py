"""Офлайнові негативні та позитивні докази захисту Git-індексу."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / "scripts" / "check_generated_artifacts.py"
spec = importlib.util.spec_from_file_location("check_generated_artifacts", MODULE)
assert spec is not None and spec.loader is not None
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class GeneratedArtifactsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True, capture_output=True)
        (self.root / ".gitignore").write_text("*.pdf\n*.aux\n*.synctex.gz\n", encoding="utf-8")

    def add(self, path: str, force: bool = False) -> None:
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("штучні дані\n", encoding="utf-8")
        command = ["git", "-C", str(self.root), "add"]
        if force:
            command.append("-f")
        subprocess.run([*command, "--", path], check=True, capture_output=True)

    def test_source_is_not_blocked(self) -> None:
        self.add("books/демо/main.tex")
        self.add("books/демо/PROVENANCE.md")
        self.assertEqual(checker.tracked_paths(self.root), ["books/демо/PROVENANCE.md", "books/демо/main.tex"])
        self.assertFalse(any(checker.is_generated_book_artifact(p) for p in checker.tracked_paths(self.root)))

    def test_force_added_pdf_and_latex_files_are_blocked(self) -> None:
        for path in (
            "books/демо/збірка.pdf",
            "books/демо/збірка.aux",
            "books/демо/збірка.synctex.gz",
            "books/демо/збірка.fdb_latexmk",
            "books/демо/збірка.xdv",
            "books/демо/збірка.idx",
        ):
            with self.subTest(path=path):
                self.add(path, force=True)
        found = [p for p in checker.tracked_paths(self.root) if checker.is_generated_book_artifact(p)]
        self.assertEqual(len(found), 6)

    def test_untracked_build_output_is_not_blocked(self) -> None:
        target = self.root / "books" / "demo" / "main.pdf"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"not a real pdf")
        self.assertEqual(checker.tracked_paths(self.root), [])

    def test_scope_limited_to_books(self) -> None:
        self.add("docs/reference.pdf", force=True)
        self.assertFalse(any(checker.is_generated_book_artifact(p) for p in checker.tracked_paths(self.root)))
        self.assertFalse(checker.is_generated_book_artifact("bookshelf/main.pdf"))
        self.assertFalse(checker.is_generated_book_artifact("books/main.tex"))

    def test_spaces_and_case(self) -> None:
        self.add("books/тест файли/MAIN.PDF", force=True)
        self.assertEqual(checker.tracked_paths(self.root), ["books/тест файли/MAIN.PDF"])
        self.assertTrue(checker.is_generated_book_artifact("books/тест файли/MAIN.PDF"))

    def test_invalid_repository_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as other:
            with self.assertRaises(subprocess.CalledProcessError):
                checker.tracked_paths(Path(other))


if __name__ == "__main__":
    unittest.main()
