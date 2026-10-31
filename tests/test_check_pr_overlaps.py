"""Офлайнові позитивні та негативні тести контролю PR-перетинів.

Набір об'єднує три родини тестів:

* офлайнові перевірки самого гейта (перетин, перейменування, snapshot);
* пакетний GraphQL-шлях і його fail-close (часткові дані, ``errors``,
  порожній перелік, розбіжність лічильників, зсув пагінації);
* діагностику збоїв API: ліміт, токен, мережа, невалідний JSON — і те, що
  токен не потрапляє у вивід ні повністю, ні частково.
"""
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

    def test_invalid_repo_is_error(self):
        with self.assertRaises(checker.AuditError):
            checker.read_live_graphql("../repo", 5, lambda *_: {}, lambda _: [])

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


def graphql_page(rows, more=False, cursor=None, total=None):
    """Синтетична відповідь GraphQL: по одному вузлу на PR, без пагінації файлів."""
    nodes = []
    for number, paths in rows:
        nodes.append({
            "number": number,
            "changedFiles": len(paths),
            "files": {
                "totalCount": len(paths),
                "nodes": [{"path": path, "changeType": "MODIFIED"} for path in paths],
                "pageInfo": {"hasNextPage": False},
            },
        })
    return {"data": {"repository": {"pullRequests": {
        "totalCount": len(rows) if total is None else total,
        "nodes": nodes,
        "pageInfo": {"hasNextPage": more, "endCursor": cursor},
    }}}}


def node_of(page, index=0):
    return page["data"]["repository"]["pullRequests"]["nodes"][index]


def files_of(page, index=0):
    return node_of(page, index)["files"]


class GraphQLBatchTests(unittest.TestCase):
    """Пакетний GraphQL-шлях: менше запитів, ті самі гарантії."""

    def test_batch_is_one_request_and_detects_conflict(self):
        pages_seen = []

        def graphql_fetch(query, variables):
            pages_seen.append(variables)
            self.assertIn("pullRequests", query)
            return graphql_page([
                (4, ["cards/1.1.json"]),
                (19, ["cards/1.2.json"]),
                (21, ["cards/1.2.json"]),
                (25, ["cards/1.3.json"]),
            ])

        def no_rest(_):
            self.fail("Для звичайних файлів REST не потрібен")

        records = checker.read_live_graphql("owner/repo", 21, graphql_fetch, no_rest)
        self.assertEqual(len(pages_seen), 1)
        self.assertEqual([x["number"] for x in records], [4, 19, 21])
        self.assertEqual(checker.overlaps(21, records),
                         [{"pr": 19, "paths": ["cards/1.2.json"]}])

    def test_earlier_prs_do_not_need_rest(self):
        rest_calls = []
        records = checker.read_live_graphql(
            "owner/repo", 5,
            lambda *_: graphql_page([(2, ["a"]), (5, ["a"]), (8, ["a"])]),
            lambda path: rest_calls.append(path) or self.fail("REST зайвий"),
        )
        self.assertEqual([r["number"] for r in records], [2, 5])
        self.assertEqual(rest_calls, [])

    def test_rename_requires_rest_old_and_new_paths(self):
        rest_calls = []

        def graphql_fetch(_query, _vars):
            page = graphql_page([(10, ["cards/new.json"]), (11, ["cards/old.json"])])
            node_of(page)["files"]["nodes"][0]["changeType"] = "RENAMED"
            return page

        def rest_fetch(path):
            rest_calls.append(path)
            return [{"filename": "cards/new.json", "previous_filename": "cards/old.json",
                     "status": "renamed"}]

        records = checker.read_live_graphql("owner/repo", 11, graphql_fetch, rest_fetch)
        self.assertEqual(len(rest_calls), 1)
        self.assertIn("/pulls/10/files", rest_calls[0])
        self.assertEqual(checker.overlaps(11, records),
                         [{"pr": 10, "paths": ["cards/old.json"]}])

    def test_over_100_files_uses_complete_rest_fallback(self):
        rest_calls = []
        first = [f"cards/{i}.json" for i in range(100)]
        all_files = first + ["cards/last.json"]

        def graphql_fetch(_query, _vars):
            page = graphql_page([(10, first), (11, ["cards/last.json"])])
            files = files_of(page)
            files["totalCount"] = 101
            files["pageInfo"]["hasNextPage"] = True
            node_of(page)["changedFiles"] = 101
            return page

        def rest_fetch(path):
            rest_calls.append(path)
            if path.endswith("&page=1"):
                return [{"filename": x} for x in all_files[:100]]
            if path.endswith("&page=2"):
                return [{"filename": all_files[-1]}]
            self.fail(f"Неочікувана сторінка: {path}")

        rows = checker.read_live_graphql("owner/repo", 11, graphql_fetch, rest_fetch)
        self.assertEqual(len(rest_calls), 2)
        self.assertEqual(checker.overlaps(11, rows),
                         [{"pr": 10, "paths": ["cards/last.json"]}])

    def test_cursor_pagination_is_complete(self):
        observed = []

        def graphql_fetch(_query, vars_):
            observed.append(vars_["cursor"])
            if vars_["cursor"] is None:
                return graphql_page([(5, ["a"])], more=True, cursor="cursor-one", total=2)
            return graphql_page([(7, ["a"])], total=2)

        rows = checker.read_live_graphql("owner/repo", 7, graphql_fetch,
                                        lambda _: self.fail("REST зайвий"))
        self.assertEqual(observed, [None, "cursor-one"])
        self.assertEqual(checker.overlaps(7, rows), [{"pr": 5, "paths": ["a"]}])


