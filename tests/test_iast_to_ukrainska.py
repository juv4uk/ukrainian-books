"""Свідки для української транслітерації IAST.

Зразки взяті з уже зроблених вручну наукових розділів
(`books/ashtavakra-gita/rozdil-5-naukove.md`, `rozdil-6-naukove.md`).
Три випадки з тих файлів НЕ відтворюються навмисно, і це зафіксовано
окремими тестами: у зразках там друкарські помилки або сандгі між словами.
"""
import importlib.util
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "scripts/iast_to_ukrainska.py"
SPEC = importlib.util.spec_from_file_location("tr", SOURCE)
tr = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tr)


class TransliterationTests(unittest.TestCase):
    def test_matches_handmade_chapter_5_verse_1(self):
        self.assertEqual(
            tr.transliterate("na te saṅgo 'sti kenāpi kiṃ śuddhas tyaktum icchasi"),
            "на те санґо ’сті кенапі кім шуддгас тьяктум іччхасі")

    def test_matches_handmade_chapter_5_verse_2(self):
        self.assertEqual(
            tr.transliterate("udeti bhavato viśvaṃ vāridher iva budbudaḥ"),
            "удеті бгавато вішвам варідгер іва будбудах")

    def test_matches_handmade_chapter_5_verse_3_head(self):
        self.assertEqual(
            tr.transliterate("pratyakṣam apy"),
            "пратьякшам апь")

    def test_nasal_ng_is_n_not_ng(self):
        # saṅga → санґа, а не санґґа: ṅ дає «н», «ґ» дає вже сама g
        self.assertEqual(tr.transliterate("saṅga"), "санґа")

    def test_double_j_is_ddj(self):
        self.assertEqual(tr.transliterate("rajju"), "радджу")

    def test_cch_is_chchh(self):
        self.assertEqual(tr.transliterate("icchasi"), "іччхасі")

    def test_palatal_nya(self):
        # jñā → джня, без зайвого «ь»
        self.assertEqual(tr.transliterate("jñāna"), "джняна")

    def test_y_between_vowels_gives_ya(self):
        self.assertEqual(tr.transliterate("layam"), "лаям")

    def test_visarga_and_anusvara(self):
        self.assertEqual(tr.transliterate("rāmaḥ"), "рамах")
        self.assertEqual(tr.transliterate("saṃskṛtam"), "самскрітам")

    def test_danda_preserved(self):
        self.assertIn("|", tr.transliterate("eva | eva ||"))

    def test_known_deviation_is_documented(self):
        """Зразок пише «мутьюх» для mṛtyuḥ; правильно — «мрітьюх».

        Тест фіксує, що скрипт дає лінгвістично послідовну форму, а не
        копіює друкарську помилку зразка.
        """
        self.assertEqual(tr.transliterate("mṛtyuḥ"), "мрітьюх")


if __name__ == "__main__":
    unittest.main()
