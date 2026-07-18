from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPOSITORY_ROOT / "skill" / "debug-orchestrator" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from _security import PathPolicy  # noqa: E402
from verify_fix import validate_plan  # noqa: E402


class VerificationPlanTests(unittest.TestCase):
    def valid_plan(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "reproduction": {
                "command": ["python", "tests/fixtures/passing_check.py"],
                "failed_before": True,
                "failure_signature": "expected 1, observed 0",
            },
            "hypotheses": [
                {"id": "H1", "status": "supported", "evidence": ["branch trace"]}
            ],
            "root_cause": {
                "statement": "A false branch skipped the required update.",
                "evidence": [
                    "The trace entered the false branch with the fixture input.",
                    "Forcing the expected branch produced the expected fixture state.",
                ],
            },
            "fix": {
                "summary": "Correct the branch condition.",
                "files": ["tests/fixtures/passing_check.py"],
            },
            "regression": {
                "command": ["python", "tests/fixtures/passing_check.py"],
                "failed_before": True,
            },
            "checks": [
                {
                    "name": "fixture check",
                    "command": ["python", "tests/fixtures/passing_check.py"],
                }
            ],
            "instrumentation": {"added": False, "removed": True},
            "residual_risks": [],
        }

    def test_accepts_complete_evidence_plan(self) -> None:
        errors = validate_plan(self.valid_plan(), PathPolicy(REPOSITORY_ROOT))
        self.assertEqual(errors, [])

    def test_rejects_more_than_three_hypotheses(self) -> None:
        plan = self.valid_plan()
        plan["hypotheses"] = [
            {"id": f"H{index}", "status": "rejected", "evidence": []}
            for index in range(4)
        ]
        errors = validate_plan(plan, PathPolicy(REPOSITORY_ROOT))
        self.assertTrue(any("one and three" in error for error in errors))

    def test_rejects_missing_regression_before_result(self) -> None:
        plan = self.valid_plan()
        plan["regression"]["failed_before"] = False
        errors = validate_plan(plan, PathPolicy(REPOSITORY_ROOT))
        self.assertIn("regression.failed_before must be true", errors)

    def test_repository_fixture_is_valid_json(self) -> None:
        fixture = REPOSITORY_ROOT / "tests" / "fixtures" / "verification-plan.json"
        plan = json.loads(fixture.read_text(encoding="utf-8"))
        errors = validate_plan(plan, PathPolicy(REPOSITORY_ROOT))
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
