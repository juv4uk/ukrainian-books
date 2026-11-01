#!/usr/bin/env python3
"""Складальна машина ФОРМАТ-02: шість шарів на вірш + поетичний переклад.

Машина працює для **всіх 298 віршів**, а не лише для глави 1. Для будь-якої
глави, де є картки, вона складає шари, які є в даних, у порядку
`docs/FORMAT_V2.md`:

1. **деванагарі** — механічно з поля `iast` (`scripts/iast_to_devanagari.py`);
2. **IAST** — латинська транслітерація з картки, поле `iast`, як є;
3. **українська транслітерація** — механічно з `iast` (`scripts/iast_to_ukrainian.py`);
4. **переклад** — з картки, поле `ukrainian_translation`;
5. **коментар** — з картки, поле `commentary`, плюс зареєстрована
   українська паралель (`books/ashtavakra-gita/paraleli.json`), якщо вона є;
6. **ілюстрація** — власна схема з `ilustratsii/`, якщо вона є.

Ті самі шість шарів ідуть і у верстку: макрос `\vdeva` (деванагарі),
`\viast` (IAST), `\vtranslit` (українська транслітерація), `\vperek`
(переклад), `\vcom` (коментар), `\vfig` (ілюстрація). Шар IAST довго був
лише в Markdown — тепер він є і в `.tex`, і в PDF.

Маркери шарів (`**Деванагарі.**`, `**IAST.**`, `**Українська транслітерація.**`,
`**Переклад.**`, `**Коментар.**`) — це контракт із
`scripts/check_scholarly_pages.py`: перевірка вимагає саме їх і саме в цьому
порядку. Змінювати маркер тут, не змінивши перевірку, не можна — це ловить
`tests/test_scholarly_pages_match_generator.py`.

Чого машина **не** робить: не вигадує перекладу, коментаря, паралелі чи
схеми. Немає даних — немає шару, і це видно в звіті, а не приховано.

Вихід:
  `books/ashtavakra-gita/rozdil-N-naukove.md`  — наукове представлення глави;
  `books/ashtavakra-gita/generated/rozdil-N.tex` — те саме для XeLaTeX;
  `books/ashtavakra-gita/generated/poetychnyi-N.tex` — поетичний переклад.

Вжиток:
    python3 scripts/build_format_v2_chapter.py --chapter 1
    python3 scripts/build_format_v2_chapter.py --all
    python3 scripts/build_format_v2_chapter.py --check
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.iast_to_devanagari import to_devanagari  # noqa: E402
from scripts.iast_to_ukrainian import to_ukrainian  # noqa: E402
from scripts.postrokove import prepare_alignment, render_markdown_alignment  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BOOK = ROOT / "books" / "ashtavakra-gita"
CARDS = ROOT / "editorial" / "cards"
EXTRA = BOOK / "format-v2"
POETIC = BOOK / "poetychnyi"
GENERATED = BOOK / "generated"
PARALLELS = BOOK / "paraleli.json"
SCENES = BOOK / "format-v2" / "scenes.json"
ILUSTRATSII = "ilustratsii"
SCENES_DIR = "ilustratsii-naratyvni"

HONEST = "Схема наша, не історична ілюстрація."
# Наративна ілюстрація — не схема поняття, а сцена; підпис інший і чесний.
HONEST_SCENE = "Наша ілюстрація до вірша {verse} — не історичне зображення."

HEADER = """# Аштавакра-ґіта. Глава {chapter}. Наукове представлення

