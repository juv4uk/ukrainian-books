"""Негативні та позитивні свідки для контролю цілості видання.

Кожен тест будує мінімальне дерево в тимчасовому каталозі, псує в ньому
рівно одну річ і перевіряє, що гейт це назвав. Без негативних свідків
зелений результат нічого не доводить.
"""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "scripts/check_book.py"
SPEC = importlib.util.spec_from_file_location("check_book", SOURCE)
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


def make_tree(tmp: Path, cards: dict, rozdil: dict, zmist: str) -> Path:
    (tmp / "editorial" / "cards").mkdir(parents=True)
    for vid, text in cards.items():
        (tmp / "editorial" / "cards" / f"{vid}.json").write_text(
            json.dumps({"id": vid, "ukrainian_translation": text}, ensure_ascii=False),
            encoding="utf-8")
    book = tmp / "books" / "ashtavakra-gita"
    book.mkdir(parents=True)
    for chapter, body in rozdil.items():
        (book / f"rozdil-{chapter}.md").write_text(body, encoding="utf-8")
    (book / "ZMIST.md").write_text(zmist, encoding="utf-8")
    return tmp


def chapter_md(chapter: int, verses: dict) -> str:
    out = [f"# Аштавакра-ґіта. Розділ {chapter}", ""]
    for v, text in verses.items():
        out += [f"## {chapter}.{v}", "", text, ""]
    return "\n".join(out)


ZMIST_OK = "| Розділ | Віршів | Стан |\n|---|---|---|\n| [1](rozdil-1.md) | 2 | повний |\n"


class BookIntegrityTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_consistent_tree_passes(self):
        make_tree(self.tmp,
                  {"1.1": "Перший.", "1.2": "Другий."},
                  {1: chapter_md(1, {1: "Перший.", 2: "Другий."})},
                  ZMIST_OK)
        self.assertEqual(checker.audit(self.tmp), [])

    def test_missing_verse_in_book_is_named(self):
        make_tree(self.tmp,
                  {"1.1": "Перший.", "1.2": "Другий."},
                  {1: chapter_md(1, {1: "Перший."})},
                  ZMIST_OK)
        errors = checker.audit(self.tmp)
        self.assertTrue(any("немає вірша 1.2" in e for e in errors), errors)

    def test_extra_verse_in_book_is_named(self):
        make_tree(self.tmp,
                  {"1.1": "Перший."},
                  {1: chapter_md(1, {1: "Перший.", 2: "Зайвий."})},
                  ZMIST_OK)
        errors = checker.audit(self.tmp)
        self.assertTrue(any("зайвий вірш 1.2" in e for e in errors), errors)

    def test_text_diverged_from_card_is_named(self):
        make_tree(self.tmp,
                  {"1.1": "Перший.", "1.2": "Другий."},
                  {1: chapter_md(1, {1: "Перший.", 2: "Змінений."})},
                  ZMIST_OK)
        errors = checker.audit(self.tmp)
        self.assertTrue(any("розійшовся з карткою" in e for e in errors), errors)

    def test_zmist_claims_full_but_gap_exists(self):
        """Саме та помилка, яку я зробив: глава 1 названа повною, а 1.2 немає."""
        make_tree(self.tmp,
                  {"1.1": "Перший.", "1.3": "Третій."},
                  {1: chapter_md(1, {1: "Перший.", 3: "Третій."})},
                  ZMIST_OK)
        errors = checker.audit(self.tmp)
        self.assertTrue(any("названо повним, але немає 1.2" in e for e in errors), errors)

    def test_chapter_with_cards_but_no_file_is_named(self):
        make_tree(self.tmp,
                  {"1.1": "Перший.", "1.2": "Другий.", "2.1": "Третій.", "2.2": "Четвертий."},
                  {1: chapter_md(1, {1: "Перший.", 2: "Другий."})},
                  ZMIST_OK + "| [2](rozdil-2.md) | 2 | повний |\n")
        errors = checker.audit(self.tmp)
        self.assertTrue(any("немає файла, хоч є 2 карток" in e for e in errors), errors)

    def test_missing_chapter_row_in_zmist_is_named(self):
        make_tree(self.tmp,
                  {"1.1": "Перший.", "1.2": "Другий."},
                  {1: chapter_md(1, {1: "Перший.", 2: "Другий."})},
                  "| Розділ | Віршів | Стан |\n|---|---|---|\n")
        errors = checker.audit(self.tmp)
        self.assertTrue(any("немає рядка для розділу 1" in e for e in errors), errors)

    def test_absent_book_directory_is_error(self):
        (self.tmp / "editorial" / "cards").mkdir(parents=True)
        (self.tmp / "editorial" / "cards" / "1.1.json").write_text(
            json.dumps({"id": "1.1", "ukrainian_translation": "X."}), encoding="utf-8")
        errors = checker.audit(self.tmp)
        self.assertTrue(any("каталогу видання немає" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
