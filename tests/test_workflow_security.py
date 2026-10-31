"""Негативні перевірки безпеки workflow без зовнішніх залежностей."""

import importlib.util
import tempfile
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "scripts/check_workflow_security.py"
SPEC = importlib.util.spec_from_file_location("workflow_security", SRC)
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)

GOOD = """name: Контроль
on:
  push:
    branches: [main]
  pull_request:
permissions:
  contents: read
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: echo ok
"""


class SecurityTests(unittest.TestCase):
    def test_safe_workflow(self):
        self.assertEqual(checker.inspect("quality.yml", GOOD), [])

    def test_no_permissions(self):
        self.assertTrue(checker.inspect("quality.yml", GOOD.replace("permissions:\n  contents: read\n", "")))

    def test_write_permissions_root(self):
        self.assertTrue(checker.inspect("quality.yml", GOOD.replace("contents: read", "contents: write")))

    def test_write_permissions_job_override(self):
        text = GOOD.replace("    runs-on:", "    permissions:\n      contents: write\n    runs-on:")
        self.assertTrue(checker.inspect("quality.yml", text))

    def test_target_event(self):
        self.assertTrue(checker.inspect("quality.yml", GOOD.replace("  pull_request:", "  pull_request_target:")))

    def test_workflow_run_event(self):
        self.assertTrue(checker.inspect("quality.yml", GOOD.replace("  pull_request:", "  workflow_run:")))

    def test_target_event_with_inline_object_is_rejected(self):
        sample = GOOD.replace(
            "  pull_request:\n",
            "  pull_request:\n  pull_request_target: {}\n",
        )
        errors = checker.inspect("quality.yml", sample)
        self.assertTrue(
            any("небезпечна подія pull_request_target" in error for error in errors),
            errors,
        )

    def test_workflow_run_with_inline_object_is_rejected(self):
        sample = GOOD.replace(
            "  pull_request:\n",
            "  pull_request:\n  workflow_run: { workflows: [Якість] }\n",
        )
        errors = checker.inspect("quality.yml", sample)
        self.assertTrue(any("небезпечна подія workflow_run" in error for error in errors), errors)

    def test_workflow_run_with_inline_array_is_rejected(self):
        sample = GOOD.replace(
            "  pull_request:\n",
            "  pull_request:\n  workflow_run: [виконано]\n",
        )
        errors = checker.inspect("provenance-audit.yml", sample)
        self.assertTrue(any("небезпечна подія workflow_run" in error for error in errors), errors)

    def test_inline_safe_pull_request_event_remains_allowed(self):
        sample = GOOD.replace("  pull_request:\n", "  pull_request: {}\n")
        self.assertEqual(checker.inspect("quality.yml", sample), [])

    def test_inline_permissions(self):
        self.assertTrue(checker.inspect("quality.yml", GOOD.replace("permissions:\n  contents: read", "permissions: write-all")))

    def test_missing_pull_request(self):
        self.assertTrue(checker.inspect("quality.yml", GOOD.replace("  pull_request:\n", "")))

    def test_missing_push_to_main(self):
        self.assertTrue(checker.inspect("quality.yml", GOOD.replace("branches: [main]", "branches: [dev]")))

    def test_missing_required_workflow(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root / ".github/workflows"
            target.mkdir(parents=True)
            (target / "quality.yml").write_text(GOOD, encoding="utf-8")
            outcome = checker.audit(root)
            self.assertEqual(outcome["status"], "failed")
            self.assertTrue(any("provenance-audit.yml" in e for e in outcome["errors"]))

    def test_valid_three_workflows(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root / ".github/workflows"
            target.mkdir(parents=True)
            for name in checker.REQUIRED:
                (target / name).write_text(GOOD, encoding="utf-8")
            self.assertEqual(checker.audit(root)["status"], "ok")


if __name__ == "__main__":
    unittest.main()
