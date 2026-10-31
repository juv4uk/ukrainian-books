"""РЕД-06: незалежні синтетичні тести повторених JSON-ключів."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.check_json_unique_keys import DuplicateKeyError, audit, load_unique, unique_object


class UniqueKeyTests(unittest.TestCase):
    def file(self, text: str) -> tuple[tempfile.TemporaryDirectory, Path]:
        temp = tempfile.TemporaryDirectory()
        path = Path(temp.name) / "test.json"
        path.write_text(text, encoding="utf-8")
        return temp, path

    def fixture(self, root: Path) -> Path:
        (root / "docs").mkdir()
        template = root / "docs/VERSE_CARD_TEMPLATE.json"
        template.write_text('{"id":"1.1"}', encoding="utf-8")
        return template

    def test_valid_nested_json(self):
        temp, path = self.file('{"id":"1.1","rights":{"verified":false}}')
        try:
            self.assertEqual(load_unique(path)["id"], "1.1")
        finally:
            temp.cleanup()

    def test_duplicate_top_level_status(self):
        temp, path = self.file('{"status":"чернетка","status":"рецензовано"}')
        try:
            with self.assertRaisesRegex(DuplicateKeyError, "status"):
                load_unique(path)
        finally:
            temp.cleanup()

    def test_duplicate_rights_verified(self):
        temp, path = self.file('{"rights":{"verified":false,"verified":true}}')
        try:
            with self.assertRaisesRegex(DuplicateKeyError, "verified"):
                load_unique(path)
        finally:
            temp.cleanup()

    def test_duplicate_review_reviewer(self):
        temp, path = self.file('{"review":{"reviewer":null,"reviewer":"Редактор"}}')
        try:
            with self.assertRaisesRegex(DuplicateKeyError, "reviewer"):
                load_unique(path)
        finally:
            temp.cleanup()

    def test_duplicate_nested_source_url(self):
        temp, path = self.file('{"sources":{"gretil":{"url":"a","url":"b"}}}')
        try:
            with self.assertRaisesRegex(DuplicateKeyError, "url"):
                load_unique(path)
        finally:
            temp.cleanup()

    def test_duplicate_inside_variant_array(self):
        temp, path = self.file('{"variants":[{"witness":"a","witness":"b"}]}')
        try:
            with self.assertRaisesRegex(DuplicateKeyError, "witness"):
                load_unique(path)
        finally:
            temp.cleanup()

    def test_same_key_in_separate_objects(self):
        self.assertEqual(unique_object([("gretil", {"url": "a"}), ("sarit", {"url": "b"})]),
                         {"gretil": {"url": "a"}, "sarit": {"url": "b"}})

    def test_no_cards_explicit(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            result = audit(root)
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["checked_cards"], 0)
            self.assertTrue(result["checked_template"])

    def test_duplicate_template_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            tpl = self.fixture(root)
            tpl.write_text('{"id":"1.1","id":"1.2"}', encoding="utf-8")
            result = audit(root)
            self.assertEqual(result["status"], "failed")
            self.assertTrue(any("id" in x and "VERSE_CARD_TEMPLATE" in x for x in result["errors"]))

    def test_duplicate_card_fails_with_filename(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            folder = root / "editorial/cards"
            folder.mkdir(parents=True)
            (folder / "1.1.json").write_text('{"status":"чернетка","status":"рецензовано"}', encoding="utf-8")
            result = audit(root)
            self.assertEqual(result["checked_cards"], 1)
            self.assertEqual(result["status"], "failed")
            self.assertTrue(any("1.1.json" in x and "status" in x for x in result["errors"]))

    def test_malformed_json_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            folder = root / "editorial/cards"
            folder.mkdir(parents=True)
            (folder / "1.2.json").write_text('{"id":', encoding="utf-8")
            self.assertEqual(audit(root)["status"], "failed")

    def test_invalid_utf8_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            folder = root / "editorial/cards"
            folder.mkdir(parents=True)
            (folder / "1.3.json").write_bytes(b"\xff")
            self.assertEqual(audit(root)["status"], "failed")

    def test_same_keys_in_separate_cards_valid(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            folder = root / "editorial/cards"
            folder.mkdir(parents=True)
            for verse in ("1.2", "1.3"):
                (folder / (verse + ".json")).write_text(json.dumps({"id": verse, "rights": {"verified": False}}), encoding="utf-8")
            result = audit(root)
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["checked_cards"], 2)

    def test_missing_template_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            result = audit(Path(temp))
            self.assertEqual(result["status"], "failed")
            self.assertTrue(any("шаблон" in x for x in result["errors"]))


if __name__ == "__main__":
    unittest.main()