> ФОРМАТ-02: кожен вірш подано шістьма шарами — деванагарі, IAST, українська
> транслітерація, переклад, науковий коментар з українськими паралелями,
> ілюстрація. Плюс окремо — поетичний переклад (`poetychnyi/rozdil-{chapter}.md`).
>
> **IAST** — те, що записано в картці (поле `iast`), без редакторських
> поправок: це єдиний шар, який не перераховується скриптом.
> **Деванагарі тут — механічна** транслітерація поля `iast` з картки
> (`scripts/iast_to_devanagari.py`), а не окреме читання за рукописом.
> **Українська транслітерація** — теж механічна (`scripts/iast_to_ukrainian.py`,
> таблиця в `docs/TRANSLITERATSIIA.md`).
> **Українські паралелі** — наша інтерпретація, а не твердження про вплив;
> реєстр і правила — `paraleli.json` і `scripts/check_ukrainian_parallels.py`.
> **Схеми** — наші власні; жодна не є історичною ілюстрацією.
> **Сцени** (`ilustratsii-naratyvni/`) — теж наші власні малюнки й теж не
> історичні: це ситуація вірша, а не поняття, і фігури там — силуети без
> облич.
>
> Цей файл згенеровано; правити треба картки й `format-v2/rozdil-{chapter}.json`,
> а не його.
"""


# ---------------------------------------------------------------------------
# Завантаження даних
# ---------------------------------------------------------------------------

def normalise(value: object) -> str | None:
    """Згорнути пробіли й переноси рядків у тексті картки.

    У картках подекуди трапляються керівні послідовності ``\\n``: у JSON вони
    декодуються в справжній переніс рядка, і тоді один абзац розсипається на
    кілька рядків усередині макроса. Для верстки це дефект, тому текст
    згортається до одного пробілу.
    """
    if not isinstance(value, str):
        return None
    text = " ".join(value.split())
    return text or None


def load_cards(chapter: int) -> list[dict]:
    picked: list[dict] = []
    for path in sorted(CARDS.glob(f"{chapter}.*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("id"):
            picked.append(data)
    picked.sort(key=lambda c: int(str(c["id"]).split(".")[1]))
    return picked


def load_extra(chapter: int) -> dict:
    path = EXTRA / f"rozdil-{chapter}.json"
    if not path.is_file():
        return {"chapter": chapter, "intro": "", "verses": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def load_parallels() -> dict[str, dict]:
    if not PARALLELS.is_file():
        return {}
    data = json.loads(PARALLELS.read_text(encoding="utf-8"))
    return {str(item["id"]): item for item in data.get("parallels", [])}


def load_scenes() -> dict[str, dict]:
    """Наративні ілюстрації: вірш → файл і підпис. Немає файлу — немає шару."""
    if not SCENES.is_file():
        return {}
    data = json.loads(SCENES.read_text(encoding="utf-8"))
    return {str(k): v for k, v in (data.get("scenes") or {}).items()}


def load_poetic(chapter: int) -> dict[str, list[str]]:
    """Розібрати поетичний переклад: ``## 1.1`` → рядки вірша."""
    path = POETIC / f"rozdil-{chapter}.md"
    if not path.is_file():
        return {}
    poems: dict[str, list[str]] = {}
    current: str | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"##\s+(\d+\.\d+)\s*", line)
        if match:
            current = match.group(1)
            poems[current] = []
            continue
        if current is None:
            continue
        if line.startswith("#"):
            current = None
            continue
        if line.strip():
            poems[current].append(line.strip())
    return poems


# ---------------------------------------------------------------------------
# Один вірш
# ---------------------------------------------------------------------------

def layers(card: dict, extra: dict, parallels: dict[str, dict],
           scenes: dict[str, dict] | None = None) -> dict:
    """Зібрати шари одного вірша. Відсутні шари позначаються як відсутні."""
    ident = str(card["id"])
    iast = card.get("iast")
    entry = (extra.get("verses") or {}).get(ident) or {}
    result = {
        "id": ident,
        "postrokovo": prepare_alignment(card, entry),
        "devanagari": to_devanagari(iast, where=f"картці {ident}") if iast else None,
        "iast": normalise(iast),
        "transliteration": to_ukrainian(iast, where=f"картці {ident}") if iast else None,
        "translation": normalise(card.get("ukrainian_translation")),
        "commentary": normalise(card.get("commentary")),
        "parallel": parallels.get(str(entry.get("parallel") or "")),
        "illustration": entry.get("illustration"),
        "scene": (scenes or {}).get(ident),
    }
    return result


