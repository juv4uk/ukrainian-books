#!/usr/bin/env python3
"""Зібрати «Аштавакра-ґіту» в один PDF.

Рушій — WeasyPrint (HTML→PDF), не XeLaTeX: у цій пісочниці немає робочого
XeLaTeX (LuaTeX без luaotfload, а CTAN недоступний для tlmgr). Тому збірка
йде іншим рушієм, і це сказано прямо в колофоні книги, а не приховано.

Джерела — згенеровані файли книги:
  books/ashtavakra-gita/rozdil-N-naukove.md   (20 розділів, пʼять шарів)
  books/ashtavakra-gita/poetychnyi/rozdil-N.md (20 розділів, поезія)
  books/ashtavakra-gita/ZMIST.md
"""

import html
import os
import re
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOOK = os.path.join(ROOT, "books", "ashtavakra-gita")
POETIC = os.path.join(BOOK, "poetychnyi")

CSS = """
@page {
  size: A5;
  margin: 16mm 14mm 18mm 16mm;
  @bottom-center { content: counter(page); font-size: 8pt; color: #666; }
  @top-center { content: string(running); font-size: 8pt; color: #888; }
}
@page :first { @bottom-center { content: none; } @top-center { content: none; } }

html { font-family: "DejaVu Serif", "Noto Serif Devanagari", serif;
       font-size: 9.6pt; line-height: 1.38; color: #1b1b1b; }
body { margin: 0; }

h1 { string-set: running content(); font-size: 15pt; line-height: 1.2;
     margin: 0 0 8pt 0; padding-bottom: 4pt;
     border-bottom: 0.6pt solid #999; page-break-before: always; }
h1.first { page-break-before: avoid; }
h2 { font-size: 10.5pt; margin: 10pt 0 3pt 0; page-break-after: avoid; }
p { margin: 0 0 5pt 0; text-align: justify; hyphens: auto; }

blockquote { margin: 0 0 8pt 0; padding: 5pt 7pt; background: #f6f3ec;
             border-left: 2pt solid #c9b98f; font-size: 8.8pt; }
blockquote p { margin: 0 0 3pt 0; text-align: left; hyphens: none; }

img { max-width: 100%; display: block; margin: 5pt auto 2pt auto; }

.title-page { text-align: center; page-break-after: always; padding-top: 40mm; }
.title-page h1 { border: none; page-break-before: avoid; font-size: 22pt;
                 string-set: none; margin-bottom: 4mm; }
.title-page .sub { font-size: 11pt; color: #444; margin-bottom: 14mm; }
.title-page .meta { font-size: 8.6pt; color: #666; margin-top: 30mm;
                    text-align: left; line-height: 1.5; }

.poetry { page-break-before: always; }
.poetry h2 { margin-top: 12pt; }
.poetry p { text-align: left; margin-bottom: 8pt; }
.poetry blockquote { display: none; }
hr { border: none; margin: 6pt 0; }
"""


def esc(t: str) -> str:
    return html.escape(t, quote=False)


def inline(t: str) -> str:
    """Мінімальний markdown: **жирний**, *курсив*, `код`."""
    t = esc(t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t, flags=re.S)
    t = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    return t


