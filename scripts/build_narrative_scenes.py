#!/usr/bin/env python3
"""Генератор власних **наративних** ілюстрацій до окремих віршів.

Чим це відрізняється від `scripts/build_verse_schemas.py`: схема пояснює
**поняття** (свідок, ілюзія, простір, вузол), а сцена показує **ситуацію**
вірша — хтось сидить, хтось іде, щось лежить на землі. Схема відповідає на
питання «як це влаштовано», сцена — на питання «що тут відбувається».

Що це **не** є: не історична ілюстрація, не репродукція, не скан, не чужий
малюнок, не фотографія. Фігури — силуети без облич, щоб зображення не можна
було прочитати як портрет. Кожен файл несе напис «Наша ілюстрація до вірша
N.N — не історичне зображення», щоб його неможливо було видати за джерело.

Палітра й геометрія — ті самі, що в схемах: папір, графіт, вохра, тонка лінія.

Вжиток:
    python3 scripts/build_narrative_scenes.py           # згенерувати SVG
    python3 scripts/build_narrative_scenes.py --check    # чи не застаріли
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOK = ROOT / "books" / "ashtavakra-gita"
OUT = BOOK / "ilustratsii-naratyvni"
INDEX = BOOK / "format-v2" / "scenes.json"

W, H = 420, 280
PAPER = "#fbf8f1"
INK = "#3b4a5a"
ACCENT = "#b0762a"
MUTED = "#8aa0b5"
FAINT = "#c9d3dd"
FONT = "font-family=\"Georgia, 'DejaVu Serif', serif\""

HONEST = "Наша ілюстрація до вірша {verse} — не історичне зображення"
FOOTER_LABEL = "СЦЕНА"


# ---------------------------------------------------------------------------
# Дрібні помічники малювання
# ---------------------------------------------------------------------------

def _f(v: float) -> str:
    return f"{v:.1f}".rstrip("0").rstrip(".")


def sil(paths: list[str], fill: str = INK, opacity: float = 1.0) -> str:
    """Заливка силуету: кілька субконтурів одним path (перекриття нешкідливі)."""
    op = f' opacity="{_f(opacity)}"' if opacity < 1 else ""
    return f'<path d="{" ".join(paths)}" fill="{fill}" stroke="none"{op}/>'


def line(d: str, stroke: str = INK, width: float = 1.6, dash: str = "",
         cap: str = "round") -> str:
    da = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<path d="{d}" fill="none" stroke="{stroke}" stroke-width="{_f(width)}" '
            f'stroke-linecap="{cap}" stroke-linejoin="round"{da}/>')


def circle(cx: float, cy: float, r: float, fill: str = "none", stroke: str = INK,
           width: float = 1.6, opacity: float = 1.0) -> str:
    op = f' opacity="{_f(opacity)}"' if opacity < 1 else ""
    return (f'<circle cx="{_f(cx)}" cy="{_f(cy)}" r="{_f(r)}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{_f(width)}"{op}/>')


def dot(cx: float, cy: float, r: float = 2.6, fill: str = ACCENT) -> str:
    return f'<circle cx="{_f(cx)}" cy="{_f(cy)}" r="{_f(r)}" fill="{fill}" stroke="none"/>'


def ground(y: float, x0: float = 26, x1: float = 394, stroke: str = FAINT) -> str:
    return line(f"M{_f(x0)} {_f(y)} L{_f(x1)} {_f(y)}", stroke=stroke, width=1.2)


# --- фігури (силуети без облич) --------------------------------------------

def standing(x: float, y: float, h: float, fill: str = INK, opacity: float = 1.0,
             arms: str = "down") -> str:
    """Стояча людина: x — центр, y — земля, h — зріст."""
    hr = h * 0.085
    head_cy = y - h + hr
    sh = head_cy + hr * 1.75
    hip = y - h * 0.44
    sw = h * 0.105
    body = [f"M{_f(x - sw)} {_f(sh)} Q{_f(x)} {_f(sh - h * 0.055)} {_f(x + sw)} {_f(sh)} "
            f"L{_f(x + sw * 0.92)} {_f(hip)} L{_f(x - sw * 0.92)} {_f(hip)} Z",
            f"M{_f(x - sw * 0.92)} {_f(hip)} L{_f(x - sw * 0.78)} {_f(y)} "
            f"L{_f(x - sw * 0.30)} {_f(y)} L{_f(x - sw * 0.06)} {_f(hip)} Z",
            f"M{_f(x + sw * 0.92)} {_f(hip)} L{_f(x + sw * 0.78)} {_f(y)} "
            f"L{_f(x + sw * 0.30)} {_f(y)} L{_f(x + sw * 0.06)} {_f(hip)} Z"]
    out = [circle(x, head_cy, hr, fill=fill, stroke="none", opacity=opacity),
           sil(body, fill=fill, opacity=opacity)]
    aw = h * 0.052
    op = f' opacity="{_f(opacity)}"' if opacity < 1 else ""
    if arms == "down":
        d = (f"M{_f(x - sw * 0.9)} {_f(sh + h * 0.02)} L{_f(x - sw * 1.5)} {_f(hip + h * 0.10)} "
             f"M{_f(x + sw * 0.9)} {_f(sh + h * 0.02)} L{_f(x + sw * 1.5)} {_f(hip + h * 0.10)}")
    elif arms == "open":
        d = (f"M{_f(x - sw * 0.9)} {_f(sh + h * 0.02)} L{_f(x - sw * 2.0)} {_f(sh + h * 0.10)} "
             f"M{_f(x + sw * 0.9)} {_f(sh + h * 0.02)} L{_f(x + sw * 2.0)} {_f(sh + h * 0.10)}")
    elif arms == "up":
        d = (f"M{_f(x - sw * 0.9)} {_f(sh + h * 0.02)} L{_f(x - sw * 1.6)} {_f(sh - h * 0.22)} "
             f"M{_f(x + sw * 0.9)} {_f(sh + h * 0.02)} L{_f(x + sw * 1.6)} {_f(sh - h * 0.22)}")
    else:  # "reach" — обидві руки вперед-вправо
        d = (f"M{_f(x + sw * 0.8)} {_f(sh + h * 0.03)} L{_f(x + sw * 2.1)} {_f(sh + h * 0.16)} "
             f"M{_f(x - sw * 0.8)} {_f(sh + h * 0.05)} L{_f(x + sw * 1.6)} {_f(sh + h * 0.26)}")
    out.append(f'<path d="{d}" fill="none" stroke="{fill}" stroke-width="{_f(aw)}" '
               f'stroke-linecap="round"{op}/>')
    return "".join(out)


def seated(x: float, y: float, h: float, fill: str = INK, opacity: float = 1.0,
           face: int = 1) -> str:
    """Сидяча людина зі схрещеними ногами: y — земля."""
    hr = h * 0.105
    head_cy = y - h + hr
    sh = head_cy + hr * 1.8
    hip = y - h * 0.20
    sw = h * 0.125
    body = [f"M{_f(x - sw)} {_f(sh)} Q{_f(x)} {_f(sh - h * 0.06)} {_f(x + sw)} {_f(sh)} "
            f"L{_f(x + sw * 0.8)} {_f(hip)} L{_f(x - sw * 0.8)} {_f(hip)} Z",
            # схрещені ноги — низький купол
            f"M{_f(x - h * 0.30)} {_f(y)} Q{_f(x)} {_f(y - h * 0.20)} {_f(x + h * 0.30)} {_f(y)} "
            f"Q{_f(x)} {_f(y + h * 0.045)} {_f(x - h * 0.30)} {_f(y)} Z"]
    out = [circle(x, head_cy, hr, fill=fill, stroke="none", opacity=opacity),
           sil(body, fill=fill, opacity=opacity)]
    op = f' opacity="{_f(opacity)}"' if opacity < 1 else ""
    aw = h * 0.058
    knee = x + face * h * 0.26
    out.append(f'<path d="M{_f(x - sw * 0.6)} {_f(sh + h * 0.04)} L{_f(x - face * h * 0.22)} '
               f'{_f(hip + h * 0.02)} L{_f(knee)} {_f(hip + h * 0.06)}" fill="none" '
               f'stroke="{fill}" stroke-width="{_f(aw)}" stroke-linecap="round"{op}/>')
    return "".join(out)


def sage(x: float, y: float, h: float, fill: str = INK, face: int = 1) -> str:
    """Старий мудрець: худіший, зі спертою на плече палицею."""
    parts = [seated(x, y, h * 0.94, fill=fill, face=face)]
    # борода-обрис (не обличчя: лише форма під головою)
    parts.append(sil([f"M{_f(x - h * 0.055)} {_f(y - h * 0.86)} Q{_f(x)} {_f(y - h * 0.62)} "
                      f"{_f(x + h * 0.055)} {_f(y - h * 0.86)} Z"], fill=fill))
    # палиця
    parts.append(line(f"M{_f(x - face * h * 0.46)} {_f(y)} L{_f(x - face * h * 0.30)} "
                      f"{_f(y - h * 1.04)}", stroke=fill, width=2.4))
    parts.append(dot(x - face * h * 0.30, y - h * 1.04, 2.4, fill=fill))
    return "".join(parts)


def sleeping(x: float, y: float, h: float, fill: str = INK) -> str:
    """Людина під ковдрою: y — земля, x — голова."""
    hr = h * 0.10
    parts = [circle(x, y - hr * 1.2, hr, fill=fill, stroke="none")]
    parts.append(sil([f"M{_f(x + hr * 0.8)} {_f(y)} Q{_f(x + h * 0.45)} {_f(y - h * 0.62)} "
                      f"{_f(x + h * 0.92)} {_f(y - h * 0.10)} Q{_f(x + h * 0.95)} {_f(y)} "
                      f"{_f(x + h * 0.80)} {_f(y)} Z"], fill=fill, opacity=0.9))
    return "".join(parts)


# --- предмети ---------------------------------------------------------------

def pot(x: float, y: float, w: float, h: float, stroke: str = INK) -> str:
    return "".join([
        line(f"M{_f(x - w)} {_f(y - h * 0.78)} Q{_f(x - w * 1.18)} {_f(y - h * 0.28)} "
             f"{_f(x - w * 0.55)} {_f(y)} L{_f(x + w * 0.55)} {_f(y)} "
             f"Q{_f(x + w * 1.18)} {_f(y - h * 0.28)} {_f(x + w)} {_f(y - h * 0.78)}",
             stroke=stroke, width=1.8),
        line(f"M{_f(x - w * 1.05)} {_f(y - h * 0.78)} L{_f(x + w * 1.05)} {_f(y - h * 0.78)}",
             stroke=stroke, width=1.8),
    ])


def bowl(x: float, y: float, w: float, fill: str = "none") -> str:
    return (f'<path d="M{_f(x - w)} {_f(y - w * 0.45)} Q{_f(x)} {_f(y + w * 0.75)} '
            f'{_f(x + w)} {_f(y - w * 0.45)} Z" fill="{fill}" stroke="{INK}" '
            f'stroke-width="1.6" stroke-linejoin="round"/>')


def waves(x0: float, x1: float, y: float, count: int = 3, stroke: str = MUTED) -> str:
    step = (x1 - x0) / count
    parts = []
    for i in range(count):
        a = x0 + step * i
        b = a + step * 0.55
        c = a + step
        parts.append(line(f"M{_f(a)} {_f(y)} Q{_f(b)} {_f(y - 7)} {_f(c)} {_f(y)}",
                          stroke=stroke, width=1.4))
    return "".join(parts)


def sea(y: float, stroke: str = MUTED) -> str:
    return "".join([waves(24, 396, y + 6 * i, 6, stroke) for i in range(3)])


def tree(x: float, y: float, h: float) -> str:
    return "".join([
        line(f"M{_f(x)} {_f(y)} L{_f(x)} {_f(y - h * 0.55)}", width=2.6),
        line(f"M{_f(x)} {_f(y - h * 0.42)} L{_f(x - h * 0.16)} {_f(y - h * 0.62)}", width=1.6),
        line(f"M{_f(x)} {_f(y - h * 0.48)} L{_f(x + h * 0.17)} {_f(y - h * 0.68)}", width=1.6),
        line(f"M{_f(x - h * 0.34)} {_f(y - h * 0.60)} Q{_f(x - h * 0.40)} {_f(y - h * 0.96)} "
             f"{_f(x - h * 0.06)} {_f(y - h * 0.99)} Q{_f(x + h * 0.22)} {_f(y - h * 1.00)} "
             f"{_f(x + h * 0.30)} {_f(y - h * 0.76)} Q{_f(x + h * 0.34)} {_f(y - h * 0.58)} "
             f"{_f(x + h * 0.06)} {_f(y - h * 0.57)} Q{_f(x - h * 0.22)} {_f(y - h * 0.55)} "
             f"{_f(x - h * 0.34)} {_f(y - h * 0.60)} Z", stroke=INK, width=1.6),
    ])


def boat(x: float, y: float, s: float = 1.0) -> str:
    hull = (f"M{_f(x - 34 * s)} {_f(y)} Q{_f(x)} {_f(y + 16 * s)} {_f(x + 34 * s)} {_f(y)} "
            f"L{_f(x + 26 * s)} {_f(y - 9 * s)} L{_f(x - 26 * s)} {_f(y - 9 * s)} Z")
    sail = (f"M{_f(x + 2 * s)} {_f(y - 10 * s)} L{_f(x + 2 * s)} {_f(y - 58 * s)} "
            f"L{_f(x + 26 * s)} {_f(y - 14 * s)} Z")
    return "".join([
        f'<path d="{hull}" fill="{INK}" stroke="none"/>',
        line(f"M{_f(x + 2 * s)} {_f(y - 6 * s)} L{_f(x + 2 * s)} {_f(y - 60 * s)}", width=1.8),
        f'<path d="{sail}" fill="{PAPER}" stroke="{INK}" stroke-width="1.4"/>',
    ])


def bird(x: float, y: float, s: float = 1.0, stroke: str = INK, width: float = 1.4) -> str:
    return line(f"M{_f(x - 7 * s)} {_f(y)} Q{_f(x - 3 * s)} {_f(y - 6 * s)} {_f(x)} {_f(y)} "
                f"Q{_f(x + 3 * s)} {_f(y - 6 * s)} {_f(x + 7 * s)} {_f(y)}",
                stroke=stroke, width=width)


def heart(x: float, y: float, s: float = 1.0, fill: str = "none", stroke: str = INK) -> str:
    return (f'<path d="M{_f(x)} {_f(y + 16 * s)} C{_f(x - 26 * s)} {_f(y - 2 * s)} '
            f'{_f(x - 12 * s)} {_f(y - 20 * s)} {_f(x)} {_f(y - 8 * s)} '
            f'C{_f(x + 12 * s)} {_f(y - 20 * s)} {_f(x + 26 * s)} {_f(y - 2 * s)} '
            f'{_f(x)} {_f(y + 16 * s)} Z" fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>')


def elephant(x: float, y: float, s: float = 1.0) -> str:
    body = (f"M{_f(x - 34 * s)} {_f(y - 44 * s)} Q{_f(x - 40 * s)} {_f(y - 16 * s)} "
            f"{_f(x - 20 * s)} {_f(y - 14 * s)} L{_f(x + 26 * s)} {_f(y - 14 * s)} "
            f"Q{_f(x + 44 * s)} {_f(y - 16 * s)} {_f(x + 38 * s)} {_f(y - 44 * s)} "
            f"Q{_f(x + 20 * s)} {_f(y - 62 * s)} {_f(x)} {_f(y - 62 * s)} "
            f"Q{_f(x - 24 * s)} {_f(y - 60 * s)} {_f(x - 34 * s)} {_f(y - 44 * s)} Z")
    head = (f"M{_f(x - 30 * s)} {_f(y - 52 * s)} Q{_f(x - 52 * s)} {_f(y - 56 * s)} "
            f"{_f(x - 50 * s)} {_f(y - 36 * s)} Q{_f(x - 50 * s)} {_f(y - 22 * s)} "
            f"{_f(x - 34 * s)} {_f(y - 24 * s)} Z")
    legs = "".join(f"M{_f(x + dx * s)} {_f(y - 16 * s)} L{_f(x + dx * s)} {_f(y)} "
                   f"L{_f(x + (dx + 9) * s)} {_f(y)} L{_f(x + (dx + 9) * s)} {_f(y - 16 * s)} Z"
                   for dx in (-24, -6, 16, 26))
    return "".join([
        sil([body, head, legs]),
        line(f"M{_f(x - 48 * s)} {_f(y - 36 * s)} Q{_f(x - 60 * s)} {_f(y - 24 * s)} "
             f"{_f(x - 52 * s)} {_f(y - 8 * s)}", width=5.2 * s),
        line(f"M{_f(x + 36 * s)} {_f(y - 40 * s)} Q{_f(x + 48 * s)} {_f(y - 32 * s)} "
             f"{_f(x + 46 * s)} {_f(y - 20 * s)}", width=1.6),
        circle(x - 36 * s, y - 44 * s, 9 * s, fill=PAPER, stroke=INK, width=1.4),
    ])


def mirror(x: float, y: float, r: float) -> str:
    return "".join([
        f'<ellipse cx="{_f(x)}" cy="{_f(y)}" rx="{_f(r * 0.78)}" ry="{_f(r)}" '
        f'fill="{PAPER}" stroke="{INK}" stroke-width="2"/>',
        line(f"M{_f(x)} {_f(y + r)} L{_f(x)} {_f(y + r + 16)}", width=2.4),
        line(f"M{_f(x - 16)} {_f(y + r + 16)} L{_f(x + 16)} {_f(y + r + 16)}", width=2.4),
    ])


def smoke(x: float, y: float, h: float) -> str:
    return line(f"M{_f(x)} {_f(y)} Q{_f(x - 16)} {_f(y - h * 0.35)} {_f(x + 4)} "
                f"{_f(y - h * 0.6)} Q{_f(x + 20)} {_f(y - h * 0.82)} {_f(x - 2)} "
                f"{_f(y - h)}", stroke=MUTED, width=2.6)


# ---------------------------------------------------------------------------
# Сцени
# ---------------------------------------------------------------------------

def scene_1_1() -> str:
    """Цар питає, старий мудрець відповідає."""
    p = [ground(216)]
    # сидіння царя: підвищення з підлокітником
    p.append(line("M262 216 L262 194 L350 194 L350 216", width=1.6))
    p.append(line("M256 194 L356 194", width=2.2))
    p.append(line("M350 194 L350 164", width=1.6))
    p.append(line("M336 164 L350 164", width=1.6))
    p.append(seated(300, 194, 80, face=-1))
    # старий мудрець на землі, з палицею
    p.append(sage(126, 216, 78, face=1))
    # три питання: тонкі дуги від того, хто питає, до того, хто відповідає
    for i, yy in enumerate((158, 144, 130)):
        p.append(line(f"M276 {yy} Q208 {yy - 14 - i * 4} 160 {yy - 4 - i * 2}",
                      stroke=ACCENT, width=1.2))
        p.append(dot(158, yy - 4 - i * 2, 2.2))
    return "".join(p)


def scene_1_2() -> str:
    """Людина відсуває чашу отрути й підносить чашу нектару."""
    p = [ground(214)]
    p.append(bowl(96, 214, 26, fill=INK))
    p.append(line("M84 206 Q96 212 108 206", stroke=PAPER, width=1.2))
    p.append(bowl(324, 214, 26, fill=ACCENT))
    p.append(standing(210, 214, 120))
    p.append(line("M188 150 L150 176", width=6, stroke=INK))   # рука до отрути — відштовхує
    p.append(line("M232 150 L286 168", width=6, stroke=INK))
    # три короткі риски відштовхування
    for dx in (-10, 0, 10):
        p.append(line(f"M{128 + dx} 176 l-12 {6 + abs(dx) * 0.2}", stroke=ACCENT, width=1.2))
    p.append(dot(310, 190, 2.6))
    return "".join(p)


def scene_1_10() -> str:
    """Мотузка на землі, що здалася змією; людина відсахнулася."""
    p = [ground(210)]
    p.append(line("M120 210 Q150 186 190 206 Q226 224 262 200 Q286 184 300 208",
                  stroke=INK, width=3.2))
    p.append(line("M300 208 Q306 214 296 214 Q288 214 292 206", stroke=INK, width=3.2))
    p.append(standing(344, 210, 112, arms="up"))
    # знаки переляку
    for i, (dx, dy) in enumerate(((0, -10), (-14, -4), (14, -4))):
        p.append(line(f"M{344 + dx} {92 + dy} l{dx * 0.4} {dy * 0.9 - 8}",
                      stroke=ACCENT, width=1.4))
    return "".join(p)


def scene_1_14() -> str:
    """Меч знання перетинає мотузку приписування."""
    p = [ground(218)]
    p.append(seated(190, 218, 96))
    # мотузка навколо тіла, розірвана там, де проходить клинок
    p.append(line("M150 158 Q190 128 220 140", stroke=ACCENT, width=2.8))
    p.append(line("M150 158 Q190 188 232 172", stroke=ACCENT, width=2.8))
    p.append(line("M150 158 Q136 168 140 182", stroke=ACCENT, width=2.8))
    # клинок: залитий силует, а не риска
    p.append('<path d="M226 156 L296 88 L304 96 Z" fill="%s" stroke="none"/>' % INK)
    p.append(line("M288 104 L310 82", stroke=INK, width=3.2))     # руків'я
    p.append(line("M286 82 L312 108", stroke=ACCENT, width=3.4))   # перехрестя
    p.append(dot(314, 78, 3, fill=INK))
    # розірвані кінці
    p.append(line("M218 136 q-8 -10 -18 -6", stroke=ACCENT, width=2.2))
    p.append(line("M236 176 q10 8 20 4", stroke=ACCENT, width=2.2))
    return "".join(p)


def scene_1_19() -> str:
    """Людина перед дзеркалом: образ усередині й те, що навколо."""
    p = [ground(224)]
    p.append(mirror(268, 140, 58))
    p.append(seated(268, 186, 40, opacity=0.85))
    p.append(standing(140, 224, 116, arms="down"))
    p.append(line("M162 176 L196 168", width=5.4, stroke=INK))
    # те, що «навколо» дзеркала — ледь помітні контури
    p.append(circle(352, 84, 12, stroke=FAINT, width=1.2))
    p.append(bird(348, 138, 1.2, stroke=FAINT, width=1.2))
    p.append(line("M330 196 q14 -10 28 0", stroke=FAINT, width=1.2))
    return "".join(p)


def scene_2_1() -> str:
    """Серпанок омани спадає, і видно чисте світло."""
    import math
    p = []
    # чисте небо — те, що відкривається
    for i in range(3):
        p.append(line(f"M24 {44 + i * 16} Q210 {24 + i * 16} 396 {44 + i * 16}",
                      stroke=FAINT, width=1.1))
    p.append(circle(330, 74, 26, stroke=ACCENT, width=1.6))
    for a in range(8):
        ang = a * math.pi / 4
        p.append(line(f"M{330 + 34 * math.cos(ang):.1f} {74 + 34 * math.sin(ang):.1f} "
                      f"L{330 + 44 * math.cos(ang):.1f} {74 + 44 * math.sin(ang):.1f}",
                      stroke=ACCENT, width=1.2))
    p.append(ground(226))
    p.append(standing(196, 226, 104, arms="down"))
    # серпанок: полотнище, що сповзає ліворуч
    p.append(line("M110 74 Q210 108 322 66", stroke=INK, width=2.2))
    p.append(line("M112 96 Q210 132 318 88", stroke=INK, width=1.8))
    for x in (150, 200, 252):
        p.append(line(f"M{x} {78 + (x - 110) * 0.1:.0f} l2 18", stroke=INK, width=1.2))
    p.append(line("M110 74 q-16 26 -4 46 q10 16 26 8", stroke=INK, width=2))
    return "".join(p)


def scene_2_9() -> str:
    """Спрагла людина йде до води, якої немає."""
    p = [ground(206)]
    p.append(line("M24 190 L396 190", stroke=FAINT, width=1.2))
    p.append(standing(140, 206, 108, arms="reach"))
    # марево: смуга «води», що просвічує
    for i, yy in enumerate((196, 202, 208)):
        p.append(line(f"M250 {yy} q16 -8 32 0 q16 8 32 0 q16 -8 32 0 q16 8 26 0",
                      stroke=MUTED, width=1.2, dash="8 6" if i == 2 else ""))
    p.append(line("M250 168 q20 -10 40 0 q20 10 40 0", stroke=FAINT, width=1.1, dash="4 5"))
    p.append(dot(300, 186, 2.4, fill=MUTED))
    return "".join(p)


def scene_4_3() -> str:
    """Дим проходить крізь небо, але не змішується з ним."""
    p = []
    # небо: широкі дуги
    for i in range(4):
        p.append(line(f"M24 {56 + i * 22} Q210 {34 + i * 22} 396 {56 + i * 22}",
                      stroke=FAINT, width=1.1))
    p.append(ground(214))
    p.append(smoke(196, 210, 150))
    # вогнище
    p.append(line("M176 210 L196 200 L216 210", stroke=ACCENT, width=2))
    p.append(line("M186 210 L196 204 L206 210", stroke=ACCENT, width=1.4))
    p.append(seated(300, 214, 76, face=-1))
    return "".join(p)


def scene_6_1() -> str:
    """Глечик на землі: той самий простір усередині й зовні."""
    p = [ground(218)]
    p.append(pot(140, 218, 34, 74))
    # простір: горизонтальні риски, що проходять крізь глечик
    for i in range(3):
        y = 168 + i * 16
        p.append(line(f"M60 {y} L108 {y}", stroke=MUTED, width=1.1))
        p.append(line(f"M172 {y} L256 {y}", stroke=MUTED, width=1.1))
        p.append(line(f"M108 {y} L172 {y}", stroke=ACCENT, width=1.1, dash="3 5"))
    p.append(seated(310, 218, 84, face=-1))
    p.append(line("M262 186 q16 -8 30 0", stroke=FAINT, width=1.2))
    return "".join(p)


def scene_8_1() -> str:
    """Людина за ґратами бажання тягнеться до птаха."""
    p = [ground(220)]
    for i in range(5):
        x = 132 + i * 34
        p.append(line(f"M{x} 96 L{x} 220", stroke=INK, width=2.4))
    p.append(line("M124 96 L284 96", stroke=INK, width=2.4))
    p.append(line("M124 220 L284 220", stroke=INK, width=2.4))
    p.append(seated(206, 220, 78))
    p.append(line("M232 158 L288 146", width=5.6, stroke=INK))
    p.append(bird(322, 132, 1.5))
    p.append(bird(350, 108, 1.1, stroke=MUTED))
    p.append(line("M24 220 L120 220", stroke=FAINT, width=1.2))
    p.append(line("M290 220 L396 220", stroke=FAINT, width=1.2))
    return "".join(p)


def scene_10_2() -> str:
    """Дім, поле й гроші розчиняються над сплячою людиною, як сон."""
    p = [ground(222)]
    p.append(sleeping(96, 222, 78))
    # дім
    p.append(line("M150 168 L186 138 L222 168 L222 208 L150 208 Z", stroke=MUTED, width=1.4, dash="7 5"))
    p.append(line("M178 208 L178 186 L194 186 L194 208", stroke=MUTED, width=1.2, dash="5 4"))
    # поле
    for i in range(4):
        p.append(line(f"M240 {200 + i * 8} l44 -6", stroke=FAINT, width=1.2, dash="6 5"))
    # монети
    p.append(circle(320, 176, 8, stroke=MUTED, width=1.3, opacity=0.9))
    p.append(circle(340, 160, 7, stroke=FAINT, width=1.2, opacity=0.9))
    p.append(circle(306, 152, 6, stroke=FAINT, width=1.2, opacity=0.9))
    p.append(smoke(210, 148, 60))
    for i, (dx, dy) in enumerate(((0, 0), (12, -12), (24, -24))):
        p.append(line(f"M{72 + dx} {198 + dy} q7 -6 0 -12", stroke=MUTED, width=1.3))
    return "".join(p)


def scene_13_1() -> str:
    """Людина сидить під деревом, відкинувши віддавання й приймання."""
    p = [ground(220)]
    p.append(tree(306, 220, 156))
    p.append(seated(132, 220, 86))
    # жебрацький пояс, що звисає поруч
    p.append(line("M196 220 q10 -30 2 -52", stroke=ACCENT, width=2.2))
    p.append(line("M190 168 q10 10 18 0", stroke=ACCENT, width=1.6))
    p.append(bowl(238, 220, 22))
    p.append(line("M60 220 L96 220", stroke=FAINT, width=1.2))
    return "".join(p)


def scene_14_2() -> str:
    """Порожній двір: речі, друзі й слуги вже не тут."""
    p = [line("M52 224 L52 70 L368 70 L368 224", stroke=MUTED, width=1.4),
         ground(224, 52, 368)]
    p.append(seated(210, 224, 80))
    # місця, де були речі, друзі й слуги
    p.append(line("M78 224 L78 192 L112 192 L112 224", stroke=FAINT, width=1.2, dash="6 5"))
    p.append(line("M78 208 L112 208", stroke=FAINT, width=1.1, dash="6 5"))
    p.append(line("M150 224 q11 -26 30 0", stroke=FAINT, width=1.2, dash="5 4"))
    p.append(line("M250 224 q12 -28 32 0", stroke=FAINT, width=1.2, dash="5 4"))
    p.append(circle(322, 200, 13, stroke=FAINT, width=1.2, opacity=0.9))
    p.append(line("M304 148 L340 148", stroke=FAINT, width=1.2))
    p.append(line("M314 162 L330 162", stroke=FAINT, width=1.1))
    return "".join(p)


def scene_15_9() -> str:
    """Тіло йде дорогою, а той, хто сидить, лишається."""
    p = [ground(222)]
    # дорога в далечінь
    p.append(line("M60 222 L150 156", stroke=FAINT, width=1.2))
    p.append(line("M300 222 L210 156", stroke=FAINT, width=1.2))
    p.append(standing(268, 200, 62, opacity=0.55))
    # сліди
    for i, (x, y) in enumerate(((300, 214), (322, 208), (344, 202))):
        p.append(line(f"M{x} {y} l10 -3", stroke=ACCENT, width=1.6))
    p.append(seated(112, 222, 92))
    p.append(line("M156 160 q12 -10 26 0", stroke=ACCENT, width=1.3))
    return "".join(p)


def scene_16_1() -> str:
    """Людина серед куп книг, і спокою нема."""
    p = [ground(224)]
    p.append(seated(212, 224, 84))
    # купи сувоїв/книг
    for x0, n in ((92, 4), (300, 5)):
        for i in range(n):
            p.append(f'<rect x="{x0 - 26}" y="{224 - 12 * (i + 1)}" width="52" height="10" '
                     f'rx="2" fill="none" stroke="{INK}" stroke-width="1.2"/>')
    p.append(line("M212 120 q-8 -14 -20 -16", stroke=ACCENT, width=1.4))
    p.append(line("M212 120 q8 -14 20 -16", stroke=ACCENT, width=1.4))
    p.append(line("M236 132 q14 4 18 16", stroke=FAINT, width=1.3))
    p.append(line("M188 132 q-14 4 -18 16", stroke=FAINT, width=1.3))
    return "".join(p)


def scene_5_2() -> str:
    """Бульбашки постають з океану — так само й світ із тебе."""
    p = [line("M24 200 L170 200", stroke=FAINT, width=1.2)]
    p.append(sea(206))
    p.append(seated(92, 200, 86, face=1))
    # бульбашки, що піднімаються з води
    for cx, cy, r in ((196, 168, 9), (222, 146, 13), (252, 118, 18), (286, 84, 24)):
        p.append(circle(cx, cy, r, stroke=ACCENT, width=1.5, opacity=0.95))
        p.append(line(f"M{cx - r * 0.5:.1f} {cy - r * 0.4:.1f} "
                      f"q{r * 0.35:.1f} -{r * 0.35:.1f} {r * 0.7:.1f} 0",
                      stroke=ACCENT, width=1.1))
    p.append(line("M150 200 q14 -10 26 0", stroke=MUTED, width=1.3))
    return "".join(p)


def scene_15_14() -> str:
    """Чи сяє окремо від золота браслет?"""
    p = [ground(220)]
    # злиток золота на плиті
    p.append(line("M96 220 L200 220 L192 204 L104 204 Z", stroke=MUTED, width=1.4))
    p.append(sil(["M118 204 Q112 178 134 172 Q158 166 172 180 Q182 192 176 204 Z"],
                 fill=ACCENT, opacity=0.9))
    # браслет
    p.append(circle(288, 176, 30, stroke=INK, width=5))
    p.append(circle(288, 176, 30, stroke=PAPER, width=2.4))
    p.append(circle(288, 176, 22, stroke=INK, width=1.4))
    # те саме сяйво: тонка лінія від золота до браслета
    p.append(line("M182 190 Q236 172 256 174", stroke=ACCENT, width=1.2, dash="5 5"))
    for x0, y0, x1, y1 in ((288, 132, 288, 118), (250, 146, 240, 136), (326, 146, 336, 136)):
        p.append(line(f"M{x0} {y0} L{x1} {y1}", stroke=ACCENT, width=1.2))
    return "".join(p)


def scene_17_12() -> str:
    """Звільнена людина дивиться, їсть і йде — і ніщо її не тримає."""
    p = [ground(224)]
    p.append(standing(196, 224, 118, arms="down"))
    # предмети, до яких вона торкається: чаша, квітка, плід
    p.append(bowl(126, 214, 18))
    p.append(line("M96 214 l-6 -18", stroke=ACCENT, width=1.4))
    p.append(circle(90, 190, 6, stroke=ACCENT, width=1.3))
    p.append(circle(300, 206, 9, stroke=INK, width=1.4))
    # розірване кільце під ногами
    p.append(line("M156 236 q40 12 82 0", stroke=MUTED, width=1.6, dash="10 8"))
    p.append(line("M258 232 l10 8", stroke=MUTED, width=1.6))
    return "".join(p)


def scene_18_13() -> str:
    """Звільнений ще за життя йде просто, як живеться."""
    p = [ground(222)]
    p.append(standing(206, 222, 122, arms="open"))
    # подвійний контур: живий і вже вільний
    p.append(line("M206 100 q-46 10 -46 62 q0 44 46 60 q46 -16 46 -60 q0 -52 -46 -62",
                  stroke=ACCENT, width=1.1, dash="6 6"))
    p.append(line("M120 222 L296 222", stroke=FAINT, width=1.2))
    p.append(bird(316, 132, 1.3, stroke=MUTED))
    return "".join(p)


def scene_19_1() -> str:
    """Кліщі знання витягують колючку з серця."""
    p = []
    p.append(heart(210, 158, 1.5))
    for i, (dx, dy) in enumerate(((-10, 0), (6, -8), (14, 6), (-4, 10))):
        p.append(line(f"M{210 + dx} {158 + dy} l-4 -10", stroke=ACCENT, width=1.6))
    # кліщі
    p.append(line("M252 100 L214 146", stroke=INK, width=2.6))
    p.append(line("M252 100 L214 152", stroke=INK, width=2.6))
    p.append(line("M214 146 l-8 -2", stroke=INK, width=2.2))
    p.append(line("M214 152 l-8 2", stroke=INK, width=2.2))
    p.append(line("M252 100 L286 72", stroke=INK, width=3))
    p.append(line("M280 66 L296 82", stroke=ACCENT, width=2.4))
    # витягнута колючка
    p.append(line("M200 140 l-2 -14", stroke=ACCENT, width=1.8))
    p.append(dot(198, 124, 2))
    return "".join(p)


def scene_20_13() -> str:
    """Порожні місця вчителя й учня."""
    p = [ground(220)]
    # сидіння вчителя
    p.append(line("M110 220 L110 200 L170 200 L170 220", stroke=INK, width=1.6))
    p.append(line("M104 200 L176 200", stroke=INK, width=2))
    # циновка учня
    p.append(line("M250 220 L296 220 L304 208 L258 208 Z", stroke=INK, width=1.6))
    # контури тих, кого немає
    p.append(seated(140, 198, 74, opacity=0.18))
    p.append(seated(276, 206, 70, opacity=0.18, face=-1))
    p.append(line("M196 150 q14 -12 28 0", stroke=FAINT, width=1.3))
    p.append(line("M196 170 q14 -12 28 0", stroke=FAINT, width=1.3))
    # закрита книжка на землі
    p.append(f'<rect x="196" y="204" width="28" height="14" rx="2" fill="none" '
             f'stroke="{MUTED}" stroke-width="1.3"/>')
    p.append(line("M210 204 L210 218", stroke=MUTED, width=1.1))
    return "".join(p)


# Вірш → (slug, коротка назва, сцена, підпис-сцена одним реченням)
SCENES: dict[str, tuple[str, str, object, str]] = {
    "1.1": ("besida", "Цар питає Аштавакру",
            scene_1_1,
            "Двоє сидять навпроти: цар питає, старий мудрець із палицею відповідає"),
    "1.2": ("otruta-i-nektar", "Отрута й нектар",
            scene_1_2,
            "Людина відштовхує чашу отрути й простягає руку до чаші нектару"),
    "1.10": ("zmii-v-motuztsi", "Змія в мотузці",
             scene_1_10,
             "Людина відсахнулася від мотузки на землі, що здалася їй змією"),
    "1.14": ("mech-znannia", "Меч знання",
             scene_1_14,
             "Меч знання перетинає мотузку, якою людина прив'язала до себе тіло"),
    "1.19": ("dzerkalo", "Дзеркало",
             scene_1_19,
             "Людина перед дзеркалом: відбиток усередині й речі навколо нього"),
    "2.1": ("serpanok", "Серпанок омани",
            scene_2_1,
            "З людини сповзає серпанок, і за ним видно чисте світло"),
    "2.9": ("marevo", "Вода в мареві",
            scene_2_9,
            "Спрагла людина простягає руку до води, якої насправді немає"),
    "4.3": ("dym-i-nebo", "Дим і небо",
            scene_4_3,
            "Дим від вогнища проходить крізь небо, але не змішується з ним"),
    "6.1": ("hlechyk-i-prostir", "Глечик і простір",
            scene_6_1,
            "Глечик на землі: той самий простір усередині й зовні, крізь стінки"),
    "5.2": ("bulbashka-z-okeanu", "Бульбашка з океану",
            scene_5_2,
            "Людина сидить на березі, а з океану одна за одною піднімаються бульбашки"),
    "8.1": ("polon", "Ґрати бажання",
            scene_8_1,
            "Людина за ґратами тягнеться рукою до птаха, що сидить на волі"),
    "10.2": ("son", "Дім, поле й гроші як сон",
             scene_10_2,
             "Над сплячою людиною розчиняються дім, поле й монети, як сон"),
    "13.1": ("sydyt-iak-zavhodno", "Сидить, як завгодно",
             scene_13_1,
             "Людина сидить під деревом, а жебрацький пояс і чаша лежать осторонь"),
    "14.2": ("porozhnii-dvir", "Порожній двір",
             scene_14_2,
             "Порожній двір: обриси речей, друзів і слуг лишилися, а їх самих немає"),
    "15.9": ("tilo-ide", "Тіло йде, свідок стоїть",
             scene_15_9,
             "Тіло йде дорогою, лишаючи сліди, а той, хто сидить, не йде"),
    "16.1": ("kupy-knyh", "Купи книг",
             scene_16_1,
             "Людина сидить між двома купами книг, тримаючись за голову"),
    "15.14": ("brastelet-i-zoloto", "Браслет і золото",
              scene_15_14,
              "Злиток золота на плиті й браслет поруч: окремо від золота браслет не сяє"),
    "17.12": ("zvlinenyi-u-diiakh", "Звільнений у звичайних діях",
              scene_17_12,
              "Людина йде повз чашу, квітку й плід, торкаючись їх, і ніщо її не тримає"),
    "18.13": ("zvlinenyi-za-zhyttia", "Звільнений за життя",
              scene_18_13,
              "Людина стоїть з відкритими долонями, обведена ще одним, пунктирним контуром"),
    "19.1": ("klishchi", "Кліщі знання",
             scene_19_1,
             "Кліщі витягують колючку з серця, в якому їх було кілька"),
    "20.13": ("porozhni-mistsia", "Порожні місця",
              scene_20_13,
              "Порожні сидіння вчителя й учня, а між ними закрита книжка на землі"),
}


# ---------------------------------------------------------------------------
# Складання файлів
# ---------------------------------------------------------------------------

def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def filename(verse: str) -> str:
    return f"{verse.replace('.', '-')}-{SCENES[verse][0]}.svg"


def render(verse: str) -> str:
    slug, title, draw, caption = SCENES[verse]
    honest = HONEST.format(verse=verse)
    body = draw()
    tid = "t-" + verse.replace(".", "-")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'width="{W}" height="{H}" role="img" aria-labelledby="{tid}">\n'
        f'  <title id="{tid}">{_esc(title)}</title>\n'
        f'  <desc>Наративна ілюстрація редакції до вірша {verse}: {_esc(caption)}. '
        f'{_esc(honest)}. Фігури — силуети без облич.</desc>\n'
        f'  <rect width="{W}" height="{H}" fill="{PAPER}"/>'
        f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" fill="none" '
        f'stroke="{FAINT}" stroke-width="1"/>\n'
        f'  {body}\n'
        f'  <text x="20" y="{H - 8}" {FONT} font-size="10" fill="{MUTED}" '
        f'text-anchor="start" font-style="italic">{_esc(honest)}</text>'
        f'<text x="{W - 20}" y="{H - 8}" {FONT} font-size="10" fill="{MUTED}" '
        f'text-anchor="end">{FOOTER_LABEL} {verse}</text>\n'
        f'</svg>\n'
    )


def index_data() -> dict:
    return {
        "schema_version": 1,
        "note": ("Наративні ілюстрації до окремих віршів: сцена, а не схема поняття. "
                 "Читає scripts/build_format_v2_chapter.py; файли генерує "
                 "scripts/build_narrative_scenes.py."),
        "scenes": {
            verse: {"file": filename(verse), "caption": SCENES[verse][3],
                    "title": SCENES[verse][1]}
            for verse in sorted(SCENES, key=lambda v: (int(v.split(".")[0]),
                                                       int(v.split(".")[1])))
        },
    }


def index_markdown() -> str:
    rows = ["| Вірш | Сцена | Що показано | Файл |", "|---|---|---|---|"]
    for verse in sorted(SCENES, key=lambda v: (int(v.split(".")[0]),
                                               int(v.split(".")[1]))):
        slug, title, _draw, caption = SCENES[verse]
        rows.append(f"| {verse} | {title} | {caption} | `{filename(verse)}` |")
    return "\n".join(rows) + "\n"


def readme() -> str:
    return (
        "# Наративні ілюстрації до віршів\n\n"
        "**Це наші власні малюнки. Вони не є історичними ілюстраціями.**\n\n"
        "Схеми в `../ilustratsii/` пояснюють **поняття** (свідок, ілюзія,\n"
        "простір, вузол). Тут — **сцени**: що саме відбувається у вірші. Двоє\n"
        "сидять і розмовляють; людина відсахнулася від мотузки; човен блукає\n"
        "океаном; слон обходить гірке листя.\n\n"
        "Фігури — силуети без облич. Це зроблено свідомо: обличчя перетворило б\n"
        "малюнок на претензію зобразити конкретну людину, а ми не маємо жодного\n"
        "зображення, на яке могли б спертися. Тому тут немає ні портретів, ні\n"
        "одягу з претензією на давність, ні орнаменту.\n\n"
        "Палітра й лінія — ті самі, що в схемах: папір, графіт, вохра, тонкий\n"
        "контур. Кожен файл несе напис «Наша ілюстрація до вірша N.N — не\n"
        "історичне зображення», щоб його неможливо було видати за джерело,\n"
        "навіть вирвавши з книги.\n\n"
        "Відібрано не всі 298 віршів, а ті, де є справжня сцена або образ:\n"
        "розмова, предмет, рух, тварина. Вірші без сцени лишилися зі схемою —\n"
        "малювати до них «щось» означало б вигадувати те, чого в тексті немає.\n\n"
        "## Як це зроблено\n\n"
        "Файли генерує `scripts/build_narrative_scenes.py`: кожна сцена —\n"
        "функція з примітивів (силует, глечик, човен, слон). Реєстр для книги —\n"
        "`../format-v2/scenes.json`.\n\n"
        "```sh\n"
        "python3 scripts/build_narrative_scenes.py          # SVG\n"
        "python3 scripts/build_narrative_scenes.py --check  # чи не застаріли\n"
        "```\n\n"
        "## Перелік\n\n" + index_markdown()
    )


def build() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    written = 0
    for verse in SCENES:
        path = OUT / filename(verse)
        text = render(verse)
        ET.fromstring(text)  # сцена мусить бути коректним XML
        if not path.is_file() or path.read_text(encoding="utf-8") != text:
            path.write_text(text, encoding="utf-8")
            written += 1
    for path, text in ((OUT / "README.md", readme()),
                       (INDEX, json.dumps(index_data(), ensure_ascii=False, indent=2) + "\n")):
        if not path.is_file() or path.read_text(encoding="utf-8") != text:
            path.write_text(text, encoding="utf-8")
            written += 1
    return {"scenes": len(SCENES), "written": written,
            "files": sorted(filename(v) for v in SCENES)}


def check() -> list[str]:
    stale: list[str] = []
    for path, text in [(OUT / "README.md", readme()),
                       (INDEX, json.dumps(index_data(), ensure_ascii=False, indent=2) + "\n")]:
        if not path.is_file() or path.read_text(encoding="utf-8") != text:
            stale.append(str(path.relative_to(ROOT)))
    for verse in SCENES:
        path = OUT / filename(verse)
        if not path.is_file() or path.read_text(encoding="utf-8") != render(verse):
            stale.append(str(path.relative_to(ROOT)))
    return stale


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if args.check:
        stale = check()
        for item in stale:
            print("ЗАСТАРІЛО: " + item, file=sys.stderr)
        print(json.dumps({"scenes": len(SCENES), "stale": stale},
                         ensure_ascii=False, indent=2))
        return 1 if stale else 0
    print(json.dumps(build(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
