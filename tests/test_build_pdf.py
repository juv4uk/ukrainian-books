"""ІНЖ-PDF: незалежні офлайнові регресії цілісності двох томів та SVG."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts import build_pdf


class PdfSourceTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.root = Path(self.tmpdir.name)

    def make_chapter(self, number: int, verses: list[int]) -> tuple[int, str]:
        path = self.root / f"rozdil-{number}.md"
        blocks = [f"# Розділ {number}"]
        for verse in verses:
            blocks.append(f"## {number}.{verse}\n\nОригінальний тестовий переклад.")
        path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
        return number, str(path)

    def test_inline_labeled_svg_is_real_image(self):
        folder = self.root / "ilustratsii"
        folder.mkdir()
        (folder / "13-7.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8"
        )
        source = (
            "**Ілюстрація.** ![Дві гілки](ilustratsii/13-7.svg) — "
            "Власна пояснювальна схема."
        )
        result = build_pdf.md_to_html(source, str(self.root), False)
        self.assertIn("<img ", result)
        self.assertIn('alt="Дві гілки"', result)
        self.assertIn("Власна пояснювальна схема.", result)
        self.assertNotIn("![Дві гілки]", result)

    def test_standalone_svg_still_works(self):
        (self.root / "test.svg").write_text("<svg/>", encoding="utf-8")
        result = build_pdf.md_to_html(
            "![Підпис](test.svg)", str(self.root), False
        )
        self.assertIn("<img ", result)

    def test_missing_svg_is_not_silently_lost(self):
        with self.assertRaisesRegex(ValueError, "Ілюстрацію не знайдено"):
            build_pdf.md_to_html(
                "**Ілюстрація.** ![Немає](ilustratsii/missing.svg)",
                str(self.root), False,
            )

    def test_complete_synthetic_volume(self):
        chapters = [self.make_chapter(1, [1, 2]),
                    self.make_chapter(2, [1])]
        expected = {(1, 1), (1, 2), (2, 1)}
        build_pdf.validate_volume(chapters, expected, "Тест", range(1, 3))

    def test_missing_chapter_rejected(self):
        chapters = [self.make_chapter(1, [1, 2])]
        with self.assertRaisesRegex(ValueError, "неповні глави"):
            build_pdf.validate_volume(
                chapters, {(1, 1), (1, 2), (2, 1)}, "Тест", range(1, 3)
            )

    def test_missing_verse_rejected_even_if_file_exists(self):
        chapters = [self.make_chapter(1, [1]),
                    self.make_chapter(2, [1])]
        with self.assertRaisesRegex(ValueError, "бракує"):
            build_pdf.validate_volume(
                chapters, {(1, 1), (1, 2), (2, 1)}, "Тест", range(1, 3)
            )

    def test_wrong_verse_rejected_with_same_total_count(self):
        chapters = [self.make_chapter(1, [1, 3]),
                    self.make_chapter(2, [1])]
        with self.assertRaisesRegex(ValueError, "зайві"):
            build_pdf.validate_volume(
                chapters, {(1, 1), (1, 2), (2, 1)}, "Тест", range(1, 3)
            )

    def test_duplicate_heading_rejected(self):
        one = self.make_chapter(1, [1, 1])
        two = self.make_chapter(2, [1])
        with self.assertRaisesRegex(ValueError, "дубльований вірш"):
            build_pdf.validate_volume(
                [one, two], {(1, 1), (2, 1)}, "Тест", range(1, 3)
            )

    def test_wrong_chapter_number_inside_file_rejected(self):
        one = self.make_chapter(1, [1])
        two = self.make_chapter(2, [1])
        Path(two[1]).write_text("## 1.2\n\nЧужий вірш.\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "неправильна глава"):
            build_pdf.validate_volume(
                [one, two], {(1, 1), (2, 1)}, "Тест", range(1, 3)
            )


    def test_actual_repository_has_both_complete_volumes(self):
        """Інтеграційна перевірка реальних 20+20 глав та ID усіх карток."""
        expected = build_pdf.expected_card_ids()
        scientific = build_pdf.chapter_files(r"^rozdil-(\d+)-naukove\.md$")
        poetic = build_pdf.chapter_files(r"^poetychnyi-rozdil-(\d+)\.md$")
        build_pdf.validate_volume(scientific, expected, "Науковий том")
        build_pdf.validate_volume(poetic, expected, "Поетичний том")

    def test_actual_chapter_10_renders_its_eight_svg_illustrations(self):
        """Поточний книжковий Markdown, а не лише вигаданий рядок тесту."""
        chapter = Path(build_pdf.BOOK) / "rozdil-10-naukove.md"
        source = chapter.read_text(encoding="utf-8")
        rendered = build_pdf.md_to_html(source, str(chapter.parent), False)
        self.assertEqual(rendered.count("<img "), 8)



if __name__ == "__main__":
    unittest.main()
