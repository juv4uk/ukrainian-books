#!/usr/bin/env python3
"""Тести контролю українських паралелей.

Головне, що тут перевіряється: **вигадана цитата не проходить**. Кожен тест
будує синтетичний реєстр у тимчасовій теці й показує, що саме перевірка
ловить — а що ні.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.check_ukrainian_parallels import (  # noqa: E402
    ALLOWED_HOSTS,
    audit,
    validate,
    verse_ids,
)

KNOWN = {"1.1", "1.2", "1.3"}


def record(**overrides) -> dict:
    base = {
        "id": "1-1",
        "verse": "1.1",
        "kind": "наша паралель",
        "figure": "Григорій Сковорода",
        "work": "«Наркіс. Розмова про те: Пізнай себе»",
        "text": "Наша паралель: це наша інтерпретація, а не твердження про вплив.",
        "quote": None,
        "quote_url": None,
        "quote_section": None,
        "quote_edition": None,
        "quote_checked_on": None,
    }
    base.update(overrides)
    return base


class RegistryTests(unittest.TestCase):
    def test_real_register_is_clean(self) -> None:
        """Реєстр чистий, і на кожен вірш припадає щонайбільше одна паралель.

        Раніше тут стояли числа 20/20 — рівно стільки, скільки було в главі 1.
        Коли паралелі дійшли до решти глав, фіксоване число замінено на
        інваріант: записів стільки ж, скільки покритих віршів, тобто дублів
        немає (це вже перевіряє і сам `audit`).
        """
        result = audit()
        self.assertEqual(result["status"], "ok", result["errors"])
        self.assertEqual(result["parallels"], result["verses_covered"])
        self.assertGreaterEqual(result["verses_covered"], 20)

    def test_real_register_has_no_unverified_quotes(self) -> None:
        """У книзі немає жодної цитати — і це має бути видно з реєстру.

        Це головне правило: цитата без перевіреного URL не проходить. Тому
        `quotes` мусить бути нулем у будь-якому стані книги, а непевні
        паралелі — позначені, а не подані як впевнені.
        """
        result = audit()
        self.assertEqual(result["quotes"], 0)
        self.assertGreater(result["by_kind"].get("ПОТРЕБУЄ ПЕРЕВІРКИ", 0), 0)

    def test_registry_index_has_298_verses(self) -> None:
        self.assertEqual(len(verse_ids()), 298)


class ShapeTests(unittest.TestCase):
    def test_valid_record_passes(self) -> None:
        self.assertEqual(validate(record(), KNOWN), [])

    def test_unknown_verse_rejected(self) -> None:
        errors = validate(record(verse="99.9"), KNOWN)
        self.assertTrue(any("відсутній у реєстрі" in e for e in errors), errors)

    def test_unknown_field_rejected(self) -> None:
        errors = validate(record(extra="x"), KNOWN)
        self.assertTrue(any("невідомі поля" in e for e in errors), errors)

    def test_unknown_kind_rejected(self) -> None:
        errors = validate(record(kind="здогад"), KNOWN)
        self.assertTrue(any("невідомий вид" in e for e in errors), errors)

    def test_missing_field_rejected(self) -> None:
        broken = record()
        del broken["work"]
        errors = validate(broken, KNOWN)
        self.assertTrue(any("відсутнє поле 'work'" in e for e in errors), errors)


class NoInventedQuotesTests(unittest.TestCase):
    """Серце перевірки: цитата без адреси не проходить."""

    def test_quoted_words_in_our_parallel_rejected(self) -> None:
        errors = validate(
            record(text="Наша паралель: як казав поет, «борітеся — поборете»."),
            KNOWN,
        )
        self.assertTrue(any("цитує чужі слова в лапках" in e for e in errors), errors)

    def test_title_in_quotes_is_not_a_quotation(self) -> None:
        errors = validate(
            record(text="Наша паралель: у «Наркіс» ідеться про самопізнання."),
            KNOWN,
        )
        self.assertEqual(errors, [])

    def test_our_own_translation_in_quotes_is_allowed(self) -> None:
        errors = validate(
            record(text="Наша паралель: вірш каже «я не діяч»."),
            KNOWN,
            ours=["… каже «я не діяч» …"],
        )
        self.assertEqual(errors, [])

    def test_quote_kind_without_url_rejected(self) -> None:
        errors = validate(record(kind="цитата", quote="Слово"), KNOWN)
        self.assertTrue(any("цитата без quote_url" in e for e in errors), errors)
        self.assertTrue(any("цитата без quote_section" in e for e in errors), errors)
        self.assertTrue(any("цитата без quote_edition" in e for e in errors), errors)
        self.assertTrue(any("без дати перевірки" in e for e in errors), errors)

    def test_quote_kind_with_foreign_host_rejected(self) -> None:
        errors = validate(record(
            kind="цитата",
            text="Наша паралель: «Слово».",
            quote="Слово",
            quote_url="https://example.com/quote",
            quote_section="розділ 1",
            quote_edition="К., 1994",
            quote_checked_on="2026-11-01",
        ), KNOWN)
        self.assertTrue(any("білого списку" in e for e in errors), errors)

    def test_quote_must_appear_verbatim_in_text(self) -> None:
        errors = validate(record(
            kind="цитата",
            text="Наша паралель: інші слова.",
            quote="Слово",
            quote_url=f"https://{sorted(ALLOWED_HOSTS)[0]}/x",
            quote_section="розділ 1",
            quote_edition="К., 1994",
            quote_checked_on="2026-11-01",
        ), KNOWN)
        self.assertTrue(any("дослівно" in e for e in errors), errors)

    def test_complete_quote_passes(self) -> None:
        host = "www.izbornyk.org.ua"
        errors = validate(record(
            kind="цитата",
            text="Наша паралель: «Серце є центром» — і далі.",
            quote="Серце є центром",
            quote_url=f"https://{host}/text",
            quote_section="розділ 2",
            quote_edition="К., 1994. — С. 341",
            quote_checked_on="2026-11-01",
        ), KNOWN)
        self.assertEqual(errors, [])


class UnverifiedTests(unittest.TestCase):
    def test_unverified_must_be_labelled(self) -> None:
        errors = validate(record(kind="ПОТРЕБУЄ ПЕРЕВІРКИ"), KNOWN)
        self.assertTrue(any("вимагає цієї позначки" in e for e in errors), errors)

    def test_unverified_cannot_quote(self) -> None:
        errors = validate(record(
            kind="ПОТРЕБУЄ ПЕРЕВІРКИ",
            text="ПОТРЕБУЄ ПЕРЕВІРКИ: «щось»",
        ), KNOWN)
        self.assertTrue(any("не може містити цитат" in e for e in errors), errors)

    def test_unverified_with_marker_passes(self) -> None:
        errors = validate(record(
            kind="ПОТРЕБУЄ ПЕРЕВІРКИ",
            text="ПОТРЕБУЄ ПЕРЕВІРКИ: джерело не встановлене.",
        ), KNOWN)
        self.assertEqual(errors, [])


class OurParallelTests(unittest.TestCase):
    def test_must_say_it_is_ours(self) -> None:
        errors = validate(record(text="Сковорода думав так само."), KNOWN)
        self.assertTrue(any("мусить прямо казати" in e for e in errors), errors)

    def test_cannot_carry_quote_fields(self) -> None:
        errors = validate(record(quote="щось"), KNOWN)
        self.assertTrue(any("не може мати полів quote_*" in e for e in errors), errors)


class DirectoryAuditTests(unittest.TestCase):
    def _write(self, temp: str, records: list[dict]) -> Path:
        path = Path(temp) / "paraleli.json"
        path.write_text(json.dumps(
            {"schema_version": 1, "parallels": records}, ensure_ascii=False),
            encoding="utf-8")
        return path

    def test_duplicate_id_and_verse_are_caught(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = self._write(temp, [record(), record(text="Наша паралель: ще одна.")])
            result = audit(path)
            self.assertEqual(result["status"], "failed")
            self.assertTrue(any("повторений id" in e for e in result["errors"]))
            self.assertTrue(any("має 2 паралелей" in e for e in result["errors"]))

    def test_missing_register_fails_loudly(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            result = audit(Path(temp) / "nope.json")
            self.assertEqual(result["status"], "failed")
            self.assertTrue(result["errors"])

    def test_bad_schema_version(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "paraleli.json"
            path.write_text(json.dumps({"schema_version": 2, "parallels": []}),
                            encoding="utf-8")
            self.assertEqual(audit(path)["status"], "failed")


if __name__ == "__main__":
    unittest.main()
