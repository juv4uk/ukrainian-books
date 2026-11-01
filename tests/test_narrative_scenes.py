"""Наративні ілюстрації: підпис, привʼязка до вірша, відсутність чужих ресурсів.

Перевіряється саме те, що можна перевірити машиною: чи є чесний підпис, чи
названий вірш, чи немає у файлі зовнішніх посилань, вбудованих зображень і
`base64`, і чи стоїть сцена в книзі після схеми того самого вірша.

Чого ці тести **не** доводять: що малюнок гарний або що він точно передає
вірш. Це редакторське судження, і машина його не замінює.
"""
from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

from scripts import build_format_v2_chapter as builder
from scripts import build_narrative_scenes as scenes
from scripts import build_pdf

BOOK = Path(__file__).resolve().parents[1] / "books" / "ashtavakra-gita"
DIR = BOOK / "ilustratsii-naratyvni"
HONEST = "Наша ілюстрація до вірша {verse} — не історичне зображення"
SVG_NS = 'xmlns="http://www.w3.org/2000/svg"'
FORBIDDEN_TAGS = {"script", "image", "foreignObject", "iframe", "object", "embed"}


def registered() -> dict[str, dict]:
    data = json.loads((BOOK / "format-v2" / "scenes.json").read_text(encoding="utf-8"))
    return data["scenes"]


def svg_text(verse: str) -> str:
    return (DIR / registered()[verse]["file"]).read_text(encoding="utf-8")


class SceneRegistryTests(unittest.TestCase):
    def test_between_fifteen_and_twenty_five_scenes(self) -> None:
        count = len(registered())
        self.assertGreaterEqual(count, 15, "менше 15 сцен — це не «особливі місця»")
        self.assertLessEqual(count, 25, "більше 25 сцен — це вже всі вірші, а не вибір")

    def test_every_registered_file_exists_and_nothing_else_does(self) -> None:
        on_disk = {p.name for p in DIR.glob("*.svg")}
        listed = {item["file"] for item in registered().values()}
        self.assertEqual(on_disk, listed)

    def test_registry_is_current(self) -> None:
        self.assertEqual(scenes.check(), [], "запустіть python3 scripts/build_narrative_scenes.py")

    def test_every_scene_points_at_a_real_card(self) -> None:
        for verse in registered():
            with self.subTest(verse=verse):
                self.assertTrue((BOOK.parents[1] / "editorial" / "cards" / f"{verse}.json").is_file())

    def test_filename_and_caption_name_the_verse(self) -> None:
        for verse, item in registered().items():
            with self.subTest(verse=verse):
                self.assertTrue(item["file"].startswith(verse.replace(".", "-") + "-"),
                                f"{item['file']}: імʼя файлу не починається з номера вірша")
                self.assertIn(f"вірша {verse}", HONEST.format(verse=verse))
                self.assertTrue(item["caption"].strip(), "порожній підпис-сцена")


class SceneSvgTests(unittest.TestCase):
    def test_valid_xml(self) -> None:
        for verse in registered():
            with self.subTest(verse=verse):
                ET.fromstring(svg_text(verse))

    def test_honest_caption_inside_the_file(self) -> None:
        """Підпис мусить бути в самому файлі, а не лише в Markdown."""
        for verse in registered():
            with self.subTest(verse=verse):
                text = svg_text(verse)
                self.assertIn(HONEST.format(verse=verse), text)
                self.assertIn(f"вірша {verse}", text)

    def test_no_external_or_embedded_resources(self) -> None:
        for verse in registered():
            with self.subTest(verse=verse):
                # `xmlns` — це назва простору імен, а не адреса ресурсу; решта
                # «http» у файлі була б посиланням на чужий малюнок.
                text = svg_text(verse).replace(SVG_NS, "")
                for needle in ("http", "<image", "xlink:href", "base64", "data:"):
                    self.assertNotIn(needle, text, f"{verse}: знайдено {needle!r}")
                self.assertNotIn("<script", text)
                self.assertNotIn("@import", text)

    def test_no_scripts_handlers_or_links_in_the_tree(self) -> None:
        for verse in registered():
            with self.subTest(verse=verse):
                root = ET.fromstring(svg_text(verse))
                for node in root.iter():
                    name = node.tag.split("}")[-1]
                    self.assertNotIn(name, FORBIDDEN_TAGS, f"{verse}: елемент {name}")
                    for attr, value in node.attrib.items():
                        attr_name = attr.split("}")[-1].lower()
                        self.assertFalse(attr_name.startswith("on"),
                                         f"{verse}: обробник події {attr_name}")
                        self.assertNotEqual(attr_name, "href", f"{verse}: href")
                        self.assertNotIn("url(", value.lower(), f"{verse}: url()")

    def test_figures_are_silhouettes_without_faces(self) -> None:
        """Облич — немає: жодного кола-ока чи лінії-рота всередині голови."""
        for verse in registered():
            with self.subTest(verse=verse):
                text = svg_text(verse)
                self.assertNotIn("eye", text)
                self.assertNotIn("face", text)


