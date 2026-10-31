"""Офлайнові позитивні та негативні тести контролю PR-перетинів."""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
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

    @staticmethod
    def graphql_page(rows, more=False, cursor=None):
        return {"data": {"repository": {"pullRequests": {
            "nodes": [
                {"number": n, "files": {
                    "totalCount": len(paths),
                    "nodes": [{"path": path, "changeType": "MODIFIED"}
                              for path in paths],
                    "pageInfo": {"hasNextPage": False},
                }} for n, paths in rows
            ],
            "pageInfo": {"hasNextPage": more, "endCursor": cursor},
        }}}}

    def test_graphql_batch_reduces_requests_and_detects_conflict(self):
        pages_seen = []
        def graphql_fetch(query, variables):
            pages_seen.append(variables)
            self.assertIn("pullRequests", query)
            return self.graphql_page([
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

    def test_graphql_rename_requires_rest_old_and_new_paths(self):
        rest_calls = []
        def graphql_fetch(_query, _vars):
            result = self.graphql_page([
                (10, ["cards/new.json"]), (11, ["cards/old.json"])
            ])
            result["data"]["repository"]["pullRequests"]["nodes"][0]["files"]["nodes"][0]["changeType"] = "RENAMED"
            return result
        def rest_fetch(path):
            rest_calls.append(path)
            return [{"filename": "cards/new.json", "previous_filename": "cards/old.json",
                     "status": "renamed"}]
        records = checker.read_live_graphql("owner/repo", 11, graphql_fetch, rest_fetch)
        self.assertEqual(len(rest_calls), 1)
        self.assertIn("/pulls/10/files", rest_calls[0])
        self.assertEqual(checker.overlaps(11, records),
                         [{"pr": 10, "paths": ["cards/old.json"]}])

    def test_graphql_over_100_files_uses_complete_rest_fallback(self):
        rest_calls = []
        first = [f"cards/{i}.json" for i in range(100)]
        all_files = first + ["cards/last.json"]
        def graphql_fetch(_query, _vars):
            page = self.graphql_page([(10, first), (11, ["cards/last.json"])])
            file_conn = page["data"]["repository"]["pullRequests"]["nodes"][0]["files"]
            file_conn["totalCount"] = 101
            file_conn["pageInfo"]["hasNextPage"] = True
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

    def test_graphql_cursor_pagination_is_complete(self):
        observed = []
        def graphql_fetch(_query, vars_):
            observed.append(vars_["cursor"])
            if vars_["cursor"] is None:
                return self.graphql_page([(5, ["a"])], more=True, cursor="cursor-one")
            return self.graphql_page([(7, ["a"])])
        rows = checker.read_live_graphql("owner/repo", 7, graphql_fetch,
                                        lambda _: self.fail("REST зайвий"))
        self.assertEqual(observed, [None, "cursor-one"])
        self.assertEqual(checker.overlaps(7, rows), [{"pr": 5, "paths": ["a"]}])

    def test_graphql_error_missing_pr_and_bad_cursor_fail_closed(self):
        malformed = [
            {"errors": [{"message": "часткова відповідь"}], "data": {}},
            {"data": {"repository": {"pullRequests": {
                "nodes": [], "pageInfo": {"hasNextPage": True, "endCursor": None}
            }}}},
            self.graphql_page([(4, ["a"])]),
        ]
        for response in malformed:
            with self.subTest(response=response):
                with self.assertRaises(checker.AuditError):
                    checker.read_live_graphql("owner/repo", 7,
                                              lambda *_: response, lambda _: [])

    def test_graphql_invalid_file_and_rename_metadata_fail_closed(self):
        for bad in [None, [], "UNKNOWN"]:
            response = self.graphql_page([(7, ["cards/7.1.json"])])
            node = response["data"]["repository"]["pullRequests"]["nodes"][0]
            node["files"]["nodes"][0]["changeType"] = bad
            with self.subTest(change_type=bad), self.assertRaises(checker.AuditError):
                checker.read_live_graphql("owner/repo", 7,
                                          lambda *_: response, lambda _: [])
        response = self.graphql_page([(7, ["cards/new.json"])])
        response["data"]["repository"]["pullRequests"]["nodes"][0]["files"]["nodes"][0]["changeType"] = "RENAMED"
        with self.assertRaises(checker.AuditError):
            checker.read_live_graphql("owner/repo", 7, lambda *_: response,
                                      lambda _: [{"filename": "cards/new.json",
                                                  "status": "renamed"}])

    def test_rest_http_status_is_visible_but_token_hidden(self):
        with patch.object(checker.request, "urlopen", side_effect=HTTPError(
            "https://api.github.com/internal", 403, "ліміт", None, None,
        )):
            with self.assertRaises(checker.AuditError) as context:
                checker.get_json("/repos/owner/repo/pulls/4/files", "секретний-токен")
        self.assertIn("HTTP 403", str(context.exception))
        self.assertNotIn("секретний-токен", str(context.exception))
        self.assertNotIn("https://", str(context.exception))

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


if __name__ == "__main__":
    unittest.main()
