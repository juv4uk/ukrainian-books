"""Офлайн-тести коректних і помилкових DOI-посилань."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

FILE = Path(__file__).resolve().parents[1] / "scripts/check_bibliography_doi.py"
SPEC = importlib.util.spec_from_file_location("doi_checker", FILE)
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


class DOIValidationTests(unittest.TestCase):
    def test_valid_doi(self):
        self.assertEqual(checker.inspect("[DOI:10.1353/par.2004.0011](https://doi.org/10.1353/par.2004.0011)", "a.md"), (1, []))

    def test_case_insensitive(self):
        self.assertEqual(checker.inspect("[doi:10.1353/ABC](https://doi.org/10.1353/abc)", "a.md"), (1, []))

    def test_plain_doi_and_unrelated_link_ignored(self):
        self.assertEqual(checker.inspect("DOI 10.1353/abc\n[Каталог](https://example.org/)", "a.md"), (0, []))

    def test_mismatch_rejected(self):
        n, errors = checker.inspect("[DOI:10.1353/a](https://doi.org/10.1353/b)", "a.md")
        self.assertEqual(n, 1)
        self.assertTrue(any("не збігається" in s for s in errors))

    def test_http_and_legacy_host_rejected(self):
        for url in ["http://doi.org/10.1353/a", "https://dx.doi.org/10.1353/a"]:
            with self.subTest(url=url):
                self.assertTrue(checker.inspect(f"[DOI:10.1353/a]({url})", "a.md")[1])

    def test_malformed_doi_and_query_rejected(self):
        for url in ["https://doi.org/invalid", "https://doi.org/10.1353/a?x=1"]:
            with self.subTest(url=url):
                self.assertTrue(checker.inspect(f"[Посилання]({url})", "a.md")[1])

    def test_label_on_unrelated_website_rejected(self):
        self.assertTrue(checker.inspect("[DOI:10.1353/a](https://example.org/a)", "a.md")[1])

    def test_percent_encoded_suffix(self):
        self.assertEqual(checker.inspect("[DOI:10.1353/abc](https://doi.org/10.1353/%61bc)", "a.md"), (1, []))

    def test_two_files_and_no_duplicate_ban(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "research/ashtavakra"
            folder.mkdir(parents=True)
            row = "[DOI:10.1353/abc](https://doi.org/10.1353/abc)"
            (folder / "bibliography.md").write_text(row, encoding="utf-8")
            (folder / "bibliography-supplement.md").write_text(row, encoding="utf-8")
            result = checker.audit(root)
            self.assertEqual((result["status"], result["files"], result["doi_links"]), ("ok", 2, 2))

    def test_reference_doi_valid_and_label_normalized(self):
        source = (
            "[DOI:10.1353/ABC][  ВИДАННЯ   А ]\n"
            "[видання а]: <https://doi.org/10.1353/abc> \"Стаття\"\n"
        )
        self.assertEqual(checker.inspect(source, "a.md"), (1, []))

    def test_reference_doi_mismatch_blocks(self):
        source = (
            "[DOI:10.1353/a][джерело]\n"
            "[джерело]: https://doi.org/10.1353/b\n"
        )
        number, errors = checker.inspect(source, "a.md")
        self.assertEqual(number, 1)
        self.assertTrue(any("не збігається" in e for e in errors), errors)

    def test_reference_doi_undefined_fails(self):
        number, errors = checker.inspect("[DOI:10.1353/a][невідомо]", "a.md")
        self.assertEqual(number, 1)
        self.assertTrue(any("невизначена" in e for e in errors), errors)

    def test_reference_doi_implicit_label_and_bad_scheme(self):
        source = (
            "[DOI:10.1353/a][]\n"
            "[doi:10.1353/a]: http://doi.org/10.1353/a\n"
        )
        number, errors = checker.inspect(source, "a.md")
        self.assertEqual(number, 1)
        self.assertTrue(any("https://doi.org/" in e for e in errors), errors)

    def test_regular_reference_link_not_treated_as_doi(self):
        source = (
            "[Каталог][покажчик]\n"
            "[покажчик]: https://example.org/catalogue\n"
        )
        self.assertEqual(checker.inspect(source, "a.md"), (0, []))

    def test_inline_and_reference_checked_together(self):
        source = (
            "[DOI:10.1353/a](https://doi.org/10.1353/a)\n"
            "[Стаття][ідентифікатор]\n"
            "[ідентифікатор]: https://doi.org/10.1353/b\n"
        )
        self.assertEqual(checker.inspect(source, "a.md"), (2, []))

    def test_missing_bibliography_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(checker.audit(Path(tmp))["status"], "failed")


if __name__ == "__main__":
    unittest.main()
