#!/usr/bin/env python3
"""Зібрати наукове представлення розділів (`rozdil-N-naukove.md`).

Формат описаний у `docs/FORMAT_V2.md`. Кожен вірш подається шарами:
деванагарі → IAST → українська транслітерація → переклад → коментар.

Деванагарі тут **механічна** (`scripts/iast_to_devanagari.py`), українська
транслітерація теж механічна (`scripts/iast_to_ukrainska.py`). Скрипти не
відновлюють сандгі й не виправляють джерела: якщо щось розійдеться, правда —
в картці, а не в скрипті.

Українська паралель (згадка наших поетів, філософів, діячів) **не
генерується**. Це редакторська робота, і вигадувати її не можна. Паралелі
беруться з `research/ashtavakra/paraleli.json` (id вірша → текст). Якщо для
вірша паралелі немає, це прямо позначено в тексті, а не приховано.

Запуск: python3 scripts/build_naukove.py [корінь репозиторію]
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


deva = _load("iast_to_devanagari", "iast_to_devanagari.py")
ukr = _load("iast_to_ukrainska", "iast_to_ukrainska.py")

PARALLELS = Path("research/ashtavakra/paraleli.json")
NO_PARALLEL = ("*Українська паралель.* Ще не додана: це редакторська робота, "
               "і вигадувати її не можна.")


def devanagari(text: str) -> str:
    for attr in ("transliterate", "to_devanagari", "convert"):
        fn = getattr(deva, attr, None)
        if callable(fn):
            return fn(text)
    raise SystemExit("iast_to_devanagari.py не має відомої функції перетворення")


def render(chapter: int, verses: dict, parallels: dict) -> str:
    out = [
        f"# Аштавакра-ґіта. Розділ {chapter}. Наукове представлення",
        "",
        "> Формат: `docs/FORMAT_V2.md`. Деванагарі — механічна транслітерація поля `iast`",
        "> з картки (`scripts/iast_to_devanagari.py`), не окреме читання за рукописом.",
        "",
    ]
    for num in sorted(verses):
        card = verses[num]
        vid = card["id"]
        iast = (card.get("iast") or card.get("sanskrit") or "").strip()
        out += [
            f"## {vid}",
            "",
            f"**Деванагарі.** {devanagari(iast)}",
            "",
            f"**IAST.** {iast}",
            "",
            f"**Українська транслітерація.** {ukr.transliterate(iast)}",
            "",
            f"**Переклад.** {card['ukrainian_translation'].strip()}",
            "",
            f"**Коментар.** {card['commentary'].strip()}",
            "",
            parallels.get(vid, NO_PARALLEL),
            "",
        ]
    return "\n".join(out).rstrip() + "\n"


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    parallels = {}
    pfile = root / PARALLELS
    if pfile.is_file():
        parallels = json.loads(pfile.read_text(encoding="utf-8"))
    cards: dict[int, dict[int, dict]] = {}
    for path in sorted((root / "editorial" / "cards").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        chapter, verse = data["id"].split(".")
        cards.setdefault(int(chapter), {})[int(verse)] = data
    book = root / "books" / "ashtavakra-gita"
    book.mkdir(parents=True, exist_ok=True)
    written = 0
    force = "--force" in sys.argv
    only = None
    if "--only" in sys.argv:
        only = int(sys.argv[sys.argv.index("--only") + 1])
    for chapter, verses in sorted(cards.items()):
        if only is not None and chapter != only:
            continue
        target = book / f"rozdil-{chapter}-naukove.md"
        if target.exists() and not force:
            # Не перезаписуємо ручну редакторську працю: у готових файлах
            # бувають «Рефрен глави» та ілюстрації, яких генератор не знає.
            print(f"rozdil-{chapter}-naukove.md: пропущено (уже є, є ручні частини)")
            continue
        text = render(chapter, verses, parallels)
        target.write_text(text, encoding="utf-8")
        written += 1
        have = sum(1 for v in verses if f"{chapter}.{v}" in parallels)
        print(f"rozdil-{chapter}-naukove.md: {len(verses)} віршів, "
              f"паралелей {have}")
    print(f"готово: {written} розділів, паралелей усього {len(parallels)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
