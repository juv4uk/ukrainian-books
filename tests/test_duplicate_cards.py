"""Негативні тести перевірки дублів: штучний дубль ловиться, унікальні — ні.

Тести синтетичні: будують тимчасове дерево `research/` + `editorial/cards/`,
не торкаються справжніх карток і не залежать від їхньої кількості в `main`.
"""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts.check_duplicate_cards import collect, json_card_verse, run, split_duplicates


class DuplicateCardTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.research = self.root / "research" / "ashtavakra"
        self.cards = self.root / "editorial" / "cards"
        self.research.mkdir(parents=True)
        self.cards.mkdir(parents=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # --- допоміжні побудовники -------------------------------------------------

    def card(self, name: str, verse: str, text: str = "власний тестовий текст") -> Path:
        path = self.cards / name
        path.write_text(json.dumps({
            "schema_version": 1,
            "id": verse,
            "work": "Аштавакра-ґіта",
            "ukrainian_translation": text,
        }, ensure_ascii=False), encoding="utf-8")
        return path

    def note(self, name: str, title: str) -> Path:
        path = self.research / name
        path.write_text(f"# {title}\n\nВласна синтетична примітка.\n", encoding="utf-8")
        return path

    def report(self, strict: bool) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = run(research=self.research, cards=self.cards, strict=strict)
        return code, out.getvalue(), err.getvalue()

    # --- негативні сценарії ----------------------------------------------------

    def test_unique_json_cards_are_not_duplicates(self) -> None:
        """Різні вірші в JSON — не дубль: і звіт, і --strict зелені."""
        self.card("2.4.json", "2.4")
        self.card("2.5.json", "2.5")
        self.card("4.3.json", "4.3")

        by_verse = collect(self.research, self.cards)
        self.assertEqual(sorted(by_verse), ["2.4", "2.5", "4.3"])
        duplicates, overlaps = split_duplicates(by_verse)
        self.assertEqual(duplicates, {})
        self.assertEqual(overlaps, {})

        for strict in (False, True):
            code, out, err = self.report(strict)
            self.assertEqual(code, 0, out + err)
            self.assertIn("дублів немає", out)

    def test_empty_folders_do_not_fail(self) -> None:
        """Немає карток — немає збою (перевірка не залежить від наявності тек)."""
        code, out, _ = self.report(strict=True)
        self.assertEqual(code, 0)
        self.assertIn("карток=0", out)

    def test_verse_comes_from_json_id_not_from_filename(self) -> None:
        """Номер вірша береться з поля `id`, а не з імені файлу."""
        path = self.card("not-a-verse-name.json", "3.1")
        self.assertEqual(json_card_verse(path), "3.1")

    def test_unreadable_json_is_skipped_without_crash(self) -> None:
        """Зіпсований JSON не валить перевірку дублів — цим опікується схема."""
        (self.cards / "broken.json").write_text("{ не json", encoding="utf-8")
        self.card("2.4.json", "2.4")
        code, out, err = self.report(strict=True)
        self.assertEqual(code, 0, err)
        self.assertIn("ДУБЛІ-ПРОПУЩЕНО", err)
        self.assertIn("карток=1", out)

    # --- позитивні сценарії: справжній дубль мусить ловитися --------------------

    def test_synthetic_json_duplicate_is_detected_and_fails_strict(self) -> None:
        """Дві JSON-картки на той самий вірш — дубль; у --strict це збій."""
        self.card("2.4.json", "2.4")
        self.card("2.4-copy.json", "2.4", text="інший текст тієї самої картки")

        by_verse = collect(self.research, self.cards)
        self.assertEqual(len(by_verse["2.4"]), 2)
        duplicates, overlaps = split_duplicates(by_verse)
        self.assertIn("2.4", duplicates)
        self.assertEqual(overlaps, {})

        code, out, _ = self.report(strict=False)
        self.assertEqual(code, 0, "типовий режим лише звітує")
        self.assertIn("ДУБЛІ-ЗНАЙДЕНО вірш 2.4", out)

        code, out, err = self.report(strict=True)
        self.assertEqual(code, 1, "у --strict дубль мусить валити перевірку")
        self.assertIn("ДУБЛІ-ЗБІЙ", err)

    def test_three_versions_of_one_verse_are_detected(self) -> None:
        """Три версії однієї картки (випадок 2.4) видно як один дубль на три файли."""
        for name in ("2.4.json", "2.4-pr50.json", "2.4-pr162.json"):
            self.card(name, "2.4")
        duplicates, _ = split_duplicates(collect(self.research, self.cards))
        self.assertEqual(len(duplicates["2.4"]), 3)

    def test_calendar_dates_in_headings_are_not_verses(self) -> None:
        """Дати 31.10.2026 і 1.10.2026 — не вірші, навіть якщо вони в H1."""
        self.note("bibliography-supplement-2026-10-31.md",
                  "Бібліографія — звірено 31.10.2026")
        self.note("young-1991-corpus-check.md",
                  "Перевірка видання станом на 31.10.2026")
        self.note("source-date.md", "Нотатки від 1.10.2026")
        self.note("verse-31-10-invalid.md", "Помилкова глава 31.10")

        self.assertEqual(collect(self.research, self.cards), {})
        code, out, err = self.report(strict=True)
        self.assertEqual(code, 0, out + err)
        self.assertIn("дублів немає", out)

    def test_real_verse_numbers_in_headings_are_recognized(self) -> None:
        """Звичайні заголовки 1.2 і 15.7 залишаються в реєстрі."""
        self.note("first-note.md", "Вірш 1.2: лексичний аналіз")
        self.note("second-note.md", "Аштавакра-ґіта 15.7: сандгі")
        self.note("third-note.md", "15.8: незалежна примітка")

        by_verse = collect(self.research, self.cards)
        self.assertEqual(sorted(by_verse), ["1.2", "15.7", "15.8"])
        self.assertEqual(self.report(strict=True)[0], 0)

    def test_markdown_duplicate_logic_still_works(self) -> None:
        """Наявна логіка для markdown не зламана: два .md на один вірш — дубль."""
        self.note("verse-1-5-ashrama-varna.md", "Аштавакра-ґіта 1.5: перша картка")
        self.note("verse-1-5-varna-ashrama.md", "Аштавакра-ґіта 1.5: друга картка")
        duplicates, _ = split_duplicates(collect(self.research, self.cards))
        self.assertIn("1.5", duplicates)
        self.assertEqual(self.report(strict=True)[0], 1)

    def test_markdown_range_cards_are_not_duplicates(self) -> None:
        """Дві картки-діапазони на той самий діапазон не стають дублем вірша 1.6."""
        self.note("verses-1-6-to-1-10.md", "Аштавакра-ґіта 1.6–1.10: перші")
        self.note("notes-1-6-to-1-10.md", "Аштавакра-ґіта 1.6–1.10: другі")
        duplicates, overlaps = split_duplicates(collect(self.research, self.cards))
        self.assertEqual(duplicates, {})
        self.assertEqual(overlaps, {})

    def test_json_and_markdown_for_one_verse_is_overlap_not_failure(self) -> None:
        """Картка + примітка до того самого вірша — перетин, а не збій.

        Це навмисна межа: `research/` містить дослідницьку примітку, а не другу
        картку. Перетин друкується, але `--strict` на ньому не падає, інакше
        гейт був би червоний на власному `main` (вірш 1.2).
        """
        self.card("1.2.json", "1.2")
        self.note("verse-1-2-tosa.md", "Вірш 1.2: п'ять чеснот і `toṣa`")

        duplicates, overlaps = split_duplicates(collect(self.research, self.cards))
        self.assertEqual(duplicates, {})
        self.assertIn("1.2", overlaps)

        code, out, _ = self.report(strict=True)
        self.assertEqual(code, 0)
        self.assertIn("ДУБЛІ-ПЕРЕТИН вірш 1.2", out)

    def test_two_json_plus_note_still_counts_as_duplicate(self) -> None:
        """Дві JSON-картки й примітка: перетин не маскує справжній дубль."""
        self.card("1.2.json", "1.2")
        self.card("1.2-other.json", "1.2")
        self.note("verse-1-2-tosa.md", "Вірш 1.2: примітка")
        duplicates, overlaps = split_duplicates(collect(self.research, self.cards))
        self.assertIn("1.2", duplicates)
        self.assertNotIn("1.2", overlaps)
        self.assertEqual(self.report(strict=True)[0], 1)


if __name__ == "__main__":
    unittest.main()
