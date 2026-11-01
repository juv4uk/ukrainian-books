#!/usr/bin/env python3
"""Генератор власних векторних схем до віршів (ФОРМАТ-02, шар «ілюстрація»).

Що це **не** є: не історична ілюстрація, не репродукція, не скан, не чужий
малюнок. Це **наші власні схеми**: геометрія й лінія, що пояснюють будову
вірша — рух думки, ключову метафору, структуру повтору. Кожна схема несе
в собі напис «Схема наша, не історична ілюстрація», щоб її неможливо було
видати за джерело.

Чому схема, а не «малюнок у стилі»: будь-яка спроба зробити «давньоіндійську»
картинку була б або підробкою, або етнографічною бутафорією. Схема ж чесно
показує, що вона є, — розбір думки. Стримана палітра (папір, графіт,
вохра) свідомо близька українській книжковій графіці: лінія й геометрія,
без орнаменту й без «східного» декору.

Мотиви параметричні: той самий код малює схеми для різних віршів, тому
машина працює і для решти 278 віршів — досить додати запис у `SPECS`.

Вжиток:
    python3 scripts/build_verse_schemas.py            # згенерувати SVG
    python3 scripts/build_verse_schemas.py --check    # перевірити актуальність
    python3 scripts/build_verse_schemas.py --pdf      # додатково SVG → PDF (cairosvg)
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOK = ROOT / "books" / "ashtavakra-gita"
OUT = BOOK / "ilustratsii"

W, H = 420, 280
PAPER = "#fbf8f1"
INK = "#3b4a5a"
ACCENT = "#b0762a"
MUTED = "#8aa0b5"
FAINT = "#c9d3dd"

HONEST = "Схема наша, не історична ілюстрація"
FONT = "font-family=\"Georgia, 'DejaVu Serif', serif\""


def _wrap(text: str, limit: int = 34) -> list[str]:
    """Розбити підпис на рядки, не розриваючи слів."""
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if len(candidate) > limit and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _text(x: int, y: int, body: str, *, size: int = 13, fill: str = INK,
          anchor: str = "start", style: str = "") -> str:
    extra = f' font-style="{style}"' if style else ""
    return (f'<text x="{x}" y="{y}" {FONT} font-size="{size}" fill="{fill}" '
            f'text-anchor="{anchor}"{extra}>{_esc(body)}</text>')


def _esc(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _footer() -> str:
    return (_text(20, H - 8, HONEST, size=10, fill=MUTED, style="italic")
            + _text(W - 20, H - 8, "ФОРМАТ-02", size=10, fill=MUTED, anchor="end"))


def _frame() -> str:
    return (f'<rect width="{W}" height="{H}" fill="{PAPER}"/>'
            f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" '
            f'fill="none" stroke="{FAINT}" stroke-width="1"/>')


# ---------------------------------------------------------------------------
# Мотиви. Кожен повертає фрагмент SVG; жоден не малює рамку й підпис чесності.
# ---------------------------------------------------------------------------

def motif_city_forest(p: dict) -> str:
    """Дві сучасні сюжетні сцени: та сама людина не тікає до міста чи лісу."""
    return (
        "<rect x=\"16\" y=\"35\" width=\"188\" height=\"181\" rx=\"8\" fill=\"#f5e8dc\" stroke=\"#d4bda6\" stroke-width=\"1.5\"/>"
        "<rect x=\"216\" y=\"35\" width=\"188\" height=\"181\" rx=\"8\" fill=\"#e6efe6\" stroke=\"#a6bba9\" stroke-width=\"1.5\"/>"
        "<text x=\"110\" y=\"27\" font-family=\"Georgia, 'DejaVu Serif', serif\" font-size=\"13\" font-weight=\"bold\" fill=\"#3b4a5a\" text-anchor=\"middle\">Серед людей</text>"
        "<text x=\"310\" y=\"27\" font-family=\"Georgia, 'DejaVu Serif', serif\" font-size=\"13\" font-weight=\"bold\" fill=\"#3b4a5a\" text-anchor=\"middle\">У лісі</text>"
        "<rect x=\"26\" y=\"83\" width=\"55\" height=\"92\" rx=\"2\" fill=\"#c6b5aa\" stroke=\"#8e817b\"/>"
        "<rect x=\"145\" y=\"68\" width=\"47\" height=\"108\" rx=\"2\" fill=\"#c4cfd4\" stroke=\"#8c9fa4\"/>"
        "<rect x=\"35\" y=\"98\" width=\"12\" height=\"15\" fill=\"#fff6d9\"/><rect x=\"54\" y=\"98\" width=\"12\" height=\"15\" fill=\"#fff6d9\"/>"
        "<rect x=\"35\" y=\"125\" width=\"12\" height=\"15\" fill=\"#fff6d9\"/><rect x=\"54\" y=\"125\" width=\"12\" height=\"15\" fill=\"#fff6d9\"/>"
        "<rect x=\"153\" y=\"88\" width=\"12\" height=\"16\" fill=\"#f8f2db\"/><rect x=\"174\" y=\"88\" width=\"11\" height=\"16\" fill=\"#f8f2db\"/>"
        "<rect x=\"153\" y=\"119\" width=\"12\" height=\"16\" fill=\"#f8f2db\"/><rect x=\"174\" y=\"119\" width=\"11\" height=\"16\" fill=\"#f8f2db\"/>"
        "<path d=\"M18 177 L202 177 L202 207 L18 207 Z\" fill=\"#ded1c0\"/>"
        "<circle cx=\"38\" cy=\"164\" r=\"6\" fill=\"#a6755b\"/><path d=\"M32 173 L44 173 L48 191 L28 191Z\" fill=\"#8797a3\"/>"
        "<circle cx=\"175\" cy=\"162\" r=\"6\" fill=\"#a6755b\"/><path d=\"M169 171 L181 171 L185 191 L165 191Z\" fill=\"#9eaa7d\"/>"
        "<path d=\"M216 177 Q258 166 294 178 T404 174 L404 209 L216 209 Z\" fill=\"#b7ccb3\"/>"
        "<path d=\"M239 180 L239 104 M370 181 L370 102\" fill=\"none\" stroke=\"#7c6e57\" stroke-width=\"8\" stroke-linecap=\"round\"/>"
        "<circle cx=\"239\" cy=\"98\" r=\"33\" fill=\"#93b49e\"/><circle cx=\"221\" cy=\"119\" r=\"26\" fill=\"#a5c0a5\"/>"
        "<circle cx=\"370\" cy=\"94\" r=\"37\" fill=\"#85a99b\"/><circle cx=\"390\" cy=\"115\" r=\"25\" fill=\"#9aba9c\"/>"
        "<path d=\"M271 178 L271 130 M345 177 L345 127\" stroke=\"#806f58\" stroke-width=\"5\"/>"
        "<circle cx=\"271\" cy=\"125\" r=\"20\" fill=\"#a7bea0\"/><circle cx=\"345\" cy=\"122\" r=\"21\" fill=\"#9cb8a7\"/>"
        "<circle cx=\"110\" cy=\"129\" r=\"12\" fill=\"#e7c2a4\" stroke=\"#3b4a5a\" stroke-width=\"1.2\"/>"
        "<path d=\"M95 149 Q110 142 125 149 L127 183 L93 183 Z\" fill=\"#63798c\" stroke=\"#3b4a5a\" stroke-width=\"1.5\"/>"
        "<path d=\"M94 164 L86 181 M126 164 L134 181 M101 183 L99 197 M119 183 L121 197\" stroke=\"#3b4a5a\" stroke-width=\"3\" fill=\"none\" stroke-linecap=\"round\"/>"
        "<circle cx=\"310\" cy=\"129\" r=\"12\" fill=\"#e7c2a4\" stroke=\"#3b4a5a\" stroke-width=\"1.2\"/>"
        "<path d=\"M295 149 Q310 142 325 149 L327 183 L293 183 Z\" fill=\"#63798c\" stroke=\"#3b4a5a\" stroke-width=\"1.5\"/>"
        "<path d=\"M294 164 L286 181 M326 164 L334 181 M301 183 L299 197 M319 183 L321 197\" stroke=\"#3b4a5a\" stroke-width=\"3\" fill=\"none\" stroke-linecap=\"round\"/>"
        "<path d=\"M90 120 Q110 111 130 120 M290 120 Q310 111 330 120\" stroke=\"#b0762a\" stroke-width=\"2\" fill=\"none\" stroke-linecap=\"round\"/>"
        "<text x=\"110\" y=\"210\" font-family=\"Georgia, 'DejaVu Serif', serif\" font-size=\"10\" fill=\"#3b4a5a\" text-anchor=\"middle\">Не поспішає до натовпу</text>"
        "<text x=\"310\" y=\"210\" font-family=\"Georgia, 'DejaVu Serif', serif\" font-size=\"10\" fill=\"#3b4a5a\" text-anchor=\"middle\">Не втікає до лісу</text>"
        "<line x1=\"210\" y1=\"39\" x2=\"210\" y2=\"218\" stroke=\"#c9d3dd\" stroke-width=\"1\" stroke-dasharray=\"4 5\"/>"
        "<text x=\"210\" y=\"246\" font-family=\"Georgia, 'DejaVu Serif', serif\" font-size=\"14\" font-weight=\"bold\" fill=\"#b0762a\" text-anchor=\"middle\">Там чи там — рівний стан</text>"
    )


def motif_motion(p: dict) -> str:
    """Рух думки: кілька вихідних точок сходяться в одну."""
    if p.get("scene") == "city_forest":
        return motif_city_forest(p)
    nodes = p["nodes"]
    parts = []
    top, step = 56, 34
    last = top + (len(nodes) - 1) * step
    mid = (top + last) / 2
    for i, node in enumerate(nodes):
        y = top + i * step
        parts.append(f'<circle cx="40" cy="{y}" r="4" fill="{ACCENT}"/>')
        parts.append(_text(54, y + 5, node, size=11))
        parts.append(f'<path d="M196 {y} C222 {y} 214 {mid} 232 {mid}" '
                     f'stroke="{MUTED}" fill="none" stroke-width="1.4"/>')
    parts.append(f'<circle cx="238" cy="{mid}" r="6" fill="{ACCENT}"/>')
    for i, line in enumerate(_wrap(p["target"], 19)):
        parts.append(_text(256, mid - 4 + i * 17, line, size=12, fill=ACCENT))
    return "".join(parts)


def motif_neti(p: dict) -> str:
    """«Не те, не те»: перелік відкинутого і те, що лишається."""
    items = p["items"]
    parts = []
    y = 50
    for item in items:
        parts.append(_text(40, y, item, size=12, fill=MUTED))
        width = 8 * len(item) + 12
        parts.append(f'<line x1="36" y1="{y - 4}" x2="{36 + width}" y2="{y - 4}" '
                     f'stroke="{MUTED}" stroke-width="1.2"/>')
        y += 26
    parts.append(f'<line x1="30" y1="{y + 6}" x2="{W - 30}" y2="{y + 6}" '
                 f'stroke="{FAINT}" stroke-width="1"/>')
    parts.append(f'<circle cx="46" cy="{y + 32}" r="5" fill="{ACCENT}"/>')
    for i, line in enumerate(_wrap(p["rest"], 30)):
        parts.append(_text(62, y + 36 + i * 17, line, size=12, fill=ACCENT))
    return "".join(parts)


def motif_witness(p: dict) -> str:
    """Бачитель і побачене: концентричні кола, центр — не предмет."""
    cx, cy, r = 210, 128, 86
    parts = [
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{MUTED}" stroke-width="1.2"/>',
        f'<circle cx="{cx}" cy="{cy}" r="{r - 22}" fill="none" stroke="{FAINT}" '
        f'stroke-width="1" stroke-dasharray="3 4"/>',
        f'<circle cx="{cx}" cy="{cy}" r="7" fill="{ACCENT}"/>',
    ]
    for k in range(8):
        import math
        angle = k * math.pi / 4
        x1 = cx + (r - 22) * math.cos(angle)
        y1 = cy + (r - 22) * math.sin(angle)
        x2 = cx + (r - 6) * math.cos(angle)
        y2 = cy + (r - 6) * math.sin(angle)
        parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                     f'stroke="{MUTED}" stroke-width="1"/>')
    parts.append(_text(cx, cy + r + 22, p["outer"], size=12, anchor="middle"))
    parts.append(_text(cx, cy - r - 8, p["inner"], size=12, fill=ACCENT, anchor="middle"))
    return "".join(parts)


def motif_illusion(p: dict) -> str:
    """Дві панелі: як здається — як є. Варіанти: мотузка, дзеркало, серпанок."""
    variant = p.get("variant", "rope")
    parts = [
        f'<line x1="{W / 2}" y1="46" x2="{W / 2}" y2="{H - 34}" stroke="{FAINT}" '
        f'stroke-width="1" stroke-dasharray="4 5"/>',
        _text(20, 36, p["left"], size=12, fill=MUTED),
        _text(W - 20, 36, p["right"], size=12, fill=ACCENT, anchor="end"),
    ]
    if variant == "rope":
        parts.append(f'<path d="M52 150 q22 -22 44 0 q22 22 44 0 q22 -22 44 0" '
                     f'stroke="{INK}" fill="none" stroke-width="2"/>')
        parts.append(f'<path d="M244 130 q22 -18 44 0 q22 18 44 0 q22 -18 44 0" '
                     f'stroke="{ACCENT}" fill="none" stroke-width="2"/>')
        parts.append(f'<circle cx="330" cy="130" r="5" fill="{ACCENT}"/>')
        parts.append(_text(52, 196, "хвиляста лінія", size=11, fill=MUTED))
        parts.append(_text(244, 196, "та сама лінія, названа", size=11, fill=ACCENT))
    elif variant == "mirror":
        parts.append(f'<rect x="60" y="70" width="120" height="130" fill="none" '
                     f'stroke="{INK}" stroke-width="1.6"/>')
        parts.append(f'<rect x="240" y="70" width="120" height="130" fill="none" '
                     f'stroke="{ACCENT}" stroke-width="1.6"/>')
        parts.append(f'<circle cx="120" cy="135" r="26" fill="none" stroke="{MUTED}" stroke-width="1.2"/>')
        parts.append(f'<circle cx="300" cy="135" r="26" fill="none" stroke="{MUTED}" '
                     f'stroke-width="1.2" stroke-dasharray="3 4"/>')
        parts.append(_text(60, 218, "образ у дзеркалі", size=11, fill=MUTED))
        parts.append(_text(240, 218, "те, що відбивається", size=11, fill=ACCENT))
    else:  # veil
        parts.append(f'<path d="M60 90 q60 30 120 0 q60 -30 120 0" stroke="{INK}" '
                     f'fill="none" stroke-width="1.6"/>')
        parts.append(f'<path d="M60 150 q60 30 120 0 q60 -30 120 0" stroke="{ACCENT}" '
                     f'fill="none" stroke-width="1.6"/>')
        parts.append(f'<path d="M240 150 q60 -30 120 0" stroke="{ACCENT}" fill="none" '
                     f'stroke-width="1.6" stroke-dasharray="5 4"/>')
        parts.append(_text(60, 196, "те, що видно крізь серпанок", size=11, fill=MUTED))
        parts.append(_text(240, 196, "те, що є під ним", size=11, fill=ACCENT))
    return "".join(parts)


def motif_space(p: dict) -> str:
    """Простір і посудина: межа є, але вона не ріже простір."""
    variant = p.get("variant", "pot")
    parts: list[str] = []
    if variant == "pot":
        parts.append(f'<path d="M150 70 q-26 40 -26 78 q0 46 30 66 q26 16 62 16 '
                     f'q36 0 62 -16 q30 -20 30 -66 q0 -38 -26 -78" fill="none" '
                     f'stroke="{INK}" stroke-width="2"/>')
        parts.append(f'<path d="M150 70 q60 -14 120 0" fill="none" '
                     f'stroke="{INK}" stroke-width="2"/>')
        parts.append(f'<line x1="212" y1="40" x2="212" y2="214" stroke="{MUTED}" '
                     f'stroke-width="1" stroke-dasharray="3 4"/>')
        parts.append(f'<line x1="40" y1="214" x2="380" y2="214" stroke="{MUTED}" '
                     f'stroke-width="1" stroke-dasharray="3 4"/>')
        parts.append(_text(262, 116, "той самий", size=12, fill=ACCENT))
        parts.append(_text(262, 134, "простір", size=12, fill=ACCENT))
        parts.append(_text(40, 56, "стінки ділять посуд,", size=12, fill=MUTED))
        parts.append(_text(40, 74, "а не простір", size=12, fill=MUTED))
    else:  # sky
        parts.append(f'<rect x="40" y="56" width="340" height="150" fill="none" '
                     f'stroke="{FAINT}" stroke-width="1"/>')
        parts.append(f'<path d="M80 120 q30 -26 62 0 q30 26 62 0" stroke="{MUTED}" '
                     f'fill="none" stroke-width="1.2" stroke-dasharray="5 4"/>')
        parts.append(f'<path d="M214 168 q30 -26 62 0 q30 26 62 0" stroke="{MUTED}" '
                     f'fill="none" stroke-width="1.2" stroke-dasharray="5 4"/>')
        parts.append(f'<line x1="40" y1="206" x2="380" y2="206" stroke="{FAINT}" stroke-width="1"/>')
    if p.get("note"):
        parts.append(_text(40, 236, p["note"], size=12, fill=ACCENT))
    return "".join(parts)


def motif_balance(p: dict) -> str:
    """Дві шальки: те, що здається різним, важить однаково."""
    cx, cy = 210, 92
    parts = [
        f'<line x1="{cx}" y1="{cy}" x2="{cx}" y2="196" stroke="{INK}" stroke-width="2"/>',
        f'<line x1="{cx - 120}" y1="{cy}" x2="{cx + 120}" y2="{cy}" stroke="{INK}" stroke-width="2"/>',
        f'<circle cx="{cx}" cy="{cy}" r="5" fill="{ACCENT}"/>',
    ]
    for side in (-1, 1):
        x = cx + side * 120
        parts.append(f'<path d="M{x} {cy} L{x - 26} {cy + 52} L{x + 26} {cy + 52} Z" '
                     f'fill="none" stroke="{MUTED}" stroke-width="1.4"/>')
        parts.append(f'<line x1="{x}" y1="{cy}" x2="{x}" y2="{cy + 26}" stroke="{MUTED}" stroke-width="1"/>')
    for i, line in enumerate(_wrap(p["left"], 22)):
        parts.append(_text(cx - 120, 176 + i * 16, line, size=11, anchor="middle"))
    for i, line in enumerate(_wrap(p["right"], 22)):
        parts.append(_text(cx + 120, 176 + i * 16, line, size=11, fill=ACCENT, anchor="middle"))
    if p.get("note"):
        parts.append(_text(cx, 240, p["note"], size=12, fill=ACCENT, anchor="middle"))
    return "".join(parts)


def motif_knot(p: dict) -> str:
    """Вузол: затягнути його можна лише думкою, і лише думкою розв'язати."""
    parts = [
        f'<path d="M50 140 q60 -70 120 0 q40 46 100 0 q60 -60 100 0" stroke="{INK}" '
        f'fill="none" stroke-width="2"/>',
        f'<circle cx="210" cy="140" r="16" fill="none" stroke="{ACCENT}" stroke-width="2"/>',
        f'<path d="M210 124 q18 16 0 32" stroke="{ACCENT}" fill="none" stroke-width="1.6"/>',
        _text(50, 196, p["left"], size=12),
        _text(W - 50, 196, p["right"], size=12, fill=ACCENT, anchor="end"),
    ]
    return "".join(parts)


