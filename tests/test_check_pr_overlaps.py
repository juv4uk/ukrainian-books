"""Офлайнові позитивні та негативні тести контролю PR-перетинів."""
import contextlib
import email.message
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

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

    def test_duplicate_across_pages_is_not_an_error(self):
        """Зсув сторінок (понад 100 відкритих PR) не має валити перевірку."""
        visited = []

        def fetch(path):
            visited.append(path)
            if "/files?" in path:
                return [{"filename": "a"}]
            if "page=2" in path:
                return [{"number": 100}, {"number": 101}]
            return [{"number": n} for n in range(1, 101)]

        rows = checker.read_live("owner/repo", 101, fetch)
        numbers = [r["number"] for r in rows]
        self.assertEqual(len(numbers), len(set(numbers)))
        self.assertEqual(numbers, list(range(1, 102)))
        self.assertEqual(sum("/pulls/100/files" in path for path in visited), 1)

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


SECRET = "ghp_FAKEtoken0123456789ABCDEF"


def http_error(code, body="", headers=None, url="https://api.github.com/repos/owner/repo/pulls"):
    """HTTPError із заголовками й тілом, як у справжній відповіді GitHub."""
    message = email.message.Message()
    for name, value in (headers or {}).items():
        message[name] = value
    return urllib.error.HTTPError(
        url, code, "error", message, io.BytesIO(body.encode("utf-8"))
    )


class FakeReply:
    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def read(self):
        return self._payload


def sequence_opener(*outcomes):
    """Опенер, що віддає наслідки по черзі: виняток або корисне навантаження."""
    queue = list(outcomes)

    def opener(req, timeout=15):
        outcome = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(outcome, BaseException):
            raise outcome
        return FakeReply(json.dumps(outcome).encode("utf-8"))

    return opener


def cli(opener, *extra):
    """Запустити CLI з підміненим опенером і зібрати вивід."""
    slept = []
    out, err = io.StringIO(), io.StringIO()
    with mock.patch.dict(os.environ, {"GITHUB_TOKEN": SECRET}), \
            contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = checker.main(
            ["--repo", "owner/repo", "--pr", "5", "--strict", *extra],
            opener=opener,
            sleep=slept.append,
        )
    return code, out.getvalue(), err.getvalue(), slept


class InfrastructureDiagnosticsTests(unittest.TestCase):
    """Ліміт і мережа не валять збірку; токен і невалідний JSON валять."""

    def test_rate_limit_429_does_not_fail_build(self):
        exc = http_error(429, "API rate limit exceeded",
                         {"X-RateLimit-Remaining": "0",
                          "X-RateLimit-Reset": "1793472222",
                          "Retry-After": "60"})
        code, out, err, _ = cli(sequence_opener(exc), "--max-wait", "0")
        self.assertEqual(code, 0, err)
        self.assertIn("ПРОПУЩЕНО: ліміт запитів GitHub", out)
        self.assertIn("HTTP=429", out)
        self.assertIn("Retry-After=60", out)
        self.assertIn("::warning::", out)
        self.assertIn('"status": "skipped"', out)

    def test_secondary_limit_403_is_skipped_not_token_error(self):
        exc = http_error(403, "You have exceeded a secondary rate limit.",
                         {"Retry-After": "0"})
        code, out, err, _ = cli(sequence_opener(exc), "--max-wait", "0")
        self.assertEqual(code, 0, err)
        self.assertIn("ПРОПУЩЕНО: ліміт запитів GitHub", out)
        self.assertNotIn("КООРД-ПОМИЛКА", err)

    def test_403_with_exhausted_quota_is_skipped(self):
        exc = http_error(403, "Forbidden", {"X-RateLimit-Remaining": "0"})
        code, out, err, _ = cli(sequence_opener(exc), "--max-wait", "0")
        self.assertEqual(code, 0, err)
        self.assertIn("ПРОПУЩЕНО", out)

    def test_403_token_problem_fails_with_named_cause(self):
        exc = http_error(403, "Resource not accessible by integration")
        code, out, err, _ = cli(sequence_opener(exc), "--max-wait", "0")
        self.assertEqual(code, 2)
        self.assertIn("Токен недійсний або без прав", err)
        self.assertIn("HTTP=403", err)
        self.assertIn("URL=https://api.github.com/repos/owner/repo/pulls", err)
        self.assertIn("Resource not accessible by integration", err)

    def test_401_fails_with_named_cause(self):
        exc = http_error(401, "Bad credentials")
        code, _, err, _ = cli(sequence_opener(exc), "--max-wait", "0")
        self.assertEqual(code, 2)
        self.assertIn("Токен недійсний або без прав", err)
        self.assertIn("HTTP=401", err)

    def test_invalid_json_fails(self):
        opener = lambda req, timeout=15: FakeReply(b"<html>not json</html>")
        code, _, err, _ = cli(opener, "--max-wait", "0")
        self.assertEqual(code, 2)
        self.assertIn("Невалідний JSON", err)
        self.assertIn("HTTP=(немає відповіді)", err)

    def test_network_error_is_skipped(self):
        exc = urllib.error.URLError("Name or service not known")
        code, out, err, _ = cli(sequence_opener(exc), "--max-wait", "0")
        self.assertEqual(code, 0, err)
        self.assertIn("ПРОПУЩЕНО: мережа або сервер GitHub недоступні", out)

    def test_5xx_is_skipped(self):
        exc = http_error(502, "Bad gateway")
        code, out, err, _ = cli(sequence_opener(exc), "--max-wait", "0")
        self.assertEqual(code, 0, err)
        self.assertIn("ПРОПУЩЕНО", out)
        self.assertIn("HTTP=502", out)

    def test_token_is_never_printed(self):
        for exc in (http_error(401, "Bad credentials"),
                    http_error(403, "Resource not accessible by integration"),
                    http_error(429, "API rate limit exceeded", {"Retry-After": "60"})):
            with self.subTest(status=exc.code):
                _, out, err, _ = cli(sequence_opener(exc), "--max-wait", "0")
                self.assertNotIn(SECRET, out + err)
                self.assertNotIn(SECRET[:12], out + err)

    def test_rate_limit_waits_then_succeeds(self):
        exc = http_error(429, "API rate limit exceeded", {"Retry-After": "0"})
        opener = sequence_opener(
            exc,
            [{"number": 5}],          # /pulls?state=open
            [{"filename": "a.json"}], # файли PR #5
        )
        code, out, err, slept = cli(opener, "--max-wait", "10")
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["status"], "ok")
        self.assertEqual(slept, [0.0])

    def test_overlap_still_fails_closed(self):
        opener = sequence_opener(
            [{"number": 4}, {"number": 5}],  # /pulls?state=open
            [{"filename": "a.json"}],        # файли PR #4
            [{"filename": "a.json"}],        # файли PR #5
        )
        code, out, err, _ = cli(opener, "--max-wait", "10")
        self.assertEqual(code, 1, err)
        self.assertEqual(json.loads(out)["status"], "conflict")


if __name__ == "__main__":
    unittest.main()
