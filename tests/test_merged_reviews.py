"""УКР-07: незалежні синтетичні тести аудиту злитих PR."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.audit_merged_reviews import REPO, audit, inspect

SHA = "a" * 40
OTHER_SHA = "b" * 40
BEFORE = "2026-10-31T15:00:00Z"
MERGED = "2026-10-31T16:00:00Z"
AFTER = "2026-10-31T17:00:00Z"
SCRIPT = Path(__file__).resolve().parents[1] / "scripts/audit_merged_reviews.py"


def pr(number=1):
    return {"number": number, "head": {"sha": SHA},
            "user": {"login": "Автор"}, "merged_at": MERGED}


def review(state="APPROVED", login="Рецензент", sha=SHA,
           submitted=BEFORE, number=1):
    return {"id": number, "state": state, "user": {"login": login},
            "commit_id": sha, "submitted_at": submitted}


class MergedReviewTests(unittest.TestCase):
    def test_valid_github_approval_on_exact_head(self):
        result = inspect(pr(), [review()])
        self.assertEqual(result["status"], "github_approval_observed")
        self.assertEqual(result["github_approvals_on_head"], ["Рецензент"])

    def test_no_reviews_is_not_evidence(self):
        self.assertEqual(inspect(pr(), [])["status"], "no_verifiable_github_approval")

    def test_approval_after_merge_does_not_count(self):
        self.assertEqual(inspect(pr(), [review(submitted=AFTER)])["status"],
                         "no_verifiable_github_approval")

    def test_approval_on_old_sha_does_not_count(self):
        self.assertEqual(inspect(pr(), [review(sha=OTHER_SHA)])["status"],
                         "no_verifiable_github_approval")

    def test_author_self_approval_casefold_does_not_count(self):
        self.assertEqual(inspect(pr(), [review(login="аВТОР")])["status"],
                         "no_verifiable_github_approval")

    def test_changes_requested_after_approval_cancels_proof(self):
        first = review(number=1)
        second = review("CHANGES_REQUESTED", number=2)
        second["submitted_at"] = "2026-10-31T15:30:00Z"
        self.assertEqual(inspect(pr(), [first, second])["status"],
                         "no_verifiable_github_approval")

    def test_dismissed_after_approval_cancels_proof(self):
        dismissed = review("DISMISSED", number=2)
        dismissed["submitted_at"] = "2026-10-31T15:45:00Z"
        self.assertEqual(inspect(pr(), [review(), dismissed])["status"],
                         "no_verifiable_github_approval")

    def test_new_approval_after_changes_requested(self):
        first = review("CHANGES_REQUESTED", number=1)
        approved = review(number=2)
        approved["submitted_at"] = "2026-10-31T15:40:00Z"
        self.assertEqual(inspect(pr(), [first, approved])["status"],
                         "github_approval_observed")

    def test_comment_does_not_cancel_existing_approval(self):
        comment = review("COMMENTED", number=9, submitted="2026-10-31T15:40:00Z")
        self.assertEqual(inspect(pr(), [review(), comment])["status"],
                         "github_approval_observed")

    def test_decision_on_newer_sha_cancels_old_proof(self):
        later = review(sha=OTHER_SHA, number=2)
        later["submitted_at"] = "2026-10-31T15:55:00Z"
        self.assertEqual(inspect(pr(), [review(), later])["status"],
                         "no_verifiable_github_approval")

    def test_unknown_reviews_are_not_treated_as_empty(self):
        self.assertEqual(inspect(pr(), None)["status"], "insufficient_data")

    def test_missing_author_or_invalid_merge_time(self):
        bad = pr()
        bad["user"] = None
        self.assertEqual(inspect(bad, [])["status"], "insufficient_data")
        bad = pr()
        bad["merged_at"] = "не дата"
        self.assertEqual(inspect(bad, [])["status"], "insufficient_data")

    def test_broken_review_metadata_is_uncertain(self):
        broken = review(submitted="не дата")
        self.assertEqual(inspect(pr(), [broken])["status"], "insufficient_data")

    def test_unmerged_items_skipped_and_limit_preserved(self):
        ignored = pr(100)
        ignored["merged_at"] = None
        result = audit([ignored, pr(1), pr(2)], {"1": [], "2": [review()]}, 1)
        self.assertEqual(result["audited_merged_prs"], 1)
        self.assertEqual(result["no_verifiable_github_approval"], 1)

    def test_reviewer_of_different_pr_cannot_count(self):
        result = audit([pr(1), pr(2)], {"1": [], "2": [review()]}, 2)
        self.assertEqual(result["github_approval_observed"], 1)
        self.assertEqual(result["no_verifiable_github_approval"], 1)

    def test_missing_review_key_is_insufficient_not_negative(self):
        result = audit([pr(7)], {}, 1)
        self.assertEqual(result["insufficient_data"], 1)
        self.assertEqual(result["no_verifiable_github_approval"], 0)

    def test_repository_argument_is_restricted(self):
        self.assertIsNotNone(REPO.fullmatch("juv4uk/ukrainian-books"))
        self.assertIsNone(REPO.fullmatch("juv4uk/foo/../../users"))

    def test_cli_fixture_reports_without_blocking(self):
        with tempfile.TemporaryDirectory() as root:
            f = Path(root) / "snapshot.json"
            f.write_text(json.dumps({"pulls": [pr()], "reviews": {"1": []}},
                                    ensure_ascii=False), encoding="utf-8")
            done = subprocess.run([sys.executable, str(SCRIPT), "--fixture", str(f)],
                                  capture_output=True, text=True, check=False)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout)["no_verifiable_github_approval"], 1)

    def test_cli_malformed_fixture_fails_closed(self):
        with tempfile.TemporaryDirectory() as root:
            f = Path(root) / "broken.json"
            f.write_text('{"pulls":[]}', encoding="utf-8")
            done = subprocess.run([sys.executable, str(SCRIPT), "--fixture", str(f)],
                                  capture_output=True, text=True, check=False)
        self.assertEqual(done.returncode, 1)
        self.assertIn("ПОМИЛКА", done.stderr)


if __name__ == "__main__":
    unittest.main()
