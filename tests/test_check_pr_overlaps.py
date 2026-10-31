"""Офлайнові позитивні та негативні тести контролю PR-перетинів."""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "scripts/check_pr_overlaps.py"
SPEC = importlib.util.spec_from_file_location("pr_overlaps", SOURCE)
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


class OverlapTests(unittest.TestCase):
    def test_distinct_files(self):
        self.assertEqual(checker.overlaps(20, [
            {"number": 10, "files": ["editorial/cards/1.1.json"]},
            {"number": 20, "files": ["editorial/cards/1.2.json"]},
        ]), [])

    def test_later_pr_fails_with_exact_path(self):
        rows = [
            {"number": 53, "files": [{"filename": "editorial/cards/2.5.json"}]},
            {"number": 58, "files": [{"filename": "editorial/cards/2.5.json"}]},
        ]
        self.assertEqual(checker.overlaps(58, rows), [
            {"pr": 53, "paths": ["editorial/cards/2.5.json"]}
        ])
        self.assertEqual(checker.run(58, rows, True), 1)
        self.assertEqual(checker.run(58, rows, False), 0)

    def test_earlier_pr_not_blocked(self):
        rows = [{"number": 53, "files": ["a.json"]}, {"number": 58, "files": ["a.json"]}]
        self.assertEqual(checker.overlaps(53, rows), [])

    def test_multiple_files_are_sorted(self):
        rows = [
            {"number": 80, "files": ["b", "a", "z"]},
            {"number": 83, "files": ["a", "b", "c"]},
        ]
        self.assertEqual(checker.overlaps(83, rows), [{"pr": 80, "paths": ["a", "b"]}])

    def test_rename_old_path_collides(self):
        rows = [
            {"number": 100, "files": [{"filename": "cards/new.json",
                                      "previous_filename": "cards/old.json",
                                      "status": "renamed"}]},
            {"number": 101, "files": [{"filename": "cards/old.json",
                                      "status": "modified"}]},
        ]
        self.assertEqual(checker.overlaps(101, rows), [
            {"pr": 100, "paths": ["cards/old.json"]}
        ])

    def test_rename_new_path_collides(self):
        rows = [
            {"number": 100, "files": [{"filename": "cards/new.json", "status": "added"}]},
            {"number": 101, "files": [{"filename": "cards/new.json",
                                      "previous_filename": "cards/old.json",
                                      "status": "renamed"}]},
        ]
        self.assertEqual(checker.overlaps(101, rows), [
            {"pr": 100, "paths": ["cards/new.json"]}
        ])

    def test_rename_without_valid_previous_path_fails_closed(self):
        for bad in [None, "", 123, "bad\npath"]:
            rows = [{"number": 101, "files": [
                {"filename": "cards/new.json", "status": "renamed",
                 "previous_filename": bad}
            ]}]
            with self.subTest(previous_filename=bad):
                with self.assertRaises(checker.AuditError):
                    checker.overlaps(101, rows)

    def test_closed_pr_not_in_open_snapshot(self):
        self.assertEqual(checker.overlaps(58, [{"number": 58, "files": ["a"]}]), [])

    def test_missing_or_repeated_pr_is_error(self):
        with self.assertRaises(checker.AuditError):
            checker.overlaps(58, [{"number": 53, "files": ["a"]}])
        with self.assertRaises(checker.AuditError):
            checker.overlaps(58, [{"number": 58, "files": ["a"]}] * 2)

    def test_wrong_paths_fail_closed(self):
        with self.assertRaises(checker.AuditError):
            checker.overlaps(58, [{"number": 58, "files": [None]}])

    def test_api_failure_or_truncation_fail_closed(self):
        with self.assertRaises(checker.AuditError):
            checker.pages("/pulls", lambda _url: {"oops": True})
        with self.assertRaises(checker.AuditError):
            checker.pages("/pulls", lambda _url: [{}] * 100, max_pages=1)

    def test_fetches_only_earlier_open_prs(self):
        visited = []
        def fetch(path):
            visited.append(path)
            if "/files?" in path:
                return [{"filename": "a"}]
            return [{"number": 2}, {"number": 5}, {"number": 8}]
        rows = checker.read_live("owner/repo", 5, fetch)
        self.assertEqual([r["number"] for r in rows], [2, 5])
        self.assertFalse(any("/8/files" in path for path in visited))

    def test_invalid_repo_is_error(self):
        with self.assertRaises(checker.AuditError):
            checker.read_live("../repo", 5, lambda _: [])

    def test_offline_cli_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "prs.json"
            path.write_text(json.dumps({"pulls": [
                {"number": 53, "files": ["file.json"]},
                {"number": 58, "files": ["file.json"]},
            ]}), encoding="utf-8")
            process = subprocess.run([sys.executable, str(SOURCE), "--pr", "58", "--strict", "--snapshot", str(path)], capture_output=True, text=True)
            self.assertEqual(process.returncode, 1)
            self.assertEqual(json.loads(process.stdout)["status"], "conflict")


class _Reply:
    """Мінімальна відповідь: json.load() читає через .read()."""

    def __init__(self, payload):
        self._raw = json.dumps(payload).encode("utf-8")

    def read(self, *args):
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class GetJsonRetryTests(unittest.TestCase):
    """Транзитний збій API не повинен валити гейт з першої спроби.

    Справжній випадок 31.10.2026: `HTTPError` від GitHub API зробив
    червоним КОЖЕН PR, і рій не міг нічого злити.
    """

    def _run(self, side_effect, **kwargs):
        from unittest import mock
        sleeps = []
        with mock.patch.object(checker.request, "urlopen", side_effect=side_effect) as opened:
            try:
                value = checker.get_json("/x", "", sleep=sleeps.append, **kwargs)
                return value, opened.call_count, sleeps
            except checker.AuditError as exc:
                return exc, opened.call_count, sleeps

    def test_transient_error_is_retried_then_succeeds(self):
        boom = checker.error.URLError("мережа")
        value, calls, sleeps = self._run([boom, boom, _Reply({"ok": 1})])
        self.assertEqual(value, {"ok": 1})
        self.assertEqual(calls, 3)
        self.assertEqual(sleeps, [1.0, 3.0])

    def test_server_error_is_retried_then_fails_closed(self):
        def raise_500(*args, **kwargs):
            raise checker.error.HTTPError("u", 500, "server", {}, None)
        value, calls, _ = self._run(raise_500)
        self.assertIsInstance(value, checker.AuditError)
        self.assertEqual(calls, 3)

    def test_permanent_4xx_is_not_retried(self):
        def raise_404(*args, **kwargs):
            raise checker.error.HTTPError("u", 404, "not found", {}, None)
        value, calls, sleeps = self._run(raise_404)
        self.assertIsInstance(value, checker.AuditError)
        self.assertEqual(calls, 1, "404 не зникне від паузи — повторювати не можна")
        self.assertEqual(sleeps, [])

    def test_rate_limit_honours_retry_after(self):
        slow = checker.error.HTTPError("u", 429, "slow down", {"Retry-After": "0"}, None)
        value, calls, sleeps = self._run([slow, _Reply({"ok": 1})])
        self.assertEqual(value, {"ok": 1})
        self.assertEqual(calls, 2)
        self.assertEqual(sleeps, [0.0])

    def test_broken_json_is_retried(self):
        class Truncated:
            def read(self, *args):
                return b'{"a":'

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        value, calls, _ = self._run([Truncated(), _Reply({"ok": 2})])
        self.assertEqual(value, {"ok": 2})
        self.assertEqual(calls, 2)


if __name__ == "__main__":
    unittest.main()
