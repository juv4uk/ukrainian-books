#!/usr/bin/env python3
"""Однаковий український текст у різних віршах — дефект, якщо санскрит різний.

Навіщо. Рій пише картки паралельно, і найдешевший спосіб зіпсувати корпус —
скопіювати переклад сусіднього вірша. Перевірити це очима на 240 картках
неможливо, а машина робить це за секунду.

Головна тонкість: однаковий переклад буває ЗАКОНОМІРНИМ. У «Аштавакра-ґіті»
є сталі зачини, що повторюються дослівно в різних главах — наприклад,
`kva dharmaḥ kva ca vā kāmaḥ kva cārthaḥ kva vivekatā` відкриває і 18.12,
і 19.2. Тому збіг перекладу вважається дефектом ЛИШЕ тоді, коли санскрит
у цих віршах різний. Якщо санскрит той самий — це рефрен, і гейт мовчить.

Перевіряється:
  1. точний збіг нормалізованого перекладу при різному санскриті;
  2. збіг перших N слів перекладу при різному санскриті (часткова копія).

Нічого не виправляє: називає пари й причину.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

HEAD_WORDS = 8  # скільки перших слів вважати підозрілою спільною основою
# Спільний початок санскриту такої довжини означає сталий зачин, а не збіг.
SHARED_SANSKRIT_PREFIX = 20


def shares_formula(a: str, b: str) -> bool:
    """Чи мають вірші спільний *засвідчений* санскритський зачин."""
    # Відсутність санскриту в обох картках не доводить існування рефрену.
    # Не приховуємо підозру на копіювання за відсутності вихідних даних.
    if not a or not b:
        return False
    if a == b:
        return True
    limit = min(len(a), len(b))
    common = 0
    while common < limit and a[common] == b[common]:
        common += 1
    return common >= SHARED_SANSKRIT_PREFIX


def normalise(text: str) -> str:
    """Звести текст до порівнюваного вигляду: без регістру й пунктуації."""
    low = text.casefold()
    low = re.sub(r"[^\wа-яїієґʼ' ]+", " ", low)
    return re.sub(r"\s+", " ", low).strip()


def normalise_sanskrit(text: str) -> str:
    """Звести санскрит до латиниці без діакритики.

    Потрібно, бо той самий зачин у різних картках записаний по-різному:
    `nāham` і `nāhaṃ` — це те саме слово, але посимвольний збіг рветься
    на третьому знакові. Без цього рефрени виглядали б як копіювання.
    """
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"[^a-z ]+", " ", stripped).strip()


def load(root: Path) -> dict[str, tuple[str, str]]:
    """id -> (нормалізований переклад, нормалізований санскрит)."""
    cards: dict[str, tuple[str, str]] = {}
    for path in sorted((root / "editorial" / "cards").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        cards[data["id"]] = (normalise(data["ukrainian_translation"]),
                             normalise_sanskrit(data.get("sanskrit") or ""))
    return cards


def audit(root: Path, head_words: int = HEAD_WORDS) -> list[str]:
    cards = load(root)
    errors: list[str] = []
    seen: dict[str, list[str]] = defaultdict(list)
    for vid, (ukr, _) in cards.items():
        seen[ukr].append(vid)
    for ukr, ids in sorted(seen.items()):
        if len(ids) < 2:
            continue
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = ids[i], ids[j]
                if shares_formula(cards[a][1], cards[b][1]):
                    continue  # спільний зачин санскриту — закономірний рефрен
                errors.append(f"{a} і {b}: однаковий переклад при різному санскриті")

    heads: dict[str, list[str]] = defaultdict(list)
    for vid, (ukr, _) in cards.items():
        words = ukr.split()
        if len(words) >= head_words:
            heads[" ".join(words[:head_words])].append(vid)
    for head, ids in sorted(heads.items()):
        if len(ids) < 2:
            continue
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = ids[i], ids[j]
                if shares_formula(cards[a][1], cards[b][1]):
                    continue
                if cards[a][0] == cards[b][0]:
                    continue  # уже названо як точний збіг
                errors.append(
                    f"{a} і {b}: спільний початок перекладу «{head}» при різному санскриті")
    return errors


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    errors = audit(root)
    if errors:
        print(f"ПОМИЛКА: підозра на копіювання перекладу ({len(errors)}):")
        for e in errors:
            print("  -", e)
        return 1
    cards = load(root)
    print(f"OK: {len(cards)} карток, однакових перекладів при різному санскриті немає")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
