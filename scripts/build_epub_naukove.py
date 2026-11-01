#!/usr/bin/env python3
"""Зібрати EPUB наукового тому «Аштавакра-ґіти».

Науковий том містить деванагарі, тому шрифт мусить їхати **всередині**
архіву: читач не має нічого доставляти. Використано Noto Serif Devanagari
(OFL 1.1); текст ліцензії кладеться в архів поруч зі шрифтом, як вимагає
сама ліцензія.

Джерело — `books/ashtavakra-gita/rozdil-N-naukove.md`.
Вихід — `books/ashtavakra-gita/ashtavakra-naukove.epub` (тека має
PROVENANCE.md, який дозволяє EPUB для власного внеску).

Запуск:
    python3 scripts/build_epub_naukove.py
"""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path

from ebooklib import epub

ROOT = Path(__file__).resolve().parents[1]
BOOK = ROOT / "books" / "ashtavakra-gita"
OUT = BOOK / "ashtavakra-naukove.epub"
FONT = Path("/usr/share/fonts/truetype/noto/NotoSerifDevanagari-Regular.ttf")
OFL = Path("/tmp/OFL.txt")

VERSE = re.compile(r"^##\s+(\d+\.\d+)\s*$")
CHAPTER = re.compile(r"^#\s+(.+)$")

CSS = """
@font-face {
  font-family: "Noto Serif Devanagari";
  src: url("../NotoSerifDevanagari-Regular.ttf");
  font-weight: normal;
  font-style: normal;
}
body { font-family: serif; line-height: 1.55; margin: 0.8em; }
h1 { font-size: 1.35em; margin: 1.1em 0 0.5em; }
h2 { font-size: 0.95em; color: #555; font-weight: normal; margin: 1.3em 0 0.3em; }
.deva { font-family: "Noto Serif Devanagari", serif; font-size: 1.15em; }
blockquote { margin: 0.6em 0; padding-left: 0.7em; border-left: 2px solid #ccc;
             color: #444; font-size: 0.94em; text-align: left; }
img { max-width: 100%; height: auto; }
figure { margin: 0.8em 0; }
figcaption { font-size: 0.85em; color: #666; }
"""


def esc(text: str) -> str:
    return html.escape(text, quote=False)


