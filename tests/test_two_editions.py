"""Офлайнові тести двох незалежних редакцій, тільки синтетичні дані."""
import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/two_editions.py"
SPEC = importlib.util.spec_from_file_location("two_editions", SCRIPT)
book = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(book)


def academic_card():
    # Окремі знаки «अ» і «आ» — НЕ санскритський вірш і не джерельний уривок.
    return {
        "id": "1.1", "status": "чернетка",
        "source": {"witness": "Синтетичний тест", "url": "https://example.org/source",
                   "locator": "приклад 1.1", "edition_note": "Штучний тест, не реальне видання",
                   "license_note": "Сторонніх рядків немає"},
        "lines": [
            {"devanagari": "अ", "transliteration_uk": "а",
             "translation_uk": "Український пробний рядок", "commentary_uk": "Авторське тестове пояснення",
             "source_locator": "1.1-а", "commentary_sources": ["https://example.org/source"]},
            {"devanagari": "आ", "transliteration_uk": "аа",
             "translation_uk": "Другий український рядок", "commentary_uk": "Друге тестове пояснення",
             "source_locator": "1.1-б", "commentary_sources": ["https://example.org/source"]},
        ],
        "research_notes": ["Жоден текст першоджерела тут не відтворено"],
        "ukrainian_parallels": [{
            "figure": "Умовний український мислитель", "work": "Штучна назва для тесту",
            "evidence_url": "https://example.org/research",
            "analogy": "Тестова аналогія", "limits": "Немає доказу прямого впливу",
        }],
        "illustration": {"brief": "Ескіз для тесту", "alt_uk": "Схема для українського читача",
                         "rights_verified": False, "rights_evidence_url": None},
        "rights": {"verified": False, "evidence_url": None, "owned_ukrainian_text": True,
                   "devanagari_permitted": False},
        "review": {"reviewer": None, "evidence_url": None},
    }


def poetic_card():
    return {
        "id": "1.1", "status": "чернетка", "author": "Автор синтетичного тесту",
        "stanzas_uk": ["Перший пробний рядок.", "Другий власний рядок."],
        "meaning_review": {"scholarly_id": "1.1", "editorial_note": "Зміст ще не перевірений"},
        "rights": {"verified": False, "evidence_url": None, "owned_ukrainian_text": True,
                   "devanagari_permitted": False},
        "review": {"reviewer": None, "evidence_url": None},
    }


class EditionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        dest = self.root / book.REGISTRY
        dest.parent.mkdir(parents=True)
        # Кількості зі спільного 20-розділового реєстру: не транскрипції віршів.
        counts = [20, 25, 14, 6, 4, 4, 5, 4, 8, 8, 8, 8, 7, 4, 20, 11, 20, 100, 8, 14]
        with dest.open("w", encoding="utf-8", newline="") as fd:
            writer = csv.writer(fd)
            writer.writerow(("глава", "GRETIL_віршів"))
            for n, count in enumerate(counts, 1):
                writer.writerow((n, count))
            writer.writerow(("разом", sum(counts)))

    def save(self, dirname, card):
        directory = self.root / dirname
        directory.mkdir(parents=True, exist_ok=True)
        (directory / (card["id"] + ".json")).write_text(
            json.dumps(card, ensure_ascii=False), encoding="utf-8")

    def test_registry_has_298_and_20(self):
        ids = book.expected_verses(self.root)
        self.assertEqual(len(ids), 298)
        self.assertIn("18.100", ids)

    def test_empty_draft_is_honest(self):
        _, _, result = book.audit(self.root)
        self.assertEqual(result["академічних"], 0)
        self.assertEqual(result["поетичних"], 0)

    def test_partial_draft_works_without_claiming_release(self):
        self.save(book.ACADEMIC, academic_card())
        self.save(book.POETIC, poetic_card())
        a, p, r = book.audit(self.root)
        self.assertEqual(r["помилки"], [])
        self.assertEqual((len(a), len(p)), (1, 1))

    def test_release_rejects_missing_297_verses(self):
        self.save(book.ACADEMIC, academic_card())
        self.save(book.POETIC, poetic_card())
        _, _, r = book.audit(self.root, release=True)
        self.assertTrue(any("297" in e for e in r["помилки"]))

    def test_release_rejects_missing_reviews(self):
        self.assertTrue(any("рецензування" in e for e in book.academic(academic_card(), True)))

    def test_release_rejects_unverified_devanagari(self):
        self.assertTrue(any("деванагарі" in e for e in book.academic(academic_card(), True)))

    def test_release_rejects_illustration_without_rights(self):
        self.assertTrue(any("права ілюстрації" in e for e in book.academic(academic_card(), True)))

    def test_devanagari_required_per_line(self):
        a = academic_card()
        a["lines"][0]["devanagari"] = "iast-only"
        self.assertTrue(any("devanagari" in e for e in book.academic(a, False)))

    def test_ukrainian_transliteration_not_iast(self):
        a = academic_card()
        a["lines"][0]["transliteration_uk"] = "ātmā"
        self.assertTrue(any("transliteration_uk" in e for e in book.academic(a, False)))

    def test_commentary_has_verifiable_source(self):
        a = academic_card()
        a["lines"][0]["commentary_sources"] = []
        self.assertTrue(any("HTTPS-джерело" in e for e in book.academic(a, False)))

    def test_ukrainian_parallels_explain_limits(self):
        a = academic_card()
        a["ukrainian_parallels"][0]["limits"] = ""
        self.assertTrue(any("межі культурної паралелі" in e for e in book.academic(a, False)))

    def test_poetic_links_matching_scholarly_verse(self):
        p = poetic_card()
        p["meaning_review"]["scholarly_id"] = "2.1"
        self.assertTrue(any("зіставлення" in e for e in book.poetic(p, False)))

    def test_poetry_must_be_ukrainian(self):
        p = poetic_card()
        p["stanzas_uk"] = ["śānti"]
        self.assertTrue(any("українські поетичні" in e for e in book.poetic(p, False)))

    def test_unknown_fields_blocked(self):
        a = academic_card()
        a["rubber_stamped"] = True
        self.assertTrue(any("невідоме поле" in e for e in book.academic(a, False)))

    def test_unknown_verse_path_blocked(self):
        a = academic_card()
        a["id"] = "30.1"
        self.save(book.ACADEMIC, a)
        _, _, r = book.audit(self.root)
        self.assertTrue(any("недопустимий шлях" in e for e in r["помилки"]))

    def test_symlink_is_forbidden(self):
        original = self.root / "unsafe.json"
        original.write_text(json.dumps(academic_card(), ensure_ascii=False), encoding="utf-8")
        directory = self.root / book.ACADEMIC
        directory.mkdir(parents=True)
        (directory / "1.1.json").symlink_to(original)
        _, _, r = book.audit(self.root)
        self.assertTrue(any("недопустимий шлях" in e for e in r["помилки"]))

    def test_preview_hides_devanagari_until_permission(self):
        folder = self.root / "preview"
        book.preview({"1.1": academic_card()}, {"1.1": poetic_card()}, folder)
        scholarly = (folder / "akademichna-chernetka.md").read_text(encoding="utf-8")
        literary = (folder / "poetychna-chernetka.md").read_text(encoding="utf-8")
        self.assertIn("Приховано", scholarly)
        self.assertNotIn("**Рядок 1, деванагарі:** अ", scholarly)
        self.assertIn("Українська транслітерація", scholarly)
        self.assertIn("Межі", scholarly)
        self.assertIn("Перший пробний", literary)

    def test_release_requires_rights_even_with_review(self):
        c = academic_card()
        c["status"] = "рецензовано"
        c["review"] = {"reviewer": "Рецензент", "evidence_url": "https://example.org/review"}
        self.assertTrue(any("права на український текст" in e for e in book.academic(c, True)))


    def test_rights_flag_without_https_evidence_rejected(self):
        a = academic_card()
        a["rights"]["verified"] = True
        self.assertTrue(any("без HTTPS-доказу" in e for e in book.academic(a, False)))

    def test_devanagari_permission_without_verified_rights_rejected(self):
        a = academic_card()
        a["rights"]["devanagari_permitted"] = True
        self.assertTrue(any("дозвіл на деванагарі" in e for e in book.academic(a, False)))

    def test_preview_never_leaks_devanagari_with_flags_but_no_evidence(self):
        a = academic_card()
        a["rights"]["verified"] = True
        a["rights"]["devanagari_permitted"] = True
        folder = self.root / "preview-flags"
        book.preview({"1.1": a}, {}, folder)
        txt = (folder / "akademichna-chernetka.md").read_text(encoding="utf-8")
        self.assertIn("Приховано", txt)
        self.assertNotIn("**Рядок 1, деванагарі:** अ", txt)

    def test_preview_can_print_devanagari_with_documented_permission(self):
        a = academic_card()
        a["rights"].update({"verified": True, "devanagari_permitted": True,
                            "evidence_url": "https://example.org/evidence"})
        folder = self.root / "preview-proved"
        book.preview({"1.1": a}, {}, folder)
        txt = (folder / "akademichna-chernetka.md").read_text(encoding="utf-8")
        self.assertIn("**Рядок 1, деванагарі:** अ", txt)

    def test_preview_hides_ukrainian_fields_if_ownership_is_false(self):
        a = academic_card()
        a["rights"]["owned_ukrainian_text"] = False
        folder = self.root / "preview-foreign-translation"
        book.preview({"1.1": a}, {}, folder)
        txt = (folder / "akademichna-chernetka.md").read_text(encoding="utf-8")
        self.assertIn("Приховано: права на український текст", txt)
        self.assertNotIn("Український пробний рядок", txt)
        self.assertNotIn("Авторське тестове пояснення", txt)

    def test_preview_hides_unowned_poetry(self):
        p = poetic_card()
        p["rights"]["owned_ukrainian_text"] = False
        folder = self.root / "preview-unowned-poetry"
        book.preview({}, {"1.1": p}, folder)
        txt = (folder / "poetychna-chernetka.md").read_text(encoding="utf-8")
        self.assertIn("Приховано: права на український поетичний", txt)
        self.assertNotIn("Перший пробний рядок", txt)

    def test_symlink_directory_is_forbidden(self):
        other = self.root / "outside"
        other.mkdir()
        (self.root / book.ACADEMIC).parent.mkdir(parents=True, exist_ok=True)
        (self.root / book.ACADEMIC).symlink_to(other, target_is_directory=True)
        _, _, report = book.audit(self.root)
        self.assertTrue(any("символьний каталог" in e for e in report["помилки"]))

    def test_symlink_editorial_parent_is_forbidden(self):
        other = self.root / "foreign-editorial"
        (other / "academic-edition").mkdir(parents=True)
        (self.root / "editorial").symlink_to(other, target_is_directory=True)
        _, _, report = book.audit(self.root)
        self.assertTrue(any("символьний каталог" in e for e in report["помилки"]))


if __name__ == "__main__":
    unittest.main()
