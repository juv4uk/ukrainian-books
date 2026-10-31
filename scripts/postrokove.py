#!/usr/bin/env python3
"""Дворядкове редакторське вирівнювання для ФОРМАТ-02.

Джерело — тільки структуроване поле postrokovo у format-v2/rozdil-N.json.
Вхідні санскритські піврядки обов'язково відповідають IAST чинної картки;
українські фрагменти разом повинні дослівно відтворювати її повний переклад.
Деванагарі та українське читання тут суто механічні проєкції IAST.
"""

from __future__ import annotations

import re

from scripts.iast_to_devanagari import to_devanagari
from scripts.iast_to_ukrainian import to_ukrainian


def _text(value: object) -> str:
    """Нормалізація лише пробілів, без зміни змісту."""
    return " ".join(value.split()) if isinstance(value, str) else ""


def prepare_alignment(card: dict, entry: dict) -> dict | None:
    """Перевірити построкові дані; без них не змінювати старі шари."""
    source = entry.get("postrokovo")
    if source is None:
        return None

    ident = str(card["id"])
    if not isinstance(source, dict) or source.get("status") != "чернетка":
        raise ValueError(f"{ident}: построкові дані мають мати status=чернетка")
    rows = source.get("lines")
    if not isinstance(rows, list) or len(rows) != 2:
        raise ValueError(f"{ident}: потрібно рівно два друковані піврядки")

    full_iast = _text(card.get("iast"))
    expected = [part.strip() for part in re.split(r"\|+", full_iast) if part.strip()]
    if len(expected) != 2:
        raise ValueError(f"{ident}: картка не має двох відділених | піврядків")

    prepared = []
    translations = []
    for index, (item, iast) in enumerate(zip(rows, expected), 1):
        if not isinstance(item, dict):
            raise ValueError(f"{ident}: рядок {index} не є об'єктом")
        actual = _text(item.get("iast"))
        uk = _text(item.get("ukrainian_translation"))
        comment = _text(item.get("commentary"))
        if actual != iast:
            raise ValueError(f"{ident}: рядок {index} не відповідає IAST картки")
        if not uk or not comment:
            raise ValueError(f"{ident}: рядок {index} не має перекладу або коментаря")
        prepared.append({
            "label": ("а", "б")[index - 1],
            "iast": actual,
            "devanagari": to_devanagari(actual, where=f"рядку {index} картки {ident}"),
            "transliteration": to_ukrainian(actual, where=f"рядку {index} картки {ident}"),
            "translation": uk,
            "commentary": comment,
        })
        translations.append(uk)

    whole_translation = _text(card.get("ukrainian_translation"))
    if " ".join(translations) != whole_translation:
        raise ValueError(f"{ident}: рядкові переклади не відтворюють переклад картки")

    return {"status": "чернетка", "lines": prepared}


def render_markdown_alignment(alignment: dict) -> str:
    """Відтворити обидва шари наукової книги, чесно позначивши статус."""
    out = [
        "**Построкове зіставлення (редакторська чернетка, не рецензовано).**",
        "",
    ]
    for line in alignment["lines"]:
        out += [
            f"### Рядок {line['label']}",
            "",
            f"**Деванагарі (механічно з IAST).** {line['devanagari']}",
            "",
            f"**IAST (з редакторської картки).** {line['iast']}",
            "",
            f"**Українська транслітерація (механічна).** {line['transliteration']}",
            "",
            f"**Український відповідник рядка.** {line['translation']}",
            "",
            f"**Коментар рядка (не рецензовано).** {line['commentary']}",
            "",
        ]
    return "\n".join(out)
