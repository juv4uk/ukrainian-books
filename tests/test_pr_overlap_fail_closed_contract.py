"""Незалежний регресійний контракт: невиконаний PR-аудит не може бути зеленим.

Тестує поведінку командного інтерфейсу без мережі й без зміни
спільного скрипту координації (його редагує інший CLAIM).
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/check_pr_overlaps.py"
SPEC = importlib.util.spec_from_file_location("pr_overlap_contract_under_test", SCRIPT)
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


def cli_with_reader(*, records=None, failure=None):
    """Підставити тільки зчитувач; жодного реального HTTP-запиту."""
    output, errors = io.StringIO(), io.StringIO()
    reader = "read_live_graphql" if hasattr(checker, "read_live_graphql") else "read_live"
    fake_argv = [str(SCRIPT), "--repo", "owner/repo", "--pr", "5", "--strict"]
    with (
        mock.patch.dict(os.environ, {"GITHUB_TOKEN": "тестовий-токен"}, clear=False),
        mock.patch.object(sys, "argv", fake_argv),
        mock.patch.object(checker, reader, return_value=records, side_effect=failure),
        contextlib.redirect_stdout(output),
        contextlib.redirect_stderr(errors),
    ):
        result = checker.main()
    return result, output.getvalue(), errors.getvalue()


class FailClosedContractTests(unittest.TestCase):
    def test_unavailable_audit_must_not_report_success(self):
        """Мережевий збій — не доказ відсутності колізії."""
        code, _, _ = cli_with_reader(failure=checker.AuditError("API недоступний"))
        self.assertNotEqual(code, 0)

    def test_explicitly_skipped_audit_must_not_report_success(self):
        """P0: майбутній AuditSkipped ніколи не повинен маскуватися exit 0."""
        # У поточному main AuditSkipped немає — fail-closed дає AuditError.
        skipped_type = getattr(checker, "AuditSkipped", checker.AuditError)
        code, out, err = cli_with_reader(
            failure=skipped_type("HTTP 403: ліміт звернень")
        )
        self.assertNotEqual(
            code, 0,
            "НЕБЕЗПЕЧНО: аудит пропущено, але CI бачить успіх. "
            f"stdout={out!r}, stderr={err!r}",
        )

    def test_timeout_or_server_failure_must_not_report_success(self):
        skipped_type = getattr(checker, "AuditSkipped", checker.AuditError)
        for problem in ("HTTP 502", "timeout", "HTTP 429"):
            with self.subTest(problem=problem):
                code, _, _ = cli_with_reader(failure=skipped_type(problem))
                self.assertNotEqual(code, 0)

    def test_confirmed_overlap_is_rejected(self):
        records = [
            {"number": 4, "files": [{"filename": "editorial/cards/1.1.json"}]},
            {"number": 5, "files": [{"filename": "editorial/cards/1.1.json"}]},
        ]
        code, output, _ = cli_with_reader(records=records)
        self.assertEqual(code, 1)
        self.assertIn('"status": "conflict"', output)

    def test_only_completed_nonconflicting_audit_succeeds(self):
        records = [
            {"number": 4, "files": [{"filename": "editorial/cards/1.1.json"}]},
            {"number": 5, "files": [{"filename": "editorial/cards/1.2.json"}]},
        ]
        code, output, _ = cli_with_reader(records=records)
        self.assertEqual(code, 0)
        self.assertIn('"status": "ok"', output)


if __name__ == "__main__":
    unittest.main()
