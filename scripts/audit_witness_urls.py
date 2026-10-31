#!/usr/bin/env python3
"""Офлайновий контроль адрес текстових свідків; не перевірка тексту або прав."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
CARDS = ROOT / "editorial" / "cards"
GRETIL_FILE = "sa_aSTAvakragItA"
SHA40 = re.compile(r"^[0-9a-fA-F]{40}$")
REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
GRETIL_HOSTS = {"www.gretil.uni-goettingen.de", "gretil.uni-goettingen.de", "gretil.sub.uni-goettingen.de"}
TEXTGRID_HOSTS = {"www.textgridrep.org", "textgridrep.org"}


def inspect_url(witness: str, value: object) -> tuple[str | None, list[str]]:
    """Повернути помилку чи попередження, не роблячи HTTP-запитів."""
    notes: list[str] = []
    if not isinstance(value, str) or not value.strip():
        return "потрібна непорожня адреса HTTPS", notes
    # urlsplit() вилучає CR/LF/TAB до перевірки: відхиляємо сирі керівні символи.
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        return "керівні символи в URL свідка заборонені", notes
    try:
        parts = urlsplit(value)
        host, port = parts.hostname, parts.port
    except ValueError:
        return "некоректна адреса", notes
    if (parts.scheme != "https" or not host or parts.username is not None
            or parts.password is not None or port is not None
            or parts.query or parts.fragment or "%" in parts.path
            or "\\" in parts.path or parts.path.startswith("//")):
        return "потрібна HTTPS-адреса без авторизації, порту, query, fragment і маскування шляху", notes

    path = parts.path
    if witness == "sarit":
        if host == "github.com":
            match = re.fullmatch(r"/sarit/SARIT-corpus/blob/([^/]+)/astavakragita\.xml", path)
        elif host == "raw.githubusercontent.com":
            match = re.fullmatch(r"/sarit/SARIT-corpus/([^/]+)/astavakragita\.xml", path)
        else:
            match = None
        if match is None or REF.fullmatch(match.group(1)) is None:
            return "SARIT: адреса має вказувати на sarit/SARIT-corpus та astavakragita.xml", notes
        if SHA40.fullmatch(match.group(1)) is None:
            notes.append("SARIT: ref не прикріплений до SHA, вміст може змінитися")
        return None, notes

    if witness != "gretil":
        return "невідомий тип свідка", notes

    official = {
        f"/gretil/corpustei/transformations/html/{GRETIL_FILE}.htm",
        f"/gretil/corpustei/transformations/plaintext/{GRETIL_FILE}.txt",
        f"/gretil/corpustei/{GRETIL_FILE}.xml",
    }
    if host in GRETIL_HOSTS and path in official:
        return None, notes
    if host in TEXTGRID_HOSTS and path == "/browse/49ks7.0":
        notes.append("TextGrid: сталий ідентифікатор запису, але не SHA байтів")
        return None, notes
    if host == "tylergneill.github.io" and path in {
        f"/gretil-mirror/gretil/corpustei/transformations/html/{GRETIL_FILE}.htm",
        f"/gretil-mirror/gretil/corpustei/transformations/plaintext/{GRETIL_FILE}.txt",
    }:
        notes.append("GRETIL: дзеркало, тотожність офіційній версії не підтверджена")
        return None, notes
    if host in {"github.com", "raw.githubusercontent.com"}:
        if host == "github.com":
            expr = rf"/INDOLOGY/GRETIL-mirror/blob/([^/]+)/gretil\.sub\.uni-goettingen\.de/gretil/corpustei/{GRETIL_FILE}\.xml"
        else:
            expr = rf"/INDOLOGY/GRETIL-mirror/([^/]+)/gretil\.sub\.uni-goettingen\.de/gretil/corpustei/{GRETIL_FILE}\.xml"
        match = re.fullmatch(expr, path)
        if match and REF.fullmatch(match.group(1)):
            notes.append("GRETIL: архівне дзеркало, тотожність офіційній версії не підтверджена")
            if not SHA40.fullmatch(match.group(1)):
                notes.append("GRETIL: ref дзеркала не прикріплений до SHA")
            return None, notes
    return "GRETIL: адреса не належить до задокументованих адрес конкретного твору", notes


def audit(folder: Path) -> dict[str, object]:
    errors: list[str] = []
    warnings: list[str] = []
    count = 0
    if folder.is_symlink():
        errors.append(f"{folder}: каталог карток є символічним посиланням")
    elif folder.exists() and not folder.is_dir():
        errors.append(f"{folder}: очікується каталог")
    elif folder.is_dir():
        # rglob("*.json") НЕ спускається у вкладені символічні каталоги.
        # Навіть якщо такі картки приховані від обліку, сам symlink має бути помилкою.
        for entry in sorted(folder.rglob("*")):
            if entry.is_symlink():
                errors.append(f"{entry.relative_to(folder).as_posix()}: символічне посилання в каталозі карток")
        for file in sorted(folder.rglob("*.json")):
            count += 1
            name = file.relative_to(folder).as_posix()
            if file.is_symlink():
                # Помилку вже додано під час перевірки всіх файлових шляхів.
                continue
            try:
                card = json.loads(file.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                errors.append(f"{name}: неправильний JSON: {exc}")
                continue
            sources = card.get("sources") if isinstance(card, dict) else None
            if not isinstance(sources, dict):
                errors.append(f"{name}: відсутній об'єкт sources")
                continue
            for witness in ("gretil", "sarit"):
                source = sources.get(witness)
                url = source.get("url") if isinstance(source, dict) else None
                error, notes = inspect_url(witness, url)
                if error:
                    errors.append(f"{name} / {witness}: {error}")
                warnings.extend(f"{name} / {witness}: {note}" for note in notes)
    return {
        "status": "failed" if errors else "ok",
        "cards": count,
        "errors": errors,
        "warnings": warnings,
        "scope": "Офлайнова форма адрес URL; НЕ перевірка мережі, текстів, прав чи рецензії",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cards", type=Path, default=CARDS)
    args = parser.parse_args()
    result = audit(args.cards)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
