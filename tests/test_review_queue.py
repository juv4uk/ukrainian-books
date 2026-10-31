"""Синтетичні незалежні тести звіту, без зовнішньої мережі."""
import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/report_review_queue.py"
spec = importlib.util.spec_from_file_location("report_review_queue", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def entry(draft=False, reviews=None, checks=None):
    return {
        "pr": {"number": 12, "draft": draft, "title": "Чернетка",
               "html_url": "https://github.com/juv4uk/ukrainian-books/pull/12",
               "user": {"login": "автор"}, "head": {"sha": "abc"}},
        "reviews": reviews if reviews is not None else [],
        "checks": checks if checks is not None else [{"name": "якість", "status": "completed", "conclusion": "success"}],
    }


def review(login, state="APPROVED", sha="abc"):
    return {"user": {"login": login}, "state": state, "commit_id": sha}


class ReviewQueueTests(unittest.TestCase):
    def test_draft_blocks_even_with_approval(self):
        row = module.inspect(entry(draft=True, reviews=[review("редактор")]))
        self.assertIn("чернетка", row["observed_technical_blockers"])
        self.assertFalse(row["automatically_mergeable"])

    def test_no_review(self):
        row = module.inspect(entry())
        self.assertIn("немає актуального схвалення іншою особою", row["observed_technical_blockers"])

    def test_self_approval_does_not_count(self):
        row = module.inspect(entry(reviews=[review("АВТОР")]))
        self.assertEqual(row["approvals_current_sha"], [])

    def test_old_sha_is_not_current(self):
        row = module.inspect(entry(reviews=[review("редактор", sha="previous")]))
        self.assertEqual(row["approvals_current_sha"], [])
        self.assertEqual(row["approvals_stale_sha"], ["редактор"])

    def test_latest_review_overrides_old_approval(self):
        row = module.inspect(entry(reviews=[review("редактор"), review("редактор", "CHANGES_REQUESTED")]))
        self.assertEqual(row["approvals_current_sha"], [])
        self.assertEqual(row["changes_requested"], ["редактор"])

    def test_comment_does_not_erase_previous_approval(self):
        row = module.inspect(entry(reviews=[
            review("редактор", "APPROVED"),
            review("редактор", "COMMENTED"),
        ]))
        self.assertEqual(row["approvals_current_sha"], ["редактор"])
        self.assertEqual(row["changes_requested"], [])

    def test_comment_does_not_erase_changes_requested(self):
        row = module.inspect(entry(reviews=[
            review("редактор", "CHANGES_REQUESTED"),
            review("редактор", "COMMENTED"),
        ]))
        self.assertEqual(row["changes_requested"], ["редактор"])
        self.assertEqual(row["approvals_current_sha"], [])

    def test_pending_does_not_erase_previous_approval(self):
        row = module.inspect(entry(reviews=[
            review("редактор", "APPROVED"),
            review("редактор", "PENDING"),
        ]))
        self.assertEqual(row["approvals_current_sha"], ["редактор"])

    def test_dismissal_cancels_previous_approval(self):
        row = module.inspect(entry(reviews=[
            review("редактор", "APPROVED"),
            review("редактор", "DISMISSED"),
        ]))
        self.assertEqual(row["approvals_current_sha"], [])
        self.assertIn("немає актуального схвалення іншою особою", row["observed_technical_blockers"])

    def test_new_approval_after_dismissal_counts(self):
        row = module.inspect(entry(reviews=[
            review("редактор", "APPROVED"),
            review("редактор", "DISMISSED"),
            review("редактор", "APPROVED"),
        ]))
        self.assertEqual(row["approvals_current_sha"], ["редактор"])
        self.assertEqual(row["observed_technical_blockers"], [])
        self.assertFalse(row["automatically_mergeable"])

    def test_failed_and_pending_checks(self):
        row = module.inspect(entry(reviews=[review("редактор")], checks=[
            {"name": "test", "status": "completed", "conclusion": "failure"},
            {"name": "lint", "status": "in_progress", "conclusion": None},
        ]))
        self.assertEqual(row["checks_failed"], ["test"])
        self.assertEqual(row["checks_unverified"], ["lint", "test"])

    def test_skipped_not_success(self):
        row = module.inspect(entry(checks=[{"name": "check", "status": "completed", "conclusion": "skipped"}]))
        self.assertEqual(row["checks_unverified"], ["check"])

    def test_missing_ci_is_not_green(self):
        row = module.inspect(entry(checks=[]))
        self.assertEqual(row["checks_observed"], 0)
        self.assertTrue(any("не знайдено CI" in issue for issue in row["observed_technical_blockers"]))

    def test_green_and_independent_review_never_auto_merge(self):
        row = module.inspect(entry(reviews=[review("редактор")]))
        self.assertEqual(row["observed_technical_blockers"], [])
        self.assertFalse(row["automatically_mergeable"])
        self.assertTrue(row["manual_requirements"])

    def test_report_counts_and_sorts(self):
        a, b = entry(), entry(draft=True)
        a["pr"]["number"], b["pr"]["number"] = 42, 10
        data = module.report([a, b])
        self.assertEqual([x["number"] for x in data["pull_requests"]], [10, 42])
        self.assertEqual(data["drafts"], 1)
        self.assertEqual(data["count"], 2)

    def test_repository_name_validation(self):
        for bad in ("juv4uk", "//evil", "juv4uk/repo?x=1"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                module.snapshot(bad)


if __name__ == "__main__":
    unittest.main()
