"""Лише синтетичні фікстури; ніяких тверджень про реальні дозволи."""
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.check_provenance import audit

PASSPORT = """# Паспорт
- **Твір / назва оригіналу:** Тестова історія
- **Автор первісного твору:** Умовний автор
- **Джерельне видання / URL / рік:** умовний рукопис, 2026
- **Мова джерела, прямий переклад чи через посередника:** українська, оригінал
- **Автор українського перекладу:** Умовний автор
- **Правова підстава перекладу і публікації:** автор власного твору
- **Документ / URL, що підтверджує права:** https://example.org/synthetic
- **Дозвіл на PDF / EPUB / редагування / подальше поширення:** PDF: так; EPUB: так; редагування: так; поширення: так
- **Авторський внесок, до якого застосовано «ВОЛЬНІСТЬ»:** умовний власний твір
- **Чужі матеріали й їхні окремі умови (якщо є):** немає
- **Рецензент, дата перевірки:** тестовий рецензент, 2026-10-31
- **Статус:** дозволено до публікації
"""

class Tests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def make_book(self, contents=PASSPORT, material=True):
        b = self.root / "books" / "example"
        b.mkdir(parents=True)
        if contents is not None:
            (b / "PROVENANCE.md").write_text(contents, encoding="utf-8")
        if material:
            (b / "main.tex").write_text("Тест", encoding="utf-8")
        return b

    def result(self):
        return audit(self.root)

    def test_no_books_is_not_legal_approval(self):
        r = self.result()
        self.assertEqual(r["status"], "ok")
        self.assertIn("НЕ підтверджує", r["warning"])

    def test_valid_synthetic_form(self):
        self.make_book()
        self.assertEqual(self.result()["books"][0]["state"], "metadata-complete")
        self.assertEqual(self.result()["errors"], [])

    def test_no_passport_blocks(self):
        self.make_book(None)
        self.assertEqual(self.result()["status"], "failed")

    def test_blank_template_blocks(self):
        self.make_book("# Шаблон\n- **Статус:** дозволено до публікації\n")
        self.assertEqual(self.result()["status"], "failed")

    def test_draft_with_material_blocks(self):
        self.make_book(PASSPORT.replace("дозволено до публікації", "чернетка"))
        self.assertEqual(self.result()["status"], "failed")

    def test_blank_rights_blocks(self):
        self.make_book(PASSPORT.replace("автор власного твору", "невідомо"))
        self.assertEqual(self.result()["status"], "failed")

    def test_bad_evidence_blocks(self):
        self.make_book(PASSPORT.replace("https://example.org/synthetic", "TODO"))
        self.assertTrue(any("HTTPS" in x for x in self.result()["errors"]))

    def test_permission_denial_blocks(self):
        self.make_book(PASSPORT.replace("EPUB: так", "EPUB: ні"))
        self.assertTrue(any("PDF/EPUB" in x for x in self.result()["errors"]))

    def test_missing_date_blocks(self):
        self.make_book(PASSPORT.replace("2026-10-31", "пізніше"))
        self.assertTrue(any("дати" in x for x in self.result()["errors"]))

    def test_metadata_only_draft_allowed(self):
        self.make_book("# Чернетка паспорта\n- **Статус:** чернетка\n", False)
        self.assertEqual(self.result()["books"][0]["state"], "metadata-only")
        self.assertEqual(self.result()["errors"], [])

    def test_any_attached_image_needs_passport(self):
        b = self.make_book(None, False)
        (b / "cover.png").write_bytes(b"fake")
        self.assertEqual(self.result()["status"], "failed")

    def test_books_symlink_to_directory_blocks(self):
        external = self.root / "outside"
        external.mkdir()
        (self.root / "books").symlink_to(external, target_is_directory=True)
        r = self.result()
        self.assertEqual(r["status"], "failed")
        self.assertTrue(any("символічне посилання" in e for e in r["errors"]))

    def test_broken_books_symlink_is_not_absent_catalog(self):
        (self.root / "books").symlink_to(
            self.root / "absent", target_is_directory=True
        )
        self.assertEqual(self.result()["status"], "failed")

    def test_symlinked_book_material_blocks_with_path(self):
        b = self.make_book(material=False)
        target = self.root / "external.tex"
        target.write_text("Зовнішній текст", encoding="utf-8")
        (b / "main.tex").symlink_to(target)
        r = self.result()
        self.assertEqual(r["status"], "failed")
        self.assertTrue(
            any("example/main.tex" in e and "символічне" in e
                for e in r["errors"]), r["errors"]
        )

    def test_dangling_material_symlink_does_not_hide_in_metadata_only(self):
        b = self.make_book(material=False)
        (b / "missing.tex").symlink_to(self.root / "absent.tex")
        r = self.result()
        self.assertEqual(r["status"], "failed")
        self.assertEqual(r["books"][0]["state"], "blocked")
        self.assertTrue(any("missing.tex" in e for e in r["errors"]))

    def test_nested_directory_symlink_blocks_without_following(self):
        b = self.make_book(material=False)
        external = self.root / "private"
        external.mkdir()
        (external / "secret.tex").write_text("не читати", encoding="utf-8")
        (b / "include").symlink_to(external, target_is_directory=True)
        r = self.result()
        self.assertEqual(r["status"], "failed")
        self.assertTrue(any("example/include" in e for e in r["errors"]))

    def test_symlinked_passport_does_not_count_as_approved(self):
        b = self.make_book(material=False)
        target = self.root / "external-passport.md"
        target.write_text(PASSPORT, encoding="utf-8")
        (b / "PROVENANCE.md").unlink()
        (b / "PROVENANCE.md").symlink_to(target)
        r = self.result()
        self.assertEqual(r["status"], "failed")
        self.assertTrue(any("PROVENANCE.md" in e for e in r["errors"]))

    def test_symlinked_book_directory_blocks(self):
        external = self.root / "external-book"
        external.mkdir()
        (self.root / "books").mkdir()
        (self.root / "books" / "example").symlink_to(
            external, target_is_directory=True
        )
        r = self.result()
        self.assertEqual(r["status"], "failed")
        self.assertTrue(any("books/example" in e for e in r["errors"]))

    def test_gitkeep_symlink_is_not_permitted(self):
        books = self.root / "books"
        books.mkdir()
        (books / ".gitkeep").symlink_to(self.root / "absent.txt")
        r = self.result()
        self.assertEqual(r["status"], "failed")
        self.assertTrue(any(".gitkeep" in e for e in r["errors"]))

if __name__ == "__main__":
    unittest.main()