def motif_flame(p: dict) -> str:
    """Вогонь: те, що згоряє, і те, що лишається світлом."""
    parts = [
        f'<path d="M210 200 q-46 -18 -46 -66 q0 -34 22 -58 q-6 30 12 44 q10 -34 30 -50 '
        f'q-8 42 14 62 q22 22 10 52 q-8 22 -42 16 z" fill="none" stroke="{ACCENT}" stroke-width="2"/>',
        f'<path d="M210 186 q-18 -10 -18 -30 q0 -16 12 -28 q0 16 10 22 q4 -14 12 -22 '
        f'q-2 22 6 32 q8 12 0 22 q-8 8 -22 4 z" fill="{ACCENT}" opacity="0.18"/>',
        _text(210, 232, p["label"], size=12, fill=MUTED, anchor="middle"),
        _text(210, 46, p.get("note", ""), size=12, fill=ACCENT, anchor="middle"),
    ]
    return "".join(parts)


def _quad(p0, c, p2, t):
    """Точка на квадратичній кривій Безьє."""
    x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * c[0] + t ** 2 * p2[0]
    y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * c[1] + t ** 2 * p2[1]
    return x, y


def motif_thread(p: dict) -> str:
    """Нитка й намистини: ціле тримається не частинами, а ниткою."""
    seg1 = ((30, 150), (120, 104), (210, 150))
    seg2 = ((210, 150), (300, 196), (390, 150))
    parts = [
        f'<path d="M30 150 q90 -46 180 0 q90 46 180 0" stroke="{INK}" '
        f'fill="none" stroke-width="1.6"/>',
    ]
    for seg in (seg1, seg2):
        for t in (0.0, 0.34, 0.68):
            x, y = _quad(*seg, t)
            parts.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="6" fill="{PAPER}" '
                         f'stroke="{ACCENT}" stroke-width="1.6"/>')
    parts.append(f'<circle cx="210" cy="150" r="6" fill="{PAPER}" '
                 f'stroke="{ACCENT}" stroke-width="1.6"/>')
    parts.append(_text(30, 214, p["label"], size=12))
    return "".join(parts)


