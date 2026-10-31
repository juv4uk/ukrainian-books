"""Офлайнові регресійні тести PDF-макета без залежності від WeasyPrint.

Служать для перевірки того, що наукові авторські SVG справді потрапляють
до HTML, а поетичний текст береться з єдиного редакторського каталогу.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import build_pdf


class ScientificIllustrationTests(unittest.TestCase):
    def test_inline_scientific_illustration_is_real_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            drawing = root / "ilustratsii" / "1-1.svg"
            drawing.parent.mkdir()
            drawing.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>',
                               encoding="utf-8")
            markdown = ("**Ілюстрація.** ![Три питання](ilustratsii/1-1.svg)"
                        " — Українська смислова схема.")
            output = build_pdf.md_to_html(markdown, str(root), False)
            self.assertIn("<strong>Ілюстрація.</strong>", output)
            self.assertIn('<img src="' + drawing.as_uri() + '"', output)
            self.assertIn("Українська смислова схема.", output)
            self.assertNotIn("![Три питання]", output)

    def test_standalone_image_still_renders(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            drawing = root / "схема.svg"
            drawing.write_text("<svg/>", encoding="utf-8")
            output = build_pdf.md_to_html("![Образ](схема.svg)", tmp, False)
            self.assertIn(drawing.as_uri(), output)
            self.assertNotIn("Ілюстрація недоступна", output)

    def test_image_attributes_are_escaped(self):
        with tempfile.TemporaryDirectory() as tmp:
            drawing = Path(tmp) / "рисунок.svg"
            drawing.write_text("<svg/>", encoding="utf-8")
            output = build_pdf.md_to_html(
                '![Пейзаж "мрії" & волі](рисунок.svg)', tmp, False
            )
            self.assertIn('alt="Пейзаж &quot;мрії&quot; &amp; волі"', output)

    def test_does_not_embed_file_outside_edition(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            edition = root / "edition"
            edition.mkdir()
            (root / "private.svg").write_text("<svg/>", encoding="utf-8")
            output = build_pdf.md_to_html(
                "![Зовнішній файл](../private.svg)", str(edition), False
            )
            self.assertNotIn("<img ", output)
            self.assertIn("Ілюстрація недоступна:", output)

    def test_missing_file_not_silently_omitted(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = build_pdf.md_to_html(
                "**Ілюстрація.** ![Невідома схема](ilustratsii/missing.svg)"
                " — Пояснювальний підпис.",
                tmp, False,
            )
            self.assertIn("Ілюстрація недоступна: Невідома схема", output)
            self.assertIn("Пояснювальний підпис.", output)


class OnePoeticEditionTests(unittest.TestCase):
    def test_only_editorial_poetic_directory_is_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            poems = root / "poetychnyi"
            poems.mkdir()
            (root / "poetychnyi-rozdil-1.md").write_text(
                "# Альтернативна редакція", encoding="utf-8"
            )
            for number in (20, 1, 2):
                (poems / f"rozdil-{number}.md").write_text(
                    "# Робоча поетична глава", encoding="utf-8"
                )
            (poems / "README.md").write_text("# Зміст", encoding="utf-8")
            with patch.object(build_pdf, "POETIC", str(poems)):
                picked = build_pdf.poetic_chapter_files()
            self.assertEqual([number for number, _ in picked], [1, 2, 20])
            self.assertTrue(all(Path(path).parent == poems for _, path in picked))


if __name__ == "__main__":
    unittest.main()