class SceneInBookTests(unittest.TestCase):
    def test_scene_follows_schema_of_the_same_verse(self) -> None:
        for verse, item in registered().items():
            chapter, number = verse.split(".")
            page = BOOK / f"rozdil-{chapter}-naukove.md"
            with self.subTest(verse=verse):
                self.assertTrue(page.is_file(), f"немає сторінки глави {chapter}")
                lines = page.read_text(encoding="utf-8").splitlines()
                chunk = []
                inside = False
                for line in lines:
                    if re.fullmatch(rf"## {re.escape(verse)}\s*", line):
                        inside = True
                        continue
                    if inside and re.match(r"^## ", line):
                        break
                    if inside:
                        chunk.append(line)
                self.assertTrue(chunk, f"{verse}: немає розділу вірша на сторінці")
                body = "\n".join(chunk)
                schema = f"](ilustratsii/"
                scene = f"](ilustratsii-naratyvni/{item['file']})"
                self.assertIn(scene, body, f"{verse}: сцени немає в книзі")
                self.assertIn(schema, body, f"{verse}: сцени немає пари — схеми")
                self.assertLess(body.index(schema), body.index(scene),
                                f"{verse}: сцена мусить іти після схеми")
                self.assertIn(HONEST.format(verse=verse), body)
                self.assertIn(item["caption"].rstrip("."), body)

    def test_page_does_not_leak_citation_markers(self) -> None:
        for chapter in range(1, 21):
            page = BOOK / f"rozdil-{chapter}-naukove.md"
            with self.subTest(chapter=chapter):
                self.assertNotIn("[cite:", page.read_text(encoding="utf-8"))

    def test_verses_without_a_scene_keep_only_the_schema(self) -> None:
        """Глава 3 — без сцен: у ній немає жодного рядка «**Сцена.**»."""
        text = (BOOK / "rozdil-3-naukove.md").read_text(encoding="utf-8")
        self.assertNotIn("**Сцена.**", text)

    def test_latex_gets_the_scene_too(self) -> None:
        tex = (BOOK / "generated" / "rozdil-1.tex").read_text(encoding="utf-8")
        self.assertIn("ilustratsii-naratyvni/1-1-besida.pdf", tex)


class ScenePdfTests(unittest.TestCase):
    def test_markdown_scene_line_becomes_an_image(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "ilustratsii-naratyvni").mkdir()
            (root / "ilustratsii-naratyvni/1-1-besida.svg").write_text(
                '<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8")
            line = ("**Сцена.** ![Двоє сидять навпроти](ilustratsii-naratyvni/1-1-besida.svg)"
                    " — Двоє сидять навпроти. " + HONEST.format(verse="1.1"))
            html = build_pdf.md_to_html(line, str(root), False)
            self.assertIn("<img", html)
            self.assertIn("Двоє сидять навпроти", html)
            self.assertIn("<strong>Сцена.</strong>", html)


if __name__ == "__main__":
    unittest.main()
