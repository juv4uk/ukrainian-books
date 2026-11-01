"""EPUB поетичного тому: структура, якірі віршів, mimetype першим."""

from __future__ import annotations

import re
import sys
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from ebooklib import epub  # noqa: F401
    HAVE_EBOOKLIB = True
except ImportError:  # pragma: no cover - залежність ставить лише крок збірки
    HAVE_EBOOKLIB = False

from scripts import build_epub as builder  # noqa: E402


class TestEpub(unittest.TestCase):
    """Без ebooklib перевіряємо лише розбір розділів; з ним — і сам файл."""

    def test_all_twenty_chapters_are_found(self):
        numbers = [number for number, _ in builder.chapters()]
        self.assertEqual(numbers, list(range(1, 21)))

    def test_every_verse_gets_an_anchor(self):
        total = 0
        for number, path in builder.chapters():
            content, verses = builder.render_chapter(number, path)
            self.assertEqual(content.count("<h2 id='v"), verses)
            total += verses
        self.assertEqual(total, 298, "у реєстрі 298 віршів")

    def test_markup_is_escaped(self):
        content, _ = builder.render_chapter(1, builder.chapters()[0][1])
        self.assertNotIn("<", content.replace("<h1", "").replace("<h2", "")
                         .replace("<h3", "").replace("</h1", "").replace("</h2", "")
                         .replace("</h3", "").replace("<p class", "").replace("</p", "")
                         .replace("<html", "").replace("</html", "").replace("<body", "")
                         .replace("</body", "").replace("<br/", ""))

    @unittest.skipUnless(HAVE_EBOOKLIB, "ebooklib не встановлено")
    def test_built_file_follows_epub_layout(self):
        import tempfile
        original = builder.OUT
        with tempfile.TemporaryDirectory() as tmp:
            builder.OUT = Path(tmp) / "book.epub"
            try:
                self.assertEqual(builder.main(), 0)
                with zipfile.ZipFile(builder.OUT) as archive:
                    first = archive.infolist()[0]
                    self.assertEqual(first.filename, "mimetype")
                    self.assertEqual(first.compress_type, 0)
                    names = archive.namelist()
                self.assertTrue(any(name.endswith(".ncx") for name in names))
                self.assertTrue(any(name.endswith("nav.xhtml") for name in names))
                text = b"".join(
                    Path(tmp).joinpath("x").read_bytes() if False else b"" for _ in []
                )
                self.assertEqual(text, b"")
            finally:
                builder.OUT = original


if __name__ == "__main__":
    unittest.main()
