#!/usr/bin/env python3
"""РЕД-05: виявити технічні пошкодження Unicode у власних текстах.

Обсяг (з 31.10.2026): `books/**` (книжкові тексти й паспорти походження),
`editorial/cards/*.json` (редакторські картки) і `research/**/*.md`
(дослідницькі примітки). Розширення на картки й примітки зроблено після того,
як у `editorial/cards/2.2.json` роками жив дефект «свіЂ» замість «світ»
(U+0402), «Аштавакрааёіти» замість «Аштавакра-ґіти» (U+0451) і
«надбанні.Ритання» замість «надбанні. Читання», а CI весь час був зелений:
перевірка дивилася лише в `books/`.

Що це НЕ є: орфографічна, санскритологічна, редакторська чи правова
перевірка. Скрипт не має словника й не оцінює зміст — лише технічні ознаки
пошкодженого кодування.

Навмисне НЕ вважається дефектом (інакше гейт вимкнуть за тиждень):
  • IAST-діакритика — ā ī ū ṛ ṃ ḥ ś ṣ ṭ ḍ ṇ ñ та подібні;
  • деванагарі (санскритське письмо);
  • латинські терміни всередині українського тексту: `dvandva-складений`,
    `bahuvrīhi-складник` — латиниця й кирилиця розділені дефісом чи пробілом;
  • український наголос (U+0301) і комбінувальні знаки IAST, а також латинські
    літери з гострим наголосом усередині кириличного слова («самóю») — це
    усталений спосіб позначити наголос, а не мішанина писемностей;
  • відступ на початку рядка, подвійний пробіл у кінці рядка (у Markdown це
    жорсткий перевід рядка), вирівнювання в таблицях Markdown і код у
    блоках ```;
  • звичайні орфографічні помилки (`двадчять`, `Чк`) — це робота людини.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path

SUFFIXES = frozenset({".tex", ".md", ".txt", ".bib", ".sty", ".cls"})
INVISIBLE = frozenset({0x200B, 0x2060, 0xFEFF})
BIDI = frozenset({0x061C, 0x200E, 0x200F}) | frozenset(range(0x202A, 0x202F)) | frozenset(range(0x2066, 0x206A))
MAX_PER_FILE = 25

# Українська абетка: 33 літери у двох регістрах. Апостроф (’ ' ʼ) — не літера,
# тому окремої перевірки не потребує. Усе інше кириличне — чуже для української
# мови: російські ы э ъ ё, сербське Ђ, болгарське ъ тощо.
UKRAINIAN_LETTERS = frozenset(
    "абвгґдеєжзиіїйклмнопрстуфхцчшщьюя"
    "АБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯ"
)

# Слово = послідовність літер і комбінувальних знаків. Дефіс, пробіл, цифра,
# підкреслення, розділові знаки розривають слово — саме тому
# `bahuvrīhi-складник` не вважається мішаниною писемностей.
WORD_RE = re.compile(r"(?:[^\W\d_]|[\u0300-\u036F\u1AB0-\u1AFF\u20D0-\u20FF])+")

# Подвійний пробіл МІЖ текстом: і ліворуч, і праворуч від нього є непробільний
# символ. Відступ і кінець рядка сюди не потрапляють.
DOUBLE_SPACE_RE = re.compile(r"\S {2,}\S")

# Втрачений пробіл після крапки: «надбанні.Ритання». Лише кирилиця з обох
# боків, щоб не спрацьовувати на іменах файлів, URL і скороченнях латиницею.
LOST_SPACE_RE = re.compile(r"[а-яіїєґ’']\.(?=[А-ЯІЇЄҐ])")

FENCE_RE = re.compile(r"^\s*(```|~~~)")

# Латинські літери з гострим наголосом — усталений спосіб позначити український
# наголос у цифровому тексті (прекомпонованої кириличної «о́» не існує).
# «самóю» — це наголос, а не зіпсоване кодування; «свiт» із латинською «i» — дефект.
STRESS_LETTERS = frozenset("áéíóúýÁÉÍÓÚÝ")


def script_of(letter: str) -> str | None:
    """Літерна писемність для зіставлення з прилеглим комбінувальним знаком."""
    if not unicodedata.category(letter).startswith("L"):
        return None
    name = unicodedata.name(letter, "")
    if name.startswith("CYRILLIC "):
        return "CYRILLIC"
    if name.startswith("LATIN "):
        return "LATIN"
    return None


def position(text: str, index: int) -> tuple[int, int]:
    """Рядок і стовпець (з одиниці) для зсуву в тексті."""
    line = text.count("\n", 0, index) + 1
    column = index - text.rfind("\n", 0, index)
    return line, column


def prose_lines(text: str) -> list[tuple[int, str]]:
    """Рядки, до яких можна застосовувати «прозові» правила.

    Виключаються блоки коду (``` … ```) і рядки таблиць Markdown: у них
    подвійний пробіл — це вирівнювання, а не дефект кодування.
    """
    lines: list[tuple[int, str]] = []
    in_fence = False
    for number, line in enumerate(text.split("\n"), start=1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if line.lstrip().startswith("|"):
            continue
        lines.append((number, line))
    return lines


def scan_text(text: str, *, prose: bool = False) -> list[dict]:
    """Знайти лише технічні артефакти; не оцінювати орфографію чи зміст.

    `prose=True` вмикає додаткові правила для суцільного тексту (подвійний
    пробіл, втрачений пробіл після крапки). Для `books/**` вони не діють,
    щоб не валити законну верстку `.tex`.
    """
    findings: list[dict] = []
    line, column = 1, 1
    base_script = None
    for index, char in enumerate(text):
        number = ord(char)
        category = unicodedata.category(char)
        name = unicodedata.name(char, "НЕВІДОМИЙ СИМВОЛ")
        reason = None
        if number == 0xFFFD:
            reason = "символ заміни Unicode: імовірно втрачено вихідні байти"
        elif (number < 0x20 and char not in "\n\r\t") or 0x7F <= number <= 0x9F:
            reason = "неприпустимий керувальний символ"
        elif number in INVISIBLE or number in BIDI:
            reason = "невидимий символ або керування напрямком письма"
        elif category.startswith("M") and name.split(" ", 1)[0] in {"HEBREW", "ARABIC"} and base_script in {"CYRILLIC", "LATIN"}:
            reason = "комбінувальний знак іншої писемності після кирилиці або латинки"
        elif (category.startswith("L") and name.startswith("CYRILLIC ")
              and char not in UKRAINIAN_LETTERS):
            reason = "кирилична літера поза українською абеткою: ознака чужого кодування"

        if reason:
            findings.append({
                "line": line, "column": column, "codepoint": f"U+{number:04X}",
                "reason": reason,
            })
            if len(findings) >= MAX_PER_FILE:
                return findings

        if category.startswith("L"):
            base_script = script_of(char)
        elif not category.startswith("M"):
            base_script = None

        if char == "\n":
            line, column = line + 1, 1
        else:
            column += 1

    # Латиниця всередині кириличного слова: «свiт» із латинським i, «світl».
    # IAST-терміни й деванагарі не зачіпаються: вони не мішають писемностей
    # усередині одного слова. Латинські літери з наголосом (ó в «самóю»)
    # вважаються українським наголосом, а не дефектом.
    for match in WORD_RE.finditer(text):
        word = match.group()
        scripts = set()
        for char in word:
            if unicodedata.category(char).startswith("L") and char not in STRESS_LETTERS:
                script = script_of(char)
                if script:
                    scripts.add(script)
        if len(scripts) > 1:
            offset = next(
                i for i, char in enumerate(word)
                if unicodedata.category(char).startswith("L")
                and script_of(char) == "LATIN"
            )
            line_no, column_no = position(text, match.start() + offset)
            findings.append({
                "line": line_no, "column": column_no,
                "codepoint": f"U+{ord(word[offset]):04X}",
                "reason": "латиниця всередині кириличного слова: мішанина писемностей",
            })
            if len(findings) >= MAX_PER_FILE:
                return sorted(findings, key=lambda f: (f["line"], f["column"]))

    if prose:
        for number, text_line in prose_lines(text):
            for match in DOUBLE_SPACE_RE.finditer(text_line):
                findings.append({
                    "line": number, "column": match.start() + 2,
                    "codepoint": "U+0020",
                    "reason": "подвійний пробіл усередині тексту",
                })
                if len(findings) >= MAX_PER_FILE:
                    break
            if len(findings) >= MAX_PER_FILE:
                break
            for match in LOST_SPACE_RE.finditer(text_line):
                findings.append({
                    "line": number, "column": match.start() + 1,
                    "codepoint": f"U+{ord(match.group()[-1]):04X}",
                    "reason": "втрачений пробіл після крапки",
                })
                if len(findings) >= MAX_PER_FILE:
                    break
            if len(findings) >= MAX_PER_FILE:
                break

    return sorted(findings, key=lambda f: (f["line"], f["column"]))[:MAX_PER_FILE]


def scan_decoded_json_strings(value: object, json_path: str = "$") -> list[dict]:
    """Виявити Unicode-артефакти в рядках після JSON-декодування.

    Координати у звіті стосуються декодованого значення, а не фізичного
    рядка файлу: JSON-екранування змінює позиції символів у вихідному тексті.
    """
    findings: list[dict] = []
    if isinstance(value, str):
        for error in scan_text(value):
            findings.append({
                "json_path": json_path,
                "decoded_line": error["line"],
                "decoded_column": error["column"],
                "codepoint": error["codepoint"],
                "reason": f"після декодування JSON: {error['reason']}",
            })
        return findings
    if isinstance(value, dict):
        children = (
            (f"{json_path}[{json.dumps(key, ensure_ascii=False)}]", child)
            for key, child in value.items()
        )
    elif isinstance(value, list):
        children = ((f"{json_path}[{i}]", child) for i, child in enumerate(value))
    else:
        return findings
    for path, child in children:
        findings.extend(scan_decoded_json_strings(child, path))
        if len(findings) >= MAX_PER_FILE:
            break
    return findings[:MAX_PER_FILE]


def iter_scope_files(root: Path, scope: str) -> list[tuple[Path, bool]]:
    """Файли обсягу разом з ознакою «це суцільний текст».

    `books/**` — усі текстові розширення, без «прозових» правил (верстка
    `.tex` законно містить вирівнювання). `editorial/cards/*.json` і
    `research/**/*.md` — суцільний текст, тому з «прозовими» правилами.
    """
    if scope == "books":
        base = root / "books"
        if not base.is_dir():
            return []
        return [
            (path, False)
            for path in sorted(base.rglob("*"))
            if not path.is_symlink() and path.is_file()
            and path.suffix.lower() in SUFFIXES
        ]
    if scope == "cards":
        base = root / "editorial" / "cards"
        if not base.is_dir():
            return []
        return [(path, True) for path in sorted(base.glob("*.json"))
                if not path.is_symlink() and path.is_file()]
    if scope == "research":
        base = root / "research"
        if not base.is_dir():
            return []
        return [(path, True) for path in sorted(base.rglob("*.md"))
                if not path.is_symlink() and path.is_file()]
    raise ValueError(f"невідомий обсяг: {scope}")


def audit(root: Path) -> dict:
    """Перевірити всі три обсяги; не переходити за симлінками."""
    errors: list[dict] = []
    per_scope: dict[str, int] = {}
    for scope in ("books", "cards", "research"):
        examined = 0
        for path, prose in iter_scope_files(root, scope):
            examined += 1
            rel = path.relative_to(root).as_posix()
            try:
                content = path.read_text(encoding="utf-8", errors="strict")
            except UnicodeDecodeError as exc:
                errors.append({"path": rel, "codepoint": "UTF-8",
                               "reason": f"некоректні байти UTF-8 на позиції {exc.start}"})
                continue
            for error in scan_text(content, prose=prose):
                errors.append({"path": rel, **error})
            if scope == "cards" and "\\u" in content:
                # Екранований U+FFFD або чужа кирилиця непомітні у сирому
                # ASCII, але після json.loads стають реальними символами.
                # Недійсні JSON-картки окремо відхиляє валідатор схеми.
                try:
                    decoded = json.loads(content)
                except json.JSONDecodeError:
                    continue
                for error in scan_decoded_json_strings(decoded):
                    errors.append({"path": rel, **error})
        per_scope[scope] = examined
    return {
        "status": "ok" if not errors else "failed",
        "scanned_files": sum(per_scope.values()),
        "scanned_by_scope": per_scope,
        "errors": errors,
        "scope": ("books/** (книжкові тексти), editorial/cards/*.json (картки), "
                  "research/**/*.md (примітки); це не орфографічна, наукова "
                  "чи правова перевірка"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = audit(args.root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