MOTIFS = {
    "motion": motif_motion,
    "neti": motif_neti,
    "witness": motif_witness,
    "illusion": motif_illusion,
    "space": motif_space,
    "balance": motif_balance,
    "knot": motif_knot,
    "flame": motif_flame,
    "thread": motif_thread,
}

# Вірш → (мотив, параметри, коротка назва для alt-тексту).
SPECS: dict[str, tuple[str, dict, str]] = {
    "1.1": ("motion", {"nodes": ["як здобути знання?", "як настане визволення?",
                                 "як досягти безсторонності?"],
                       "target": "одне питання, одна відповідь"},
            "Три питання сходяться в одну відповідь"),
    "1.2": ("balance", {"left": "чуттєві речі — як отрута",
                        "right": "терпимість, щирість, співчуття — як нектар",
                        "note": "вага не в речах, а в тому, чим вони стають"},
            "Дві шальки: отрута й нектар"),
    "1.3": ("neti", {"items": ["земля", "вода", "вогонь", "вітер", "небо"],
                     "rest": "свідок цих стихій, чия природа — cit"},
            "Пʼять стихій відкинуто, лишається свідок"),
    "1.4": ("motion", {"nodes": ["тіло", "cit"], "target": "вже вільний, уже в мирі"},
            "Відокремлення тіла від cit"),
    "1.5": ("neti", {"items": ["брахман", "інший стан", "учень", "відречений"],
                     "rest": "без форми, свідок усього"},
            "Варна й ашрама відкинуті"),
    "1.6": ("balance", {"left": "дхарма / адхарма", "right": "щастя / страждання",
                        "note": "усе це розумове, не твоє"},
            "Дхарма й адхарма на одній шальці"),
    "1.7": ("witness", {"outer": "усе, що бачиш", "inner": "єдиний бачитель"},
            "Бачитель у центрі побаченого"),
    "1.8": ("illusion", {"variant": "rope", "left": "«я діяч» — укус змія",
                         "right": "«я не діяч» — нектар"},
            "Змія «я діяч» на мотузці"),
    "1.9": ("flame", {"label": "хаща сумнівів", "note": "впевненість «я — чисте прозріння»"},
            "Вогонь упевненості палить сумніви"),
    "1.10": ("illusion", {"variant": "rope", "left": "світ — як змія",
                          "right": "насправді — мотузка"},
             "Змія в мотузці: світ як вигадка"),
    "1.11": ("knot", {"left": "вважаєш себе звʼязаним", "right": "вважаєш себе вільним"},
             "Вузол затягує й розвʼязує думка"),
    "1.12": ("illusion", {"variant": "veil", "left": "здається звʼязаним",
                          "right": "насправді втихлий і вільний"},
             "Серпанок омани"),
    "1.13": ("witness", {"outer": "приписування собі тіла",
                         "inner": "незмінне недвоїсте усвідомлення"},
             "Незмінне усвідомлення під приписуванням"),
    "1.14": ("knot", {"left": "мотузка приписування тіла", "right": "розвʼязано знанням"},
             "Мотузка приписування тіла"),
    "1.15": ("flame", {"label": "самосяйний, незаплямлений",
                       "note": "світло не потребує іншого світла"},
             "Самосяйне світло"),
    "1.16": ("thread", {"label": "всесвіт нанизаний на тебе, як намистини на нитку"},
             "Нитка, на яку нанизаний всесвіт"),
    "1.17": ("space", {"variant": "sky", "note": "без очікування, без видозмін, без тягаря"},
             "Небо без хмар"),
    "1.18": ("neti", {"items": ["образ", "безобразність"], "rest": "те, що є, — і ти в ньому"},
             "Образ і безобразність відкинуті"),
    "1.19": ("illusion", {"variant": "mirror", "left": "образ у дзеркалі",
                          "right": "те, що відбивається"},
             "Дзеркало й відбиток"),
    "1.20": ("space", {"variant": "pot", "note": "один простір — зовні й усередині"},
             "Простір у глечику"),
}

