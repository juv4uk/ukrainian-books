"""Офлайнова перевірка друкованих номерів у синтетичному TEI, без чужого корпусу."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from fetch_witnesses import sarit_verse, gretil_verse, compare

# Відтворюємо лише *структуру* SARIT 1.1, 1.12–1.13, 18.95–18.96.
# Наповнення навмисно вигадане українською: це не санскритський свідок.
SARIT = """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
  <div n="1">
    <lg><l xml:id="verse_1.1">перший рядок один|</l>
    <l>другий рядок один||1|1||</l></lg>
    <lg xml:id="verse_1.2"><l>початок два|</l>
    <l>кінець два||1|2||</l></lg>
    <lg xml:id="verse_1.13"><l>початок дванадцять|</l></lg>
    <lg xml:id="verse_1.12"><l>кінець дванадцять||1|12||</l>
    <l>початок тринадцять|</l>
    <l>кінець тринадцять||1|13||</l></lg>
  </div>
  <div n="18">
    <lg xml:id="verse_18.96"><l>початок дев'яносто п'ять|</l>
    <l>кінець дев'яносто п'ять||18|95|||</l>
    <l>початок дев'яносто шість|</l>
    <l>кінець дев'яносто шість||18|96||</l></lg>
  </div>
</body></text></TEI>"""

GRETIL = """<TEI><text><body><lg xml:id="Avg_1.2">
<l>початок два|</l><l>кінець два||1|2||</l>
</lg></body></text></TEI>"""


class TestSaritPrintedNumbers(unittest.TestCase):
    def test_first_verse_id_on_child_line(self):
        self.assertEqual(
            sarit_verse(SARIT, "1.1"),
            "перший рядок один другий рядок один",
        )

    def test_normal_verse_unchanged(self):
        self.assertEqual(sarit_verse(SARIT, "1.2"), "початок два кінець два")

    def test_interchanged_1_12_and_1_13(self):
        self.assertEqual(
            sarit_verse(SARIT, "1.12"),
            "початок дванадцять кінець дванадцять",
        )
        self.assertEqual(
            sarit_verse(SARIT, "1.13"),
            "початок тринадцять кінець тринадцять",
        )

    def test_split_shared_group_18_95_and_18_96(self):
        self.assertEqual(
            sarit_verse(SARIT, "18.95"),
            "початок дев'яносто п'ять кінець дев'яносто п'ять",
        )
        self.assertEqual(
            sarit_verse(SARIT, "18.96"),
            "початок дев'яносто шість кінець дев'яносто шість",
        )

    def test_unknown_or_invalid_verse_not_invented(self):
        self.assertIsNone(sarit_verse(SARIT, "18.94"))
        self.assertIsNone(sarit_verse(SARIT, "1.0"))
        self.assertIsNone(sarit_verse(SARIT, "18.95'"))

    def test_malformed_xml_or_no_body_returns_none(self):
        self.assertIsNone(sarit_verse("<TEI>", "1.1"))
        self.assertIsNone(sarit_verse("<TEI/>", "1.1"))

    def test_duplicate_printed_number_is_not_silently_selected(self):
        duplicate = SARIT.replace(
            "</body>",
            '<lg><l>інший початок|</l><l>інший кінець||1|2||</l></lg></body>',
        )
        self.assertIsNone(sarit_verse(duplicate, "1.2"))

    def test_incomplete_verse_returns_none(self):
        incomplete = SARIT.replace("<l>початок два|</l>\n    ", "")
        self.assertIsNone(sarit_verse(incomplete, "1.2"))

    def test_gretil_extraction_and_comparison_unchanged(self):
        self.assertEqual(gretil_verse(GRETIL, "1.2"), "початок два кінець два")
        self.assertTrue(compare("рядок один", "рядокодин")["identical_ignoring_spaces"])


if __name__ == "__main__":
    unittest.main()