def inline(text: str) -> str:
    text = esc(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    # деванагарі — окремим класом, щоб шрифт застосувався саме до нього
    return re.sub(r"([\u0900-\u097F][\u0900-\u097F\s\u200c\u200d]*[\u0900-\u097F]|[\u0900-\u097F])",
                  r'<span class="deva">\1</span>', text)


def to_html(md: str, chapter: int) -> tuple[str, list[str]]:
    """Мінімальний конвертер: заголовки, врізки, картинки, абзаци."""
    out: list[str] = []
    verses: list[str] = []
    para: list[str] = []
    quote: list[str] = []

    def flush_para() -> None:
        if para:
            out.append("<p>" + inline(" ".join(para)) + "</p>")
            para.clear()

    def flush_quote() -> None:
        if quote:
            out.append("<blockquote>" + inline(" ".join(quote)) + "</blockquote>")
            quote.clear()

    for raw in md.splitlines():
        line = raw.rstrip()
        if not line.strip():
            flush_para()
            flush_quote()
            continue
        if line.startswith("# "):
            flush_para(); flush_quote()
            out.append(f"<h1>{inline(line[2:].strip())}</h1>")
            continue
        m = VERSE.match(line)
        if m:
            flush_para(); flush_quote()
            verse = m.group(1)
            verses.append(verse)
            anchor = verse.replace(".", "-")
            out.append(f'<h2 id="v{anchor}">{esc(verse)}</h2>')
            continue
        if line.startswith(">"):
            flush_para()
            quote.append(line.lstrip("> ").strip())
            continue
        img = re.search(r"!\[(.*?)\]\((.*?)\)", line)
        if img:
            flush_para(); flush_quote()
            alt, src = img.group(1), img.group(2)
            name = Path(src).name
            caption = re.sub(r"^—\s*", "", line[img.end():].strip())
            fig = f'<figure><img src="images/{name}" alt="{esc(alt)}"/>'
            if caption:
                fig += f"<figcaption>{inline(caption)}</figcaption>"
            fig += "</figure>"
            out.append(fig)
            continue
        if line.strip() in ("---", "***"):
            flush_para(); flush_quote()
            continue
        para.append(line.strip())
    flush_para(); flush_quote()
    return "\n".join(out), verses


def main() -> int:
    sources = sorted(BOOK.glob("rozdil-*-naukove.md"),
                     key=lambda p: int(re.search(r"rozdil-(\d+)-", p.name).group(1)))
    if len(sources) != 20:
        print(f"ПОМИЛКА: наукових глав {len(sources)}, треба 20", file=sys.stderr)
        return 1
    if not FONT.is_file():
        print(f"ПОМИЛКА: немає шрифту {FONT}", file=sys.stderr)
        return 1

    book = epub.EpubBook()
    book.set_identifier("ukrainian-books-ashtavakra-naukove")
    book.set_title("Аштавакра-ґіта. Наукове представлення українською")
    book.set_language("uk")

    css = epub.EpubItem(uid="style", file_name="style/main.css",
                        media_type="text/css", content=CSS)
    book.add_item(css)

    font = epub.EpubItem(uid="font-deva", file_name="NotoSerifDevanagari-Regular.ttf",
                         media_type="font/ttf", content=FONT.read_bytes())
    book.add_item(font)
    if OFL.is_file():
        book.add_item(epub.EpubItem(uid="ofl", file_name="OFL.txt",
                                    media_type="text/plain", content=OFL.read_bytes()))

    # ілюстрації: ті самі SVG, що в книзі
    images: set[str] = set()
    chapters: list[epub.EpubHtml] = []
    total_verses = 0
    for path in sources:
        number = int(re.search(r"rozdil-(\d+)-", path.name).group(1))
        md = path.read_text(encoding="utf-8")
        body, verses = to_html(md, number)
        total_verses += len(verses)
        for m in re.finditer(r"!\[[^\]]*\]\(([^)]+\.svg)\)", md):
            images.add(m.group(1))
        item = epub.EpubHtml(title=f"Розділ {number}", file_name=f"rozdil-{number:02d}.xhtml",
                             lang="uk")
        item.content = (f'<html><head><link rel="stylesheet" href="style/main.css"/></head>'
                        f"<body>{body}</body></html>")
        item.add_item(css)
        book.add_item(item)
        chapters.append(item)

    flat: dict[str, str] = {}
    for rel in sorted(images):
        src = BOOK / rel
        if not src.is_file():
            print(f"УВАГА: посилання в порожнечу {rel}", file=sys.stderr)
            continue
        name = Path(rel).name
        if name in flat and flat[name] != rel:
            # однакові імена в різних теках — не змішувати
            name = rel.replace("/", "-")
        flat[name] = rel
    for name, rel in sorted(flat.items()):
        src = BOOK / rel
        book.add_item(epub.EpubItem(uid=f"img-{name}", file_name=f"images/{name}",
                                    media_type="image/svg+xml", content=src.read_bytes()))

    colophon = epub.EpubHtml(title="Вихідні дані", file_name="colophon.xhtml", lang="uk")
    colophon.content = (
        '<html><head><link rel="stylesheet" href="style/main.css"/></head><body>'
        "<h1>Вихідні дані</h1>"
        "<p>Науковий том: деванагарі, українська транслітерація, переклад, "
        "науковий коментар з українськими паралелями, власна схема.</p>"
        "<p>Деванагарі й транслітерація — механічні, з редакторських карток; "
        "це не критичне видання.</p>"
        '<p>Шрифт деванагарі: Noto Serif Devanagari, ліцензія SIL Open Font '
        'License 1.1. Текст ліцензії — у файлі <code>OFL.txt</code> всередині '
        "цього архіву.</p>"
        "</body></html>")
    colophon.add_item(css)
    book.add_item(colophon)

    book.toc = tuple(chapters) + (colophon,)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav"] + chapters + [colophon]

    epub.write_epub(str(OUT), book)
    print({"chapters": len(chapters), "verses": total_verses,
           "images": len(images), "bytes": OUT.stat().st_size})
    return 0


if __name__ == "__main__":
    sys.exit(main())