class GraphQLFailClosedTests(unittest.TestCase):
    """Кожен шлях, де даних немає, мусить бути червоним, а не зеленим."""

    def read(self, payload, pr_number=7):
        return checker.read_live_graphql("owner/repo", pr_number,
                                         lambda *_: payload,
                                         lambda _: self.fail("REST не мав викликатися"))

    def test_graphql_errors_fail_closed(self):
        for payload in (
            {"errors": [{"message": "часткова відповідь"}], "data": {}},
            {"errors": [{"message": "часткова відповідь"}],
             "data": {"repository": {"pullRequests": {
                 "totalCount": 1,
                 "nodes": [{"number": 7, "changedFiles": 1, "files": {
                     "totalCount": 1, "nodes": [{"path": "a", "changeType": "MODIFIED"}],
                     "pageInfo": {"hasNextPage": False}}}],
                 "pageInfo": {"hasNextPage": False, "endCursor": None}}}}},
            {"errors": [{"message": "boom"}]},
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(checker.AuditError) as context:
                    self.read(payload)
                self.assertIn("errors", str(context.exception))

    def test_partial_file_list_fails_closed(self):
        # Оголошено 5 файлів, прийшло 3 — переліку вірити не можна.
        page = graphql_page([(7, ["a", "b", "c"])])
        files_of(page)["totalCount"] = 5
        node_of(page)["changedFiles"] = 5
        with self.assertRaises(checker.AuditError):
            self.read(page)

    def test_changed_files_mismatch_fails_closed(self):
        page = graphql_page([(7, ["a", "b"])])
        node_of(page)["changedFiles"] = 9
        with self.assertRaises(checker.AuditError):
            self.read(page)

    def test_missing_changed_files_fails_closed(self):
        for bad in (None, "2", 2.0, -1):
            page = graphql_page([(7, ["a", "b"])])
            node_of(page)["changedFiles"] = bad
            with self.subTest(changed_files=bad), self.assertRaises(checker.AuditError):
                self.read(page)

    def test_empty_pr_list_with_open_prs_fails_closed(self):
        # GitHub каже, що відкрито 3 PR, але вузлів немає: це втрата даних.
        with self.assertRaises(checker.AuditError):
            self.read(graphql_page([], total=3))

    def test_short_pr_list_with_open_prs_fails_closed(self):
        # Цільовий PR є, але перелік коротший за оголошену кількість.
        with self.assertRaises(checker.AuditError) as context:
            self.read(graphql_page([(7, ["a"])], total=3))
        self.assertIn("неповний", str(context.exception).lower())

    def test_target_pr_missing_from_list_fails_closed(self):
        with self.assertRaises(checker.AuditError):
            self.read(graphql_page([(4, ["a"])]), pr_number=7)

    def test_pagination_skip_fails_closed(self):
        # Сторінки віддали 2 PR, а оголошено 5 — курсор міг перескочити PR.
        def graphql_fetch(_query, variables):
            if variables["cursor"] is None:
                return graphql_page([(4, ["a"])], more=True, cursor="c1", total=5)
            return graphql_page([(7, ["a"])], total=5)

        with self.assertRaises(checker.AuditError):
            checker.read_live_graphql("owner/repo", 7, graphql_fetch, lambda _: [])

    def test_bad_cursor_fails_closed(self):
        for page in (
            {"data": {"repository": {"pullRequests": {
                "totalCount": 1, "nodes": [],
                "pageInfo": {"hasNextPage": True, "endCursor": None}}}}},
            {"data": {"repository": {"pullRequests": {
                "totalCount": 1, "nodes": [],
                "pageInfo": {"hasNextPage": "yes", "endCursor": "c1"}}}}},
            {"data": {"repository": None}},
            {"data": {}},
            {},
            [],
        ):
            with self.subTest(page=page), self.assertRaises(checker.AuditError):
                self.read(page)

    def test_duplicate_or_invalid_pr_number_fails_closed(self):
        for bad in (0, -1, "7", 7.0, None):
            page = graphql_page([(7, ["a"])])
            node_of(page)["number"] = bad
            with self.subTest(number=bad), self.assertRaises(checker.AuditError):
                self.read(page)
        page = graphql_page([(7, ["a"]), (7, ["b"])])
        with self.assertRaises(checker.AuditError):
            self.read(page)

    def test_missing_files_connection_fails_closed(self):
        for files in (None, [], "files", {"totalCount": 1}):
            page = graphql_page([(7, ["a"])])
            node_of(page)["files"] = files
            with self.subTest(files=files), self.assertRaises(checker.AuditError):
                self.read(page)

    def test_invalid_file_and_change_type_fail_closed(self):
        for bad in (None, [], "UNKNOWN", "modified"):
            page = graphql_page([(7, ["cards/7.1.json"])])
            files_of(page)["nodes"][0]["changeType"] = bad
            with self.subTest(change_type=bad), self.assertRaises(checker.AuditError):
                self.read(page)
        for bad_path in (None, "", 42, "bad\npath"):
            page = graphql_page([(7, ["cards/7.1.json"])])
            files_of(page)["nodes"][0]["path"] = bad_path
            with self.subTest(path=bad_path), self.assertRaises(checker.AuditError):
                self.read(page)

    def test_rename_without_previous_path_fails_closed(self):
        page = graphql_page([(7, ["cards/new.json"])])
        files_of(page)["nodes"][0]["changeType"] = "RENAMED"
        with self.assertRaises(checker.AuditError):
            checker.read_live_graphql("owner/repo", 7, lambda *_: page,
                                      lambda _: [{"filename": "cards/new.json",
                                                  "status": "renamed"}])

    def test_rest_fallback_shorter_than_declared_fails_closed(self):
        page = graphql_page([(7, ["a", "b"])])
        node_of(page)["files"]["nodes"][0]["changeType"] = "RENAMED"
        with self.assertRaises(checker.AuditError):
            checker.read_live_graphql("owner/repo", 7, lambda *_: page,
                                      lambda _: [{"filename": "a"}])


SECRET = "ghp_FAKEtoken0123456789ABCDEF"


def http_error(code, body="", headers=None, url="https://api.github.com/graphql"):
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

    def opener(req, timeout=20):
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
    """Невиконаний через API або мережу аудит блокує збірку."""

    def test_rate_limit_429_does_not_fail_build(self):
        exc = http_error(429, "API rate limit exceeded",
                         {"X-RateLimit-Remaining": "0",
                          "X-RateLimit-Reset": "1793472222",
                          "Retry-After": "60"})
        code, out, err, _ = cli(sequence_opener(exc), "--max-wait", "0")
        self.assertEqual(code, 2, err)
        self.assertIn("ПРОПУЩЕНО: ліміт запитів GitHub", out)
        self.assertIn("HTTP=429", out)
        self.assertIn("Retry-After=60", out)
        self.assertIn("X-RateLimit-Remaining=0", out)
        self.assertIn("X-RateLimit-Reset=1793472222", out)
        self.assertIn("::warning::", out)
        self.assertIn('"status": "skipped"', out)
        self.assertIn("тіло=", out)
        self.assertIn("URL=https://api.github.com/graphql", out)

    def test_secondary_limit_403_is_skipped_not_token_error(self):
        exc = http_error(403, "You have exceeded a secondary rate limit.",
                         {"Retry-After": "0"})
        code, out, err, _ = cli(sequence_opener(exc), "--max-wait", "0")
        self.assertEqual(code, 2, err)
        self.assertIn("ПРОПУЩЕНО: ліміт запитів GitHub", out)
        self.assertNotIn("КООРД-ПОМИЛКА", err)

    def test_403_with_exhausted_quota_is_skipped(self):
        exc = http_error(403, "Forbidden", {"X-RateLimit-Remaining": "0"})
        code, out, err, _ = cli(sequence_opener(exc), "--max-wait", "0")
        self.assertEqual(code, 2, err)
        self.assertIn("ПРОПУЩЕНО", out)

    def test_403_token_problem_fails_with_named_cause(self):
        exc = http_error(403, "Resource not accessible by integration")
        code, out, err, _ = cli(sequence_opener(exc), "--max-wait", "0")
        self.assertEqual(code, 2)
        self.assertIn("Токен недійсний або без прав", err)
        self.assertIn("HTTP=403", err)
        self.assertIn("URL=https://api.github.com/graphql", err)
        self.assertIn("Resource not accessible by integration", err)

    def test_401_fails_with_named_cause(self):
        exc = http_error(401, "Bad credentials")
        code, _, err, _ = cli(sequence_opener(exc), "--max-wait", "0")
        self.assertEqual(code, 2)
        self.assertIn("Токен недійсний або без прав", err)
        self.assertIn("HTTP=401", err)

    def test_invalid_json_fails(self):
        opener = lambda req, timeout=20: FakeReply(b"<html>not json</html>")
        code, _, err, _ = cli(opener, "--max-wait", "0")
        self.assertEqual(code, 2)
        self.assertIn("Невалідний JSON", err)
        self.assertIn("HTTP=(немає відповіді)", err)

    def test_network_error_is_skipped(self):
        exc = urllib.error.URLError("Name or service not known")
        code, out, err, _ = cli(sequence_opener(exc), "--max-wait", "0")
        self.assertEqual(code, 2, err)
        self.assertIn("ПРОПУЩЕНО: мережа або сервер GitHub недоступні", out)

    def test_5xx_is_skipped(self):
        exc = http_error(502, "Bad gateway")
        code, out, err, _ = cli(sequence_opener(exc), "--max-wait", "0")
        self.assertEqual(code, 2, err)
        self.assertIn("ПРОПУЩЕНО", out)
        self.assertIn("HTTP=502", out)

    def test_body_diagnostic_is_capped_at_200_characters(self):
        exc = http_error(401, "x" * 250 + "ХВІСТ-ЗА-МЕЖЕЮ")
        _, out, err, _ = cli(sequence_opener(exc), "--max-wait", "0")
        self.assertIn("тіло=", err)
        self.assertNotIn("ХВІСТ-ЗА-МЕЖЕЮ", err)

    def test_token_is_never_printed(self):
        for exc in (http_error(401, "Bad credentials"),
                    http_error(403, "Resource not accessible by integration"),
                    http_error(429, "API rate limit exceeded", {"Retry-After": "60"})):
            with self.subTest(status=exc.code):
                _, out, err, _ = cli(sequence_opener(exc), "--max-wait", "0")
                self.assertNotIn(SECRET, out + err)
                self.assertNotIn(SECRET[:12], out + err)

    def test_token_echoed_by_server_is_redacted(self):
        # Навіть якщо сервер відлунить отриманий Bearer назад у тілі,
        # у вивід він не потрапляє.
        exc = http_error(403, f"Bad credentials for Bearer {SECRET}")
        code, _, err, _ = cli(sequence_opener(exc), "--max-wait", "0")
        self.assertEqual(code, 2)
        self.assertNotIn(SECRET, err)
        self.assertNotIn(SECRET[:12], err)
        self.assertIn("(приховано)", err)

    def test_graphql_errors_message_is_reported_without_token(self):
        page = {"errors": [{"message": f"Field failed for {SECRET}"}]}
        code, _, err, _ = cli(sequence_opener(page), "--max-wait", "0")
        self.assertEqual(code, 2)
        self.assertIn("GraphQL повернув errors", err)
        self.assertNotIn(SECRET, err)

    def test_rate_limit_without_strict_fails_closed(self):
        """Відсутність --strict не робить пропущений аудит успішним."""
        exc = http_error(429, "API rate limit exceeded", {"Retry-After": "60"})
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, {"GITHUB_TOKEN": SECRET}), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = checker.main(
                ["--repo", "owner/repo", "--pr", "5", "--max-wait", "0"],
                opener=sequence_opener(exc),
                sleep=lambda _: None,
            )
        self.assertEqual(code, 2, err.getvalue())
        self.assertEqual(json.loads(out.getvalue())["status"], "skipped")

    def test_rate_limit_waits_then_succeeds(self):
        exc = http_error(429, "API rate limit exceeded", {"Retry-After": "0"})
        opener = sequence_opener(
            exc,
            graphql_page([(4, ["a.json"]), (5, ["b.json"])]),
        )
        code, out, err, slept = cli(opener, "--max-wait", "10")
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["status"], "ok")
        self.assertEqual(slept, [0.0])

    def test_overlap_still_fails_closed(self):
        opener = sequence_opener(graphql_page([(4, ["a.json"]), (5, ["a.json"])]))
        code, out, err, _ = cli(opener, "--max-wait", "10")
        self.assertEqual(code, 1, err)
        self.assertEqual(json.loads(out)["status"], "conflict")

    def test_missing_token_fails_closed(self):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, {"GITHUB_TOKEN": ""}), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = checker.main(["--repo", "owner/repo", "--pr", "5"],
                                opener=sequence_opener(graphql_page([])))
        self.assertEqual(code, 2)
        self.assertIn("GITHUB_TOKEN відсутній", err.getvalue())


if __name__ == "__main__":
    unittest.main()
