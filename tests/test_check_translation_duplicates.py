"""Свідки для контролю однакових перекладів.

Найважливіший тест — `test_refrain_with_same_sanskrit_passes`: він фіксує,
що гейт НЕ вважає дефектом закономірний повтор, як у 18.12 і 19.2, де
перший піввірш санскриту збігається дослівно.
"""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "scripts/check_translation_duplicates.py"
SPEC = importlib.util.spec_from_file_location("dup_check", SOURCE)
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


def tree(tmp: Path, cards: dict) -> Path:
    d = tmp / "editorial" / "cards"
    d.mkdir(parents=True)
    for vid, (ukr, sa) in cards.items():
        (d / f"{vid}.json").write_text(
            json.dumps({"id": vid, "ukrainian_translation": ukr, "sanskrit": sa},
                       ensure_ascii=False), encoding="utf-8")
    return tmp


class DuplicateTranslationTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_distinct_translations_pass(self):
        tree(self.tmp, {
            "1.1": ("Перший переклад.", "prathamaḥ"),
            "1.2": ("Другий переклад.", "dvitīyaḥ"),
        })
        self.assertEqual(checker.audit(self.tmp), [])

    def test_identical_translation_with_different_sanskrit_fails(self):
        tree(self.tmp, {
            "1.1": ("Той самий текст.", "prathamaḥ"),
            "1.2": ("Той самий текст.", "dvitīyaḥ"),
        })
        errors = checker.audit(self.tmp)
        self.assertTrue(any("однаковий переклад при різному санскриті" in e
                            for e in errors), errors)

    def test_same_translation_without_sanskrit_is_suspicious(self):
        """Дві порожні лексеми не доводять санскритського рефрену."""
        tree(self.tmp, {
            "1.1": ("Повторений український переклад.", ""),
            "1.2": ("Повторений український переклад.", ""),
        })
        self.assertFalse(checker.shares_formula("", ""))
        errors = checker.audit(self.tmp)
        self.assertTrue(any("однаковий переклад" in e for e in errors), errors)

    def test_one_missing_sanskrit_does_not_hide_duplicate(self):
        """Навіть один порожній свідок не є підставою пропускати перевірку."""
        tree(self.tmp, {
            "1.1": ("Повторений український переклад.", ""),
            "1.2": ("Повторений український переклад.", "prathamah"),
        })
        self.assertFalse(checker.shares_formula("", "prathamah"))
        self.assertTrue(checker.audit(self.tmp))

    def test_empty_sanskrit_with_different_translations_allowed(self):
        """Не відхиляємо різні українські тексти лише за порожній санскрит."""
        tree(self.tmp, {
            "1.1": ("Перший український переклад.", ""),
            "1.2": ("Другий український переклад.", ""),
        })
        self.assertEqual(checker.audit(self.tmp), [])

    def test_refrain_with_same_sanskrit_passes(self):
        """18.12 і 19.2: перший піввірш збігається — це не дефект."""
        refrain = ("Де дгарма, де бажання, де користь, де вміння розрізняти?",
                   "kva dharmaḥ kva ca vā kāmaḥ kva cārthaḥ kva vivekatā | "
                   "idaṃ kṛtam idaṃ neti dvandvair muktasya yoginaḥ")
        other = ("Де дгарма, де бажання, де користь, де вміння розрізняти?",
                 "kva dharmaḥ kva ca vā kāmaḥ kva cārthaḥ kva vivekatā | "
                 "kva dvaitaṃ kva ca vādvaitaṃ svamahimni sthitasya me")
        tree(self.tmp, {"18.12": refrain, "19.2": other})
        self.assertEqual(checker.audit(self.tmp), [])

    def test_second_refrain_2_22_and_11_6_passes(self):
        """nāhaṃ deho na me deho відкриває і 2.22, і 11.6 — теж рефрен."""
        tree(self.tmp, {
            "2.22": ("Я не тіло, і тіло не моє. Я не живчик — я свідомість. Ось у чому була моя уза: спрага до життя.",
                     "nāham deho na me deho jīvo nāham ahaṃ hi cit ayam eva hi me bandha āsīt"),
            "11.6": ("Я не тіло, і тіло не моє; я — усвідомлення» — хто має таке переконання, той не пам'ятає.",
                     "nāhaṃ deho na me deho bodho aham iti niścayī kaivalyam iva saṃprāpto"),
        })
        self.assertEqual(checker.audit(self.tmp), [])

    def test_shared_opening_with_different_sanskrit_fails(self):
        tree(self.tmp, {
            "1.1": ("Де дгарма, де бажання, де користь, де вміння розрізняти? Одне.",
                    "prathamaḥ"),
            "1.2": ("Де дгарма, де бажання, де користь, де вміння розрізняти? Друге.",
                    "dvitīyaḥ"),
        })
        errors = checker.audit(self.tmp)
        self.assertTrue(any("спільний початок перекладу" in e for e in errors), errors)

    def test_punctuation_and_case_do_not_hide_copy(self):
        tree(self.tmp, {
            "1.1": ("Той самий текст.", "prathamaḥ"),
            "1.2": ("той самий   ТЕКСТ!", "dvitīyaḥ"),
        })
        errors = checker.audit(self.tmp)
        self.assertTrue(any("однаковий переклад" in e for e in errors), errors)

    def test_short_translations_skip_head_check(self):
        """Короткі тексти не мають 8 слів — перевіряється лише точний збіг."""
        tree(self.tmp, {
            "1.1": ("Коротко.", "prathamaḥ"),
            "1.2": ("Коротко й інакше.", "dvitīyaḥ"),
        })
        self.assertEqual(checker.audit(self.tmp), [])


if __name__ == "__main__":
    unittest.main()
