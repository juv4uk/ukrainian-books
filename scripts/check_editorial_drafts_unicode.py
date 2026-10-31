#!/usr/bin/env python3
"""ІНЖ-12: додатковий Unicode-аудит редакторських Markdown-чернеток.

Не змінює вимог видавничого шлюзу й не засвідчує рецензування.
Правила перевірки символів запозичує з чинного книжкового аудитора.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.check_book_text_integrity import scan_text


def audit(root: Path) -> dict:
    """Знайти дефекти в editorial/drafts/**/*.md без переходу за symlink."""
    editorial = root / "editorial"
    drafts = editorial / "drafts"
    errors: list[dict] = []
    examined = 0

    if editorial.is_symlink() or drafts.is_symlink():
        errors.append({
            "path": "editorial/drafts",
            "reason": "символьне посилання в каталозі чернеток заборонено",
        })
    elif drafts.exists() and not drafts.is_dir():
        errors.append({
            "path": "editorial/drafts",
            "reason": "шлях чернеток існує, але це не каталог",
        })
    elif drafts.is_dir():
        for path in sorted(drafts.rglob("*")):
            rel = path.relative_to(root).as_posix()
            if path.is_symlink():
                errors.append({
                    "path": rel,
                    "reason": "символьне посилання в редакторських чернетках заборонено",
                })
                continue
            if not path.is_file() or path.suffix.lower() != ".md":
                continue
            examined += 1
            try:
                content = path.read_text(encoding="utf-8", errors="strict")
            except UnicodeDecodeError as exc:
                errors.append({
                    "path": rel,
                    "codepoint": "UTF-8",
                    "reason": f"некоректні байти UTF-8 на позиції {exc.start}",
                })
                continue
            for finding in scan_text(content, prose=True):
                errors.append({"path": rel, **finding})

    return {
        "status": "failed" if errors else "ok",
        "scope": "editorial/drafts/**/*.md",
        "scanned_files": examined,
        "errors": errors,
        "warning": (
            "Каталогу чернеток немає: це не підтверджує готовності до видання"
            if not drafts.exists() and not drafts.is_symlink()
            else "Перевірено лише технічну цілісність, не якість, права чи рецензування"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    result = audit(args.root)
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    print(payload, end="")
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(payload, encoding="utf-8")
    return int(result["status"] == "failed")


if __name__ == "__main__":
    raise SystemExit(main())