# Схеми решти глав лежать у даних, а не в коді: `format-v2/schemas.json`.
# Словник вище лишається зразком запису й першою главою; усе інше додається
# сюди, щоб 298 віршів не перетворили скрипт на тисячу рядків літералів.
EXTRA_SPECS = BOOK / "format-v2" / "schemas.json"


def load_extra_specs(path: Path = EXTRA_SPECS) -> dict[str, tuple[str, dict, str]]:
    """Прочитати додаткові схеми. Невідомий мотив — помилка, а не мовчазний пропуск."""
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    loaded: dict[str, tuple[str, dict, str]] = {}
    for verse, item in (data.get("schemas") or {}).items():
        motif = item.get("motif")
        if motif not in MOTIFS:
            raise SystemExit(f"схема {verse}: невідомий мотив {motif!r}; "
                             f"дозволено {sorted(MOTIFS)}")
        alt = (item.get("alt") or "").strip()
        if not alt:
            raise SystemExit(f"схема {verse}: порожній підпис (alt)")
        loaded[str(verse)] = (motif, item.get("params") or {}, alt)
    return loaded


SPECS.update(load_extra_specs())


def render(verse: str) -> str:
    """Повний SVG для одного вірша."""
    motif_name, params, alt = SPECS[verse]
    body = MOTIFS[motif_name](params)
    description = (f"Дві сюжетні сцени до вірша {verse}: та сама людина серед людей "
                   f"і в лісі не біжить до жодного місця, зберігаючи рівність. {HONEST}."
                   if params.get("scene") == "city_forest"
                   else f"Власна схема редакції до вірша {verse}. Мотив: {motif_name}. {HONEST}.")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'width="{W}" height="{H}" role="img" aria-labelledby="t-{verse.replace(".", "-")}">\n'
        f'  <title id="t-{verse.replace(".", "-")}">{_esc(alt)}</title>\n'
        f'  <desc>{_esc(description)}</desc>\n'
        f'  {_frame()}\n  {body}\n  {_footer()}\n</svg>\n'
    )


