#!/usr/bin/env python3
"""Зібрати книжкові розділи з редакторських карток.

Читає editorial/cards/*.json, бере поле ukrainian_translation і пише
books/ashtavakra-gita/rozdil-N.md у форматі, заданому rozdil-15.md.

Нічого не вигадує: якщо вірша немає — його немає, і пропуск перелічено
вгорі розділу чесно.
"""
import json, os, sys, glob, re

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
SKIP = {15}  # rozdil-15.md уже створений іншим агентом; не перезаписуємо

cards = {}
for p in glob.glob(os.path.join(ROOT, "editorial", "cards", "*.json")):
    d = json.load(open(p, encoding="utf-8"))
    ch, v = d["id"].split(".")
    cards.setdefault(int(ch), {})[int(v)] = d

os.makedirs(os.path.join(ROOT, "books", "ashtavakra-gita"), exist_ok=True)

for ch in sorted(cards):
    if ch in SKIP:
        continue
    verses = cards[ch]
    nums = sorted(verses)
    missing = [i for i in range(1, max(nums) + 1) if i not in verses]
    lines = [
        f"# Аштавакра-ґіта. Розділ {ch}",
        "",
        "> Робочий текст українського видання. Переклад власний, узятий з редакторських карток",
        f"> `editorial/cards/{ch}.*`. Санскритське читання тут не відтворюється — воно звірене",
        "> за SARIT і GRETIL і зберігається в картках. Паспорт походження: `PROVENANCE.md`.",
    ]
    if missing:
        lines.append(">")
        lines.append("> **Розділ неповний.** Немає віршів: "
                     + ", ".join(f"{ch}.{i}" for i in missing) + ".")
    lines.append("")
    for v in nums:
        lines.append(f"## {ch}.{v}")
        lines.append("")
        lines.append(verses[v]["ukrainian_translation"].strip())
        lines.append("")
    out = os.path.join(ROOT, "books", "ashtavakra-gita", f"rozdil-{ch}.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")
    print(f"rozdil-{ch}.md: {len(nums)} віршів"
          + (f", пропущено {len(missing)}" if missing else ", повний"))


def write_zmist() -> None:
    """Переписати ZMIST.md із карток, щоб зміст не відставав від них."""
    cards = {}
    for p in glob.glob(os.path.join(ROOT, "editorial", "cards", "*.json")):
        d = json.load(open(p, encoding="utf-8"))
        ch, v = d["id"].split(".")
        cards.setdefault(int(ch), set()).add(int(v))
    lines = ["# Аштавакра-ґіта — українське видання", "",
             "Робочі тексти видання, зібрані з редакторських карток `editorial/cards/`.", "",
             "| Розділ | Віршів у виданні | Стан |", "|---|---|---|"]
    total = full = 0
    for ch in range(1, 21):
        vs = cards.get(ch, set())
        n = len(vs)
        total += n
        if n == 0:
            lines.append(f"| {ch} | 0 | немає карток |")
            continue
        gaps = [i for i in range(1, max(vs) + 1) if i not in vs]
        if gaps:
            state = "неповний — немає " + ", ".join(f"{ch}.{i}" for i in gaps)
        else:
            state = "повний"
            full += 1
        lines.append(f"| [{ch}](rozdil-{ch}.md) | {n} | {state} |")
    lines += ["", f"**Разом карток: {total}.** Повних розділів: {full} із 20.", "",
              "Усі тексти — чернетки: незалежної редакторської рецензії ще не було.",
              "Санскритське читання в розділах не відтворюється: воно звірене за SARIT і GRETIL",
              "і зберігається в картках. Паспорт походження: `PROVENANCE.md`."]
    out = os.path.join(ROOT, "books", "ashtavakra-gita", "ZMIST.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"ZMIST.md: {total} карток, повних {full} із 20")


if __name__ == "__main__":
    write_zmist()
