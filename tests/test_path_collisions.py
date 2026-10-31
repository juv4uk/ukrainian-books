"""Самодостатні негативні й позитивні тести колізій шляхів Git."""

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "scripts/check_path_collisions.py"
SPEC = importlib.util.spec_from_file_location("check_path_collisions", SOURCE)
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


class CollisionTests(unittest.TestCase):
    def test_distinct_filenames(self):
        self.assertEqual(checker.find_collisions(["research/1.1.md", "research/1.2.md"]), [])

    def test_same_file_different_case(self):
        self.assertIn(("README.md", "readme.md"), checker.find_collisions(["README.md", "readme.md"]))

    def test_directory_case_difference_is_collision(self):
        collisions = checker.find_collisions(["Книги/a.md", "книги/b.md"])
        self.assertIn(("Книги", "книги"), collisions)

    def test_nfc_nfd_equivalence(self):
        composed = "теми/cafe\u0301.md"
        normalized = "теми/caf\u00e9.md"
        self.assertTrue(checker.find_collisions([composed, normalized]))

    def test_casefold_expansion(self):
        self.assertTrue(checker.find_collisions(["Straße.md", "STRASSE.md"]))

    def test_same_path_appears_twice(self):
        self.assertEqual(checker.find_collisions(["Книга.md", "Книга.md"]), [])

    def test_nested_different_parents(self):
        self.assertEqual(checker.find_collisions(["a/b.txt", "c/B.txt"]), [])

    def test_nested_conflicting_file(self):
        self.assertIn(("розділ/Вступ.md", "розділ/вступ.md"),
                      checker.find_collisions(["розділ/Вступ.md", "розділ/вступ.md"]))

    def test_git_failure_is_closed(self):
        with patch.object(checker, "tracked_paths", side_effect=FileNotFoundError("git")):
            self.assertEqual(checker.run(Path(".")), 2)

    def test_empty_git_index_is_closed(self):
        with patch.object(checker, "tracked_paths", return_value=[]):
            self.assertEqual(checker.run(Path(".")), 2)

    def test_git_index_read_success(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
            (root / "Текст.txt").write_text("тест", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "Текст.txt"], check=True)
            self.assertEqual(checker.tracked_paths(root), ["Текст.txt"])
            self.assertEqual(checker.run(root), 0)

    def test_real_case_collision_git_index(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
            (root / "Book.md").write_text("а", encoding="utf-8")
            (root / "book.md").write_text("б", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "Book.md", "book.md"], check=True)
            self.assertEqual(checker.run(root), 1)


if __name__ == "__main__":
    unittest.main()