def filename(verse: str) -> str:
    return f"{verse.replace('.', '-')}-{SPECS[verse][0]}.svg"


def build(*, pdf: bool = False) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    written = 0
    for verse in SPECS:
        path = OUT / filename(verse)
        text = render(verse)
        ET.fromstring(text)  # схема мусить бути коректним XML
        if not path.is_file() or path.read_text(encoding="utf-8") != text:
            path.write_text(text, encoding="utf-8")
            written += 1
        if pdf:
            _to_pdf(path)
    index_path = OUT / "README.md"
    index_text = index_document()
    if not index_path.is_file() or index_path.read_text(encoding="utf-8") != index_text:
        index_path.write_text(index_text, encoding="utf-8")
        written += 1
    return {"schemas": len(SPECS), "written": written,
            "files": sorted(filename(v) for v in SPECS)}


def _to_pdf(svg_path: Path) -> None:
    try:
        import cairosvg  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("для --pdf потрібен cairosvg: python3 -m pip install cairosvg") from exc
    cairosvg.svg2pdf(url=str(svg_path), write_to=str(svg_path.with_suffix(".pdf")))


def check() -> list[str]:
    """Перелік застарілих або відсутніх файлів."""
    stale: list[str] = []
    index_path = OUT / "README.md"
    if not index_path.is_file() or index_path.read_text(encoding="utf-8") != index_document():
        stale.append(str(index_path.relative_to(ROOT)))
    for verse in SPECS:
        path = OUT / filename(verse)
        if not path.is_file() or path.read_text(encoding="utf-8") != render(verse):
            stale.append(str(path.relative_to(ROOT)))
    return stale


