"""EPUB поетичного тому: розбір розділів, якорі віршів, будова архіву."""

from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from ebooklib import epub  # noqa: F401
    from scripts import build_epub as builder  # noqa: E402
    HAVE_EBOOKLIB = True
except ImportError:  # залежність ставить лише крок збірки
    HAVE_EBOOKLIB = False
    builder = None


@unittest.skipUnless(HAVE_EBOOKLIB, "ebooklib не встановлено")
class TestEpub(unittest.TestCase):
    def test_all_twenty_chapters_are_found(self):
        self.assertEqual([n for n, _ in builder.chapters()], list(range(1, 21)))

    def test_every_verse_gets_an_anchor(self):
        total = 0
        for number, path in builder.chapters():
            content, verses = builder.render_chapter(number, path)
            self.assertEqual(content.count("<h2 id='v"), verses)
            total += verses
        self.assertEqual(total, 298, "у реєстрі 298 віршів")

    def test_markup_is_escaped(self):
        content, _ = builder.render_chapter(*builder.chapters()[0])
        self.assertNotIn("<script", content)
        self.assertNotIn("<&", content)

    def test_built_file_follows_epub_layout(self):
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
                self.assertTrue(any(n.endswith(".ncx") for n in names))
                self.assertTrue(any(n.endswith("nav.xhtml") for n in names))
            finally:
                builder.OUT = original


if __name__ == "__main__":
    unittest.main()