def md_to_html(text: str, base: str, poetry: bool) -> str:
    out = []
    lines = text.split("\n")
    i = 0
    quote = []
    para = []

    def flush_para():
        if para:
            out.append("<p>" + inline(" ".join(para).strip()) + "</p>")
            para.clear()

    def flush_quote():
        if quote:
            out.append("<blockquote>" + "".join(quote) + "</blockquote>")
            quote.clear()

    while i < len(lines):
        line = lines[i]
        s = line.strip()

        if not s:
            flush_para(); flush_quote(); i += 1; continue

        m = re.match(r"^(#{1,3})\s+(.*)$", s)
        if m:
            flush_para(); flush_quote()
            level, title = len(m.group(1)), m.group(2)
            if level == 1:
                cls = ' class="first"' if not out else ""
                out.append(f"<h1{cls}>{inline(title)}</h1>")
            elif level == 2:
                out.append(f"<h2>{inline(title)}</h2>")
            else:
                out.append(f"<h3>{inline(title)}</h3>")
            i += 1; continue

        if s.startswith(">"):
            flush_para()
            quote.append("<p>" + inline(s.lstrip("> ").strip()) + "</p>")
            i += 1; continue

        # Генератор наукових глав ставить SVG після мітки **Ілюстрація.**.
        # Розпізнаємо і цей формат, і окремий Markdown-рисунок.
        m = re.fullmatch(
            r"(?:\*\*Ілюстрація\.\*\*\s+)?!\[([^\]]*)\]\(([^)]+)\)"
            r"(?:\s*—\s*(.*))?", s
        )
        if m:
            flush_para(); flush_quote()
            alt, src, caption = m.group(1), m.group(2), (m.group(3) or "")
            if s.startswith("**Ілюстрація.**"):
                out.append("<p><strong>Ілюстрація.</strong></p>")
            root = Path(base).resolve()
            path = (root / src).resolve()
            # Лише власні локальні ілюстрації цього тому, без ../../ і URI.
            if root in path.parents and path.is_file():
                out.append(f'<img src="{html.escape(path.as_uri(), quote=True)}" '
                           f'alt="{html.escape(alt, quote=True)}">')
            else:
                out.append("<p>Ілюстрація недоступна: " + esc(alt) + "</p>")
            if caption:
                out.append('<p style="font-size:8pt;color:#555;text-align:center">'
                           + inline(caption) + "</p>")
            i += 1; continue

        if set(s) <= set("-*_") and len(s) >= 3:
            flush_para(); flush_quote()
            out.append("<hr>")
            i += 1; continue

        if s.startswith("|"):
            flush_para(); flush_quote()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(lines[i].strip()); i += 1
            cells = [[c.strip() for c in r.strip("|").split("|")] for r in rows]
            cells = [c for c in cells if not all(set(x) <= set("-: ") for x in c)]
            if cells:
                out.append('<table style="width:100%;font-size:8.4pt;border-collapse:collapse;margin-bottom:6pt">')
                for n, row in enumerate(cells):
                    tag = "th" if n == 0 else "td"
                    style = ' style="border-bottom:0.4pt solid #ccc;padding:2pt 3pt;text-align:left"'
                    out.append("<tr>" + "".join(f"<{tag}{style}>{inline(c)}</{tag}>" for c in row) + "</tr>")
                out.append("</table>")
            continue

        para.append(s)
        i += 1

    flush_para(); flush_quote()
    return "\n".join(out)


def chapter_files(pattern: str, directory: str = BOOK) -> list[tuple[int, str]]:
    found = []
    for name in os.listdir(directory):
        m = re.match(pattern, name)
        if m:
            found.append((int(m.group(1)), os.path.join(directory, name)))
    return sorted(found)


def poetic_chapter_files() -> list[tuple[int, str]]:
    """Книжковий поетичний том — лише з однієї редакторської теки."""
    return chapter_files(r"^rozdil-(\d+)\.md$", POETIC)


def main() -> int:
    out_pdf = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "ashtavakra.pdf")

    parts = []
    parts.append("""<div class="title-page">
<h1>Аштавакра-ґіта</h1>
<div class="sub">український науково-редакторський макет<br>з окремою поетичною чернеткою</div>
<div class="meta">
Двадцять глав, 298 віршів.<br>
Науковий том: деванагарі, українська транслітерація, переклад,
науковий коментар з українськими паралелями, власна схема.<br>
Поетичний том: наш поетичний переклад усієї книги.<br><br>
Санскритське читання звірене за SARIT і GRETIL; деванагарі й транслітерація —
механічні, з редакторських карток.<br>
Власні українські внески — за ліцензією «ВОЛЬНІСТЬ».<br>
Це редакторська чернетка; незалежну санскритологічну рецензію й права
на відтворення електронних санскритських свідків не підтверджено.<br><br>
Зібрано рушієм WeasyPrint: у середовищі збірки немає робочого XeLaTeX.<br>
Це не критичне видання й не факсиміле.
</div>
</div>""")

    zmist = os.path.join(BOOK, "ZMIST.md")
    if os.path.exists(zmist):
        parts.append(md_to_html(open(zmist, encoding="utf-8").read(), BOOK, False))

    for num, path in chapter_files(r"^rozdil-(\d+)-naukove\.md$"):
        parts.append(md_to_html(open(path, encoding="utf-8").read(), BOOK, False))

    parts.append('<div class="poetry"><h1>Поетичний переклад</h1>'
                 "<p>Окремий том. Це не науковий переклад: тут дозволено стиснути, "
                 "переставити, замінити термін на образ — але не додати думки, "
                 "якої у вірші немає. У спірних місцях правий науковий том.</p></div>")

    for num, path in poetic_chapter_files():
        html_part = md_to_html(open(path, encoding="utf-8").read(), POETIC, True)
        parts.append(f'<div class="poetry">{html_part}</div>')

    doc = ("<!DOCTYPE html><html lang=\"uk\"><head><meta charset=\"utf-8\">"
           f"<style>{CSS}</style></head><body>" + "\n".join(parts) + "</body></html>")

    html_path = os.path.join(ROOT, "ashtavakra.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(doc)

    from weasyprint import HTML
    HTML(filename=html_path).write_pdf(out_pdf)
    print("PDF:", out_pdf, os.path.getsize(out_pdf), "байт")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