def index_markdown() -> str:
    rows = ["| Вірш | Мотив | Що пояснює схема | Файл |", "|---|---|---|---|"]
    for verse in sorted(SPECS, key=lambda v: (int(v.split(".")[0]), int(v.split(".")[1]))):
        motif_name, _params, alt = SPECS[verse]
        rows.append(f"| {verse} | `{motif_name}` | {alt} | `{filename(verse)}` |")
    return "\n".join(rows) + "\n"


def index_document() -> str:
    """Покажчик схем із чесним поясненням, чим вони є і чим не є."""
    return (
        "# Схеми до віршів\n\n"
        "**Це наші власні векторні схеми. Вони не є історичними ілюстраціями.**\n\n"
        "Жодна з них не є репродукцією, сканом, фотографією чи чужим малюнком.\n"
        "Кожна пояснює будову вірша — рух думки, ключову метафору, структуру\n"
        "повтору — і не претендує на те, щоб виглядати «давньою».\n\n"
        "Стиль навмисно стриманий: лінія, геометрія, палітра паперу й вохри.\n"
        "Це ближче до української книжкової графіки, ніж до «східної» бутафорії,\n"
        "і саме тому тут немає ні орнаменту, ні стилізації під мініатюру.\n\n"
        "Кожен файл містить напис «Схема наша, не історична ілюстрація» — щоб\n"
        "його неможливо було видати за джерело, навіть вирвавши з книги.\n\n"
        "## Як це зроблено\n\n"
        "Файли генерує `scripts/build_verse_schemas.py` з параметричних мотивів.\n"
        "Мотив — це функція, яка малює схему за параметрами (підписи, варіант\n"
        "образу). Тому машина працює і для решти віршів: досить додати запис\n"
        "у `SPECS`. PDF-версії для верстки — `--pdf` (потрібен `cairosvg`).\n\n"
        "```sh\n"
        "python3 scripts/build_verse_schemas.py          # SVG\n"
        "python3 scripts/build_verse_schemas.py --pdf    # ще й PDF для XeLaTeX\n"
        "python3 scripts/build_verse_schemas.py --check  # чи не застаріли\n"
        "```\n\n"
        "## Перелік\n\n" + index_markdown()
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--pdf", action="store_true")
    args = parser.parse_args(argv)
    if args.check:
        stale = check()
        for item in stale:
            print("ЗАСТАРІЛО: " + item, file=sys.stderr)
        print(json.dumps({"schemas": len(SPECS), "stale": stale}, ensure_ascii=False, indent=2))
        return 1 if stale else 0
    print(json.dumps(build(pdf=args.pdf), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
