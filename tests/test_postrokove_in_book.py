#!/usr/bin/env python3
"""ГЕН-04: перевірити, що построкові JSON-дані справді відтворені в книзі.

Не редагує файлів і не виконує PDF-генерацію. Порівнює лише построкові
фрагменти з чинним форматом; інші історичні частини глав не перезаписує.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import build_format_v2_chapter as builder  # noqa: E402

BOOK = ROOT / "books" / "ashtavakra-gita"


class PostrokoviInBookTests(unittest.TestCase):
    def test_every_registered_alignment_is_in_both_editions(self) -> None:
        found = 0
        for chapter in builder.chapters_with_cards():
            extra = builder.load_extra(chapter)
            markdown = (BOOK / f"rozdil-{chapter}-naukove.md").read_text(
                encoding="utf-8")
            latex = (BOOK / "generated" / f"rozdil-{chapter}.tex").read_text(
                encoding="utf-8")
            for card in builder.load_cards(chapter):
                data = builder.layers(card, extra, {})
                alignment = data["postrokovo"]
                if alignment is None:
                    continue

                found += 1
                ident = str(card["id"])
                with self.subTest(verse=ident):
                    mark = f"## {ident}\n"
                    self.assertEqual(markdown.count(mark), 1)
                    md_verse = markdown.split(mark, 1)[1].split("\n## ", 1)[0]
                    expected_md = builder.render_markdown_alignment(alignment).strip()
                    self.assertIn(expected_md, md_verse,
                                  "Построкові дані є в JSON, але відсутні в Markdown")

                    start = rf"\vsec{{{ident}}}" + "\n"
                    self.assertEqual(latex.count(start), 1)
                    tex_verse = latex.split(start, 1)[1].split("\n\\vsec{", 1)[0]
                    expected_tex = [
                        r"\vcom{%s}" % builder.esc(
                            "Построкове зіставлення: редакторська чернетка, не рецензовано.")
                    ]
                    for line in alignment["lines"]:
                        expected_tex += [
                            r"\vcom{%s}" % builder.esc("Рядок " + line["label"]),
                            r"\vdeva{%s}" % builder.esc(line["devanagari"]),
                            r"\vtranslit{%s}" % builder.esc(line["transliteration"]),
                            r"\vperek{%s}" % builder.esc(line["translation"]),
                            r"\vcom{%s}" % builder.esc(line["commentary"]),
                        ]
                    self.assertIn("\n".join(expected_tex), tex_verse,
                                  "Построкові дані є в JSON, але LaTeX не оновлено")
        self.assertGreaterEqual(found, 2, "Мають бути щонайменше пілоти 4.1 та 11.1")


if __name__ == "__main__":
    unittest.main()
