#!/usr/bin/env python3
"""Офлайнові тести аудитора GitHub без мережі й адміністративних прав."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/audit_main_protection.py"
SPEC = importlib.util.spec_from_file_location("audit_main_protection", SCRIPT)
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class AuditMainProtectionTests(unittest.TestCase):
    def test_unprotected_remains_explicit(self):
        report = AUDIT.summarize({"protected": False}, [])
        self.assertEqual(report["стан"], "незахищено")
        self.assertIs(report["protected"], False)
        self.assertEqual(report["активні_rulesets"], [])
        self.assertFalse(report["рев'ю_підтверджено"])

    def test_protected_does_not_imply_reviews(self):
        report = AUDIT.summarize(
            {"protected": True},
            [{"name": "Основний", "enforcement": "active"},
             {"name": "Чернетка", "enforcement": "disabled"}],
        )
        self.assertEqual(report["стан"], "захищено")
        self.assertEqual(report["активні_rulesets"], ["Основний"])
        self.assertFalse(report["рев'ю_підтверджено"])
        self.assertFalse(report["обов'язкові_CI_підтверджено"])
        self.assertFalse(report["заборону_force_push_підтверджено"])

    def test_nonboolean_and_missing_values_are_unknown(self):
        for value in (None, "false", 1):
            with self.subTest(value=value):
                report = AUDIT.summarize({"protected": value}, None)
                self.assertEqual(report["стан"], "невідомо")
                self.assertIsNone(report["protected"])
                self.assertIsNone(report["активні_rulesets"])

    def test_api_error_is_not_reported_as_unprotected(self):
        def failing_fetch(url, token):
            raise HTTPError(url, 403, "forbidden", None, None)
        report = AUDIT.inspect(
            "juv4uk/ukrainian-books", fetch=failing_fetch
        )
        self.assertEqual(report["стан"], "невідомо")
        self.assertEqual(report["похибка_читання_гілки"], "HTTPError")
        self.assertEqual(report["похибка_читання_rulesets"], "HTTPError")

    def test_ruleset_error_does_not_erase_branch_protection(self):
        def partial_fetch(url, token):
            if url.endswith("/rulesets"):
                raise OSError("недоступно")
            return {"protected": True}
        report = AUDIT.inspect(
            "juv4uk/ukrainian-books", fetch=partial_fetch
        )
        self.assertIs(report["protected"], True)
        self.assertIsNone(report["активні_rulesets"])
        self.assertEqual(report["похибка_читання_rulesets"], "OSError")

    def test_strict_mode_fails_closed(self):
        for protected, expected in ((False, 2), (None, 2), (True, 0)):
            with self.subTest(protected=protected):
                with tempfile.TemporaryDirectory() as folder:
                    with patch.object(
                        AUDIT, "inspect",
                        return_value={"protected": protected, "стан": "test"}
                    ):
                        destination = str(Path(folder) / "audit.json")
                        rc = AUDIT.main(
                            ["--repo", "juv4uk/ukrainian-books",
                             "--report", destination, "--require-protected"]
                        )
                        self.assertEqual(rc, expected)
                        result = json.loads(
                            Path(destination).read_text(encoding="utf-8")
                        )
                        self.assertEqual(result["репозиторій"],
                                         "juv4uk/ukrainian-books")

    def test_report_mode_does_not_claim_enforcement(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(
                AUDIT, "inspect",
                return_value={"protected": False, "стан": "незахищено"}
            ):
                rc = AUDIT.main(["--report", str(Path(folder) / "a.json")])
                self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