def render_markdown_verse(data: dict) -> str:
    out = [f"## {data['id']}", ""]
    if data["devanagari"]:
        out += [f"**Деванагарі.** {data['devanagari']}", ""]
    if data.get("iast"):
        out += [f"**IAST.** {data['iast']}", ""]
    if data["transliteration"]:
        out += [f"**Українська транслітерація.** {data['transliteration']}", ""]
    if data["translation"]:
        out += [f"**Переклад.** {data['translation']}", ""]
    if data["postrokovo"]:
        out += [render_markdown_alignment(data["postrokovo"]), ""]
    if data["commentary"]:
        out += [f"**Коментар.** {data['commentary']}", ""]
    parallel = data["parallel"]
    if parallel:
        label = {
            "наша паралель": "Українська паралель (наша інтерпретація, не твердження про вплив)",
            "цитата": "Українська паралель (перевірена цитата)",
            "ПОТРЕБУЄ ПЕРЕВІРКИ": "Українська паралель (ПОТРЕБУЄ ПЕРЕВІРКИ)",
        }.get(parallel.get("kind"), "Українська паралель")
        body = f"*{parallel['figure']}*, {parallel['work']}. {parallel['text']}"
        if parallel.get("kind") == "цитата":
            body += (f"\n\n> «{parallel['quote']}»\n>\n> — {parallel['quote_section']}. "
                     f"{parallel['quote_edition']}. {parallel['quote_url']} "
                     f"(перевірено {parallel['quote_checked_on']})")
        out += [f"**{label}.** {body}", ""]
    if data["illustration"]:
        caption = data["illustration"].get("caption") or ""
        file = data["illustration"]["file"]
        out += [f"**Ілюстрація.** ![{caption}]({ILUSTRATSII}/{file}) — "
                f"{caption.rstrip('.')}. {HONEST}", ""]
    scene = data.get("scene")
    if scene:
        caption = scene.get("caption") or ""
        file = scene["file"]
        honest = HONEST_SCENE.format(verse=data["id"])
        out += [f"**Сцена.** ![{caption}]({SCENES_DIR}/{file}) — "
                f"{caption.rstrip('.')}. {honest}", ""]
    return "\n".join(out)


