from __future__ import annotations

import argparse
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPOSITORY_ROOT / "skill" / "debug-orchestrator" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from _security import SafetyError  # noqa: E402
from collect_context import collect  # noqa: E402


class CollectContextTests(unittest.TestCase):
    def arguments(self, root: Path, include: list[str]) -> argparse.Namespace:
        return argparse.Namespace(
            root=str(root),
            include=include,
            max_file_bytes=4096,
            max_total_bytes=8192,
        )

    def test_collects_only_explicit_file_content(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "package.json").write_text('{"name":"fixture"}', encoding="utf-8")
            (root / "debug.txt").write_text(
                "Authorization: Bearer abcdefghijklmnopqrstuvwxyz", encoding="utf-8"
            )

            packet = collect(self.arguments(root, ["debug.txt"]))

            self.assertEqual(packet["manifests"][0]["path"], "package.json")
            selected = packet["selected_files"][0]
            self.assertEqual(selected["path"], "debug.txt")
            self.assertIn("[REDACTED]", selected["content"])

    def test_refuses_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / ".env").write_text("PASSWORD=secret", encoding="utf-8")
            with self.assertRaises(SafetyError):
                collect(self.arguments(root, [".env"]))


if __name__ == "__main__":
    unittest.main()
