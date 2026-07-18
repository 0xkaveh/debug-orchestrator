from __future__ import annotations

import re
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPOSITORY_ROOT / "skill" / "debug-orchestrator"


class SkillStructureTests(unittest.TestCase):
    def test_skill_frontmatter_and_size(self) -> None:
        content = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn("TODO", content)
        self.assertLess(len(content.splitlines()), 500)
        match = re.match(r"\A---\n(.*?)\n---\n", content, flags=re.DOTALL)
        self.assertIsNotNone(match)
        keys = [
            line.split(":", 1)[0].strip()
            for line in match.group(1).splitlines()
            if ":" in line
        ]
        self.assertEqual(keys, ["name", "description"])
        self.assertIn("name: debug-orchestrator", match.group(1))

    def test_openai_metadata_mentions_explicit_skill(self) -> None:
        content = (SKILL_ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertIn('default_prompt: "Use $debug-orchestrator ', content)

    def test_referenced_resources_exist(self) -> None:
        expected = [
            "references/browser-debugging.md",
            "references/runtime-debugging.md",
            "references/ci-debugging.md",
            "references/security-policy.md",
            "references/evidence-protocol.md",
            "scripts/collect_context.py",
            "scripts/inspect_logs.py",
            "scripts/run_tests.py",
            "scripts/verify_fix.py",
            "assets/hypothesis-ledger.json",
            "assets/verification-plan.json",
            "assets/verification-report.md",
        ]
        for relative in expected:
            with self.subTest(relative=relative):
                self.assertTrue((SKILL_ROOT / relative).is_file())


if __name__ == "__main__":
    unittest.main()