LATEX_SPECIAL = {
    "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
    "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def esc(text: str) -> str:
    return "".join(LATEX_SPECIAL.get(ch, ch) for ch in text)


def render_latex_verse(data: dict) -> str:
    parts = [r"\vsec{%s}" % esc(data["id"])]
    if data["devanagari"]:
        parts.append(r"\vdeva{%s}" % esc(data["devanagari"]))
    if data.get("iast"):
        parts.append(r"\viast{%s}" % esc(data["iast"]))
    if data["transliteration"]:
        parts.append(r"\vtranslit{%s}" % esc(data["transliteration"]))
    if data["translation"]:
        parts.append(r"\vperek{%s}" % esc(data["translation"]))
    if data["postrokovo"]:
        parts.append(r"\vcom{%s}" % esc("Построкове зіставлення: редакторська чернетка, не рецензовано."))
        for line in data["postrokovo"]["lines"]:
            parts.append(r"\vcom{%s}" % esc("Рядок " + line["label"]))
            parts.append(r"\vdeva{%s}" % esc(line["devanagari"]))
            parts.append(r"\viast{%s}" % esc(line["iast"]))
            parts.append(r"\vtranslit{%s}" % esc(line["transliteration"]))
            parts.append(r"\vperek{%s}" % esc(line["translation"]))
            parts.append(r"\vcom{%s}" % esc(line["commentary"]))
    if data["commentary"]:
        parts.append(r"\vcom{%s}" % esc(data["commentary"]))
    parallel = data["parallel"]
    if parallel:
        kind = parallel.get("kind")
        label = {
            "наша паралель": "Українська паралель (наша інтерпретація)",
            "цитата": "Українська паралель (перевірена цитата)",
            "ПОТРЕБУЄ ПЕРЕВІРКИ": "Українська паралель (ПОТРЕБУЄ ПЕРЕВІРКИ)",
        }.get(kind, "Українська паралель")
        head = f"{parallel['figure']}, {parallel['work']}."
        parts.append(r"\vpar{%s}{%s}{%s}" % (esc(label), esc(head), esc(parallel["text"])))
        if kind == "цитата":
            parts.append(r"\vquot{%s}{%s}{%s}{%s}" % (
                esc(parallel["quote"]), esc(parallel["quote_section"]),
                esc(parallel["quote_edition"]), esc(parallel["quote_url"])))
    illustration = data["illustration"]
    if illustration:
        pdf = str(Path(illustration["file"]).with_suffix(".pdf"))
        parts.append(r"\vfig{%s}{%s}{%s}" % (
            ILUSTRATSII + "/" + pdf, esc(illustration.get("caption") or ""), esc(HONEST)))
    scene = data.get("scene")
    if scene:
        pdf = str(Path(scene["file"]).with_suffix(".pdf"))
        parts.append(r"\vfig{%s}{%s}{%s}" % (
            SCENES_DIR + "/" + pdf, esc(scene.get("caption") or ""),
            esc(HONEST_SCENE.format(verse=data["id"]))))
    return "\n".join(parts) + "\n"


# ---------------------------------------------------------------------------
# Глава
# ---------------------------------------------------------------------------

def build_markdown(chapter: int) -> str:
    cards = load_cards(chapter)
    extra = load_extra(chapter)
    parallels = load_parallels()
    scenes = load_scenes()
    body = [HEADER.format(chapter=chapter)]
    if extra.get("title"):
        body += [f"## {extra['title']}", ""]
    if extra.get("intro"):
        body += [extra["intro"], ""]
    for card in cards:
        body.append(render_markdown_verse(layers(card, extra, parallels, scenes)))
    body += ["## Поетичний переклад", "",
             f"Окремо, у [`poetychnyi/rozdil-{chapter}.md`]"
             f"(poetychnyi/rozdil-{chapter}.md). Це **наш поетичний переклад**, "
             "не канонічний і не науковий; у PDF він іде окремою частиною.", ""]
    return "\n".join(body)


def build_latex(chapter: int) -> str:
    cards = load_cards(chapter)
    extra = load_extra(chapter)
    parallels = load_parallels()
    scenes = load_scenes()
    out = [
        "% ЗГЕНЕРОВАНО scripts/build_format_v2_chapter.py — не редагувати вручну.",
        f"% Джерело: editorial/cards/{chapter}.*.json, "
        f"format-v2/rozdil-{chapter}.json, paraleli.json.",
        "",
        r"\naukchapter{%d}{%d}{%s}" % (chapter, len(cards), esc(extra.get("title") or "")),
    ]
    if extra.get("intro"):
        out.append(r"\naukintro{%s}" % esc(extra["intro"]))
    for card in cards:
        out.append(render_latex_verse(layers(card, extra, parallels, scenes)))
    return "\n".join(out) + "\n"


def build_poetic_latex(chapter: int) -> str:
    poems = load_poetic(chapter)
    out = [
        "% ЗГЕНЕРОВАНО scripts/build_format_v2_chapter.py — не редагувати вручну.",
        f"% Джерело: books/ashtavakra-gita/poetychnyi/rozdil-{chapter}.md",
        "",
    ]
    for ident, lines in poems.items():
        out.append(r"\poemverse{%s}{%s}" % (esc(ident), r" \\ ".join(esc(x) for x in lines)))
    return "\n".join(out) + "\n"


def targets(chapter: int) -> dict[Path, str]:
    return {
        BOOK / f"rozdil-{chapter}-naukove.md": build_markdown(chapter),
        GENERATED / f"rozdil-{chapter}.tex": build_latex(chapter),
        GENERATED / f"poetychnyi-{chapter}.tex": build_poetic_latex(chapter),
    }


def chapters_with_cards() -> list[int]:
    found: set[int] = set()
    for path in CARDS.glob("*.json"):
        head = path.name.split(".", 1)[0]
        if head.isdigit():
            found.add(int(head))
    return sorted(found)


def stale(path: Path, text: str) -> bool:
    return not path.is_file() or path.read_text(encoding="utf-8") != text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--chapter", type=int, action="append", default=[])
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    wanted = list(args.chapter) if args.chapter else (
        chapters_with_cards() if args.all else [1])

    outdated: list[str] = []
    written = 0
    report: dict = {"chapters": [], "written": 0, "stale": []}
    for chapter in wanted:
        files = targets(chapter)
        layers_count = {"verses": 0, "devanagari": 0, "transliteration": 0,
                        "translation": 0, "commentary": 0, "parallels": 0,
                        "illustrations": 0, "scenes": 0}
        cards = load_cards(chapter)
        extra = load_extra(chapter)
        parallels = load_parallels()
        scenes = load_scenes()
        for card in cards:
            data = layers(card, extra, parallels, scenes)
            layers_count["verses"] += 1
            for key in ("devanagari", "transliteration", "translation",
                        "commentary", "parallel", "illustration", "scene"):
                if data[key]:
                    target = {"parallel": "parallels",
                              "illustration": "illustrations",
                              "scene": "scenes"}.get(key, key)
                    layers_count[target] += 1
        report["chapters"].append({"chapter": chapter, **layers_count})
        for path, text in files.items():
            if stale(path, text):
                outdated.append(str(path.relative_to(ROOT)))
                if not args.check:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(text, encoding="utf-8")
                    written += 1
    report["written"] = written
    report["stale"] = outdated
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.check and outdated:
        print("Згенеровані файли застаріли: " + ", ".join(outdated), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
