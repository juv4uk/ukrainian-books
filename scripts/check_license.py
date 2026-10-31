#!/usr/bin/env python3
"""Офлайн-контроль незмінності ліцензії «ВОЛЬНІСТЬ».

Перевіряє три речі, яких не покриває check_project.py:

1. ``LICENSE`` і ``VOLNOST.md`` побайтово однакові;
2. обидва файли збігаються із **закріпленим канонічним SHA-256**
   тексту з ``juv4uk/sens/LICENSE``;
3. заголовок і розмір відповідають канону.

Навіщо хеш: без нього можна однаково змінити обидва файли, і
перевірка «вони рівні» пройде. Хеш робить підміну тексту неможливою
без явної зміни цього скрипта.

Мережа не використовується: канонічний хеш закріплено тут.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Канонічний текст «ВОЛЬНОСТІ» з juv4uk/sens.
CANONICAL_SHA256 = "395fc9e43412edde4884568d5b0949f1d7c992f6503946746556eb1bb52b9bb0"
CANONICAL_BYTES = 649
CANONICAL_SOURCE = "https://github.com/juv4uk/sens/blob/main/LICENSE"
CANONICAL_TAKEN = "2026-10-31"
HEADER = "ВОЛЬНІСТЬ\n\n"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def check(root: Path) -> list[str]:
    """Повертає перелік порушень; порожній список означає успіх."""
    errors: list[str] = []
    license_path = root / "LICENSE"
    copy_path = root / "VOLNOST.md"

    # is_file() переходить за символьними посиланнями: правильний хеш
    # зовнішнього файла не доводить наявності канону у самому Git-дереві.
    for name, path in (("LICENSE", license_path), ("VOLNOST.md", copy_path)):
        if path.is_symlink():
            errors.append(f"{name}: символічне посилання не дозволено")
        elif not path.is_file():
            errors.append(f"Відсутній {name}")
    if errors:
        return errors

    license_data = license_path.read_bytes()
    copy_data = copy_path.read_bytes()

    if license_data != copy_data:
        errors.append("LICENSE і VOLNOST.md не збігаються побайтово")

    for name, data in (("LICENSE", license_data), ("VOLNOST.md", copy_data)):
        actual = digest(data)
        if actual != CANONICAL_SHA256:
            errors.append(
                f"{name}: SHA-256 {actual} не збігається з канонічним "
                f"{CANONICAL_SHA256} (джерело: {CANONICAL_SOURCE}, "
                f"знято {CANONICAL_TAKEN})"
            )
        if len(data) != CANONICAL_BYTES:
            errors.append(
                f"{name}: {len(data)} байтів замість канонічних {CANONICAL_BYTES}"
            )

    text = license_data.decode("utf-8", errors="replace")
    if not text.startswith(HEADER):
        errors.append("Неправильний заголовок канонічної ліцензії")
    if "SPDX-License-Identifier" in text:
        errors.append(
            "У тексті з'явився SPDX-ідентифікатор — «ВОЛЬНІСТЬ» не має "
            "офіційного SPDX без відповідного визнання"
        )
    if not text.endswith("\n"):
        errors.append("Файл не закінчується переводом рядка")

    return errors


def _self_test() -> list[str]:
    """Негативні перевірки на тимчасових копіях. Реальні файли не чіпаються."""
    failures: list[str] = []
    good = (ROOT / "LICENSE").read_bytes()

    def case(name: str, license_bytes: bytes, copy_bytes: bytes | None = None,
             expect_error: str | None = None) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "LICENSE").write_bytes(license_bytes)
            (root / "VOLNOST.md").write_bytes(
                license_bytes if copy_bytes is None else copy_bytes
            )
            errors = check(root)
            if expect_error is None:
                if errors:
                    failures.append(f"{name}: очікували успіх, отримали {errors}")
            elif not any(expect_error in e for e in errors):
                failures.append(f"{name}: очікували «{expect_error}», отримали {errors}")

    case("канон проходить", good)
    case("підміна одного символу",
         good.replace("волю".encode(), "воля".encode(), 1),
         expect_error="не збігається з канонічним")
    case("зайвий рядок", good + "\nДодаткова умова.\n".encode(),
         expect_error="не збігається з канонічним")
    case("зміна заголовка",
         good.replace("ВОЛЬНІСТЬ".encode(), "СВОБОДА".encode(), 1),
         expect_error="Неправильний заголовок")
    case("розбіжність копій", good, good + b"\n",
         expect_error="не збігаються побайтово")
    case("SPDX-ідентифікатор",
         good + "SPDX-License-Identifier: MIT\n".encode(),
         expect_error="SPDX")
    case("без фінального переводу рядка", good.rstrip(b"\n"),
         expect_error="не закінчується переводом рядка")
    case("порожній файл", b"", expect_error="не збігається з канонічним")

    with tempfile.TemporaryDirectory() as tmp:
        if not any("Відсутній LICENSE" in e for e in check(Path(tmp))):
            failures.append("порожній каталог: не виявлено відсутність LICENSE")

    # Символьне посилання на точні канонічні байти не є самостійною
    # копією ліцензії у Git. Обидва випадки мають бути відхилені навіть
    # тоді, коли всі байтові/хеш-перевірки інакше пройшли б успішно.
    for link_name in ("LICENSE", "VOLNOST.md"):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "canon").write_bytes(good)
            other = "VOLNOST.md" if link_name == "LICENSE" else "LICENSE"
            (root / other).write_bytes(good)
            try:
                (root / link_name).symlink_to(root / "canon")
            except (OSError, NotImplementedError) as exc:
                failures.append(f"{link_name}: не вдалося створити тестове посилання: {exc}")
                continue
            if not any("символічне посилання" in e for e in check(root)):
                failures.append(f"{link_name}: канонічний symlink пройшов перевірку")

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "VOLNOST.md").write_bytes(good)
        try:
            (root / "LICENSE").symlink_to(root / "missing")
        except (OSError, NotImplementedError) as exc:
            failures.append(f"пошкоджене посилання: неможливо створити тест: {exc}")
        else:
            if not any("символічне посилання" in e for e in check(root)):
                failures.append("пошкоджене посилання LICENSE не виявлено")

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true",
                        help="прогнати негативні перевірки на тимчасових копіях")
    parser.add_argument("--root", type=Path, default=ROOT,
                        help="корінь репозиторію (типово — батько scripts/)")
    args = parser.parse_args()

    if args.self_test:
        failures = _self_test()
        if failures:
            for item in failures:
                print(f"САМОПЕРЕВІРКА-ПРОВАЛ: {item}")
            return 1
        print("САМОПЕРЕВІРКА-OK: 11 негативних випадків і 1 позитивний")
        return 0

    errors = check(args.root)
    if errors:
        for item in errors:
            print(f"ЛІЦЕНЗІЯ-ПРОВАЛ: {item}")
        return 1
    print(
        f"ЛІЦЕНЗІЯ-OK: LICENSE і VOLNOST.md збігаються з каноном "
        f"{CANONICAL_SHA256[:16]}… ({CANONICAL_BYTES} байтів)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
