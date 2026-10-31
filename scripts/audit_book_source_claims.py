#!/usr/bin/env python3
"""Офлайновий аудит буквальних тверджень книжкового паспорта.

Виявляє тільки фактичну суперечність: PROVENANCE.md заперечує наявність
деванагарі/IAST у розділах, але непорожній шар уже є в книзі.
Не встановлює права, джерельну достовірність або академічну готовність.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

# Свідомо вузько: не виводимо правових наслідків із довільної прози.
EXPLICIT_DENIAL = re.compile(
    r"деванагарі\s+й\s+IAST\s+у\s+\x60rozdil-\*\.md\x60\s+відсутні",
    flags=re.IGNORECASE,
)
# Доказом є непорожній шар, а не згадка в коментарі чи порожня мітка.
LAYER = re.compile(
    r"^[ \t]*\*\*(Деванагарі|IAST)\.\*\*[ \t]+(\S[^\r\n]*)$",
    flags=re.MULTILINE | re.IGNORECASE,
)


def audit(root: Path) -> dict:
    """Тільки читає локальні файли; повертає детермінований JSON-звіт."""
    root = root.resolve()
    books_root = root / "books"
    contradictions: list[dict] = []
    examined = 0
    denials = 0
    if books_root.is_dir():
        for book in sorted(p for p in books_root.iterdir() if p.is_dir()):
            passport = book / "PROVENANCE.md"
            if not passport.is_file():
                continue
            examined += 1
            if not EXPLICIT_DENIAL.search(passport.read_text(encoding="utf-8")):
                continue
            denials += 1
            evidence: list[dict] = []
            for chapter in sorted(book.rglob("rozdil-*.md")):
                if not chapter.is_file():
                    continue
                counts = {"Деванагарі": 0, "IAST": 0}
                for match in LAYER.finditer(chapter.read_text(encoding="utf-8")):
                    key = "IAST" if match.group(1).upper() == "IAST" else "Деванагарі"
                    counts[key] += 1
                if any(counts.values()):
                    evidence.append({
                        "path": chapter.relative_to(root).as_posix(),
                        "layers": counts,
                    })
            if evidence:
                contradictions.append({
                    "book": book.name,
                    "passport": passport.relative_to(root).as_posix(),
                    "claim": "у розділах немає деванагарі й IAST",
                    "evidence": evidence,
                })
    return {
        "status": "inconsistent" if contradictions else "no_detected_conflict",
        "books_examined": examined,
        "books_with_explicit_denial": denials,
        "contradictions": contradictions,
        "limitation": (
            "Перевірено лише явну заяву про відсутність шарів. "
            "Відсутність конфлікту НЕ підтверджує права, джерела або наукову якість."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--strict", action="store_true",
                        help="код 1 за наявності суперечності")
    args = parser.parse_args(argv)
    report = audit(args.root)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if args.strict and report["contradictions"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
