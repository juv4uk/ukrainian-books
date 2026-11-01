#!/usr/bin/env python3
"""Збирає EPUB поетичного перекладу «Аштавакра-ґіти» з розділів у Markdown.

Джерело — `books/ashtavakra-gita/poetychnyi/rozdil-N.md`, той самий, що й для
PDF-тому (`scripts/build_poetic_book.py`). Тут — окремий формат для читання
з телефона, а не заміна PDF.

Що перевіряється перед записом: кожен вірш отримує власний якір, і їх має
бути стільки ж, скільки віршів у реєстрі (298). Розбіжність — помилка.

Запуск:
    python3 scripts/build_epub.py
"""

from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

from ebooklib import epub

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "books" / "ashtavakra-gita" / "poetychnyi"
OUT = ROOT / "books" / "ashtavakra-poetychnyi" / "ashtavakra-poetychnyi.epub"

CHAPTER = re.compile(r"^#\s+Аштавакра-ґіта\.\s*Розділ\s+(\d+)", re.I)
VERSE = re.compile(r"^##\s+(\d+\.\d+)\s*$")
STYLE = (
    "body{font-family:serif;line-height:1.5;margin:1em}"
    "h1{font-size:1.4em;margin:1.2em 0 .6em}"
    "h2{font-size:.85em;color:#666;font-weight:normal;margin:1.4em 0 .3em}"
    "h3{font-size:1.05em;margin:1.6em 0 .5em}"
    ".stanza{margin:0 0 .9em;text-indent:0}"
    ".note{font-size:.9em;color:#333;margin:0 0 1em}"
)


def chapters() -> list[tuple[int, Path]]:
    found = []
    for path in SRC.glob("rozdil-*.md"):
        match = re.match(r"rozdil-(\d+)\.md$", path.name)
        if match:
            found.append((int(match.group(1)), path))
    return sorted(found)


def render_chapter(number: int, path: Path) -> tuple[str, int]:
    parts = [f"<h1>Розділ {number}</h1>"]
    stanza: list[str] = []
    mode = "verse"
    verses = 0

    def flush() -> None:
        if not stanza:
            return
        body = " ".join(html.escape(line) for line in stanza) if mode == "note" \
            else "<br/>".join(html.escape(line) for line in stanza)
        css = "note" if mode == "note" else "stanza"
        parts.append(f"<p class='{css}'>{body}</p>")
        stanza.clear()

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            flush()
            continue
        if CHAPTER.match(line) or line.startswith(">") or line.startswith("# "):
            continue
        match = VERSE.match(line)
        if match:
            flush()
            mode = "verse"
            verses += 1
            parts.append(f"<h2 id='v{match.group(1)}'>{match.group(1)}</h2>")
            continue
        if line.startswith("## "):
            flush()
            mode = "note"
            parts.append(f"<h3>{html.escape(line[3:])}</h3>")
            continue
        stanza.append(line)
    flush()
    return "<html><body>" + "".join(parts) + "</body></html>", verses


def main() -> int:
    book = epub.EpubBook()
    book.set_identifier("urn:juv4uk:ukrainian-books:ashtavakra-poetychnyi")
    book.set_title("Аштавакра-ґіта. Поетичний переклад українською")
    book.set_language("uk")
    book.add_author("редакція проєкту juv4uk/ukrainian-books")
    book.add_metadata("DC", "description",
        "Робоче пілотне видання. Поетичний переклад власний, не вивірений "
        "санскритологом і не рецензований. Ліцензія власного внеску — «ВОЛЬНІСТЬ».")

    items = []
    total = 0
    for number, path in chapters():
        content, verses = render_chapter(number, path)
        total += verses
        item = epub.EpubHtml(title=f"Розділ {number}",
                             file_name=f"rozdil-{number:02d}.xhtml", lang="uk")
        item.content = content
        book.add_item(item)
        items.append(item)

    style = epub.EpubItem(uid="style", file_name="style.css",
                          media_type="text/css", content=STYLE)
    book.add_item(style)
    for item in items:
        item.add_item(style)

    book.toc = tuple(items)
    book.spine = ["nav"] + items
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    OUT.parent.mkdir(parents=True, exist_ok=True)
    epub.write_epub(str(OUT), book)

    report = {"chapters": len(items), "verses": total, "bytes": OUT.stat().st_size}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if total != 298:
        print(f"ПОМИЛКА: віршів {total}, а в реєстрі 298", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
