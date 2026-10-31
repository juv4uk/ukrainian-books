#!/usr/bin/env python3
"""Перевірити мінімальні безпекові передумови GitHub Actions без PyYAML.

Це навмисно вузька перевірка контрольованого формату YAML, а не YAML-парсер
або заміна GitHub branch rulesets. Невідомі форми подання прав відхиляються.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

REQUIRED = {"quality.yml", "provenance-audit.yml", "verse-registry.yml"}
EVENT = re.compile(r"^  ([a-z_]+):\s*(?:#.*)?$")
RIGHT = re.compile(r"^([ \t]*)([a-z][a-z-]*):\s*([a-z-]+)?\s*(?:#.*)?$")
PERMISSIONS = re.compile(r"^([ \t]*)permissions:\s*(.*?)\s*$")
DANGEROUS = {"pull_request_target", "workflow_run"}


def block(lines: list[str], start: int) -> list[str]:
    """Повернути рядки до наступного ключа такої самої/меншої вкладеності."""
    depth = len(lines[start]) - len(lines[start].lstrip(" "))
    data = []
    for line in lines[start + 1 :]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent <= depth:
            break
        data.append(line)
    return data


def inspect(name: str, source: str) -> list[str]:
    errors = []
    lines = source.splitlines()
    event_line = next((i for i, row in enumerate(lines) if row == "on:"), None)
    if event_line is None:
        errors.append(f"{name}: потрібний багаторядковий блок on:")
        events = set()
    else:
        events = {m.group(1) for row in block(lines, event_line) if (m := EVENT.match(row))}
    for event in sorted(DANGEROUS & events):
        errors.append(f"{name}: небезпечна подія {event}")

    root = next((i for i, row in enumerate(lines) if row == "permissions:"), None)
    if root is None:
        errors.append(f"{name}: немає явного кореневого permissions:")
    else:
        root_items = {m.group(2): m.group(3) for row in block(lines, root) if (m := RIGHT.match(row))}
        if root_items.get("contents") != "read":
            errors.append(f"{name}: потрібне contents: read у кореневих permissions")

    for i, row in enumerate(lines):
        m = PERMISSIONS.match(row)
        if not m:
            continue
        if m.group(2) or "\t" in m.group(1):
            errors.append(f"{name}:{i+1}: нетипове/скорочене визначення permissions")
            continue
        settings = block(lines, i)
        if not settings:
            errors.append(f"{name}:{i+1}: порожнє визначення permissions")
        for field in settings:
            field_match = RIGHT.match(field)
            if not field_match:
                errors.append(f"{name}:{i+1}: невідомий формат permissions")
            elif field_match.group(3) not in {"read", "none"}:
                errors.append(f"{name}:{i+1}: заборонені права {field_match.group(2)}: {field_match.group(3)}")

    if name == "quality.yml":
        if "pull_request" not in events:
            errors.append("quality.yml: перевірка повинна запускатися на pull_request")
        push = next((i for i, row in enumerate(lines) if row == "  push:"), None)
        if push is None or not any(re.search(r"\bmain\b", x) for x in block(lines, push)):
            errors.append("quality.yml: потрібно перевіряти push до main")
    return errors


def audit(root: Path) -> dict:
    folder = root / ".github" / "workflows"
    present = {p.name: p for p in folder.glob("*.yml")}
    present.update({p.name: p for p in folder.glob("*.yaml")})
    errors = [f"Відсутній обов'язковий workflow: {name}" for name in sorted(REQUIRED - present.keys())]
    for name, path in sorted(present.items()):
        errors.extend(inspect(name, path.read_text(encoding="utf-8")))
    if not present:
        errors.append("Немає жодного GitHub Actions workflow")
    return {"status": "ok" if not errors else "failed", "workflow_files": len(present), "errors": errors,
            "scope": "Перевірка YAML-передумов, НЕ реального захисту main"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = audit(args.root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
