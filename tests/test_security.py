from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPOSITORY_ROOT / "skill" / "debug-orchestrator" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from _security import (  # noqa: E402
    PathPolicy,
    SafetyError,
    ensure_not_sensitive,
    redact_text,
    run_bounded_command,
    safe_environment,
    validate_command,
    _validate_windows_batch_arguments,
)


class RedactionTests(unittest.TestCase):
    def test_redacts_recognizable_secrets(self) -> None:
        fake_github_token = "ghp_" + ("a" * 36)
        text = (
            "Authorization: Bearer abcdefghijklmnopqrstuvwxyz\n"
            "password=correct-horse-battery-staple\n"
            "TOKEN=plain-token-value-123456\n"
            f"token {fake_github_token}\n"
            "url=https://alice:secret@example.test/path"
        )

        redacted = redact_text(text)

        self.assertNotIn("abcdefghijklmnopqrstuvwxyz", redacted)
        self.assertNotIn("correct-horse", redacted)
        self.assertNotIn("plain-token-value", redacted)
        self.assertNotIn("alice:secret", redacted)
        self.assertGreaterEqual(redacted.count("[REDACTED"), 4)

    def test_preserves_normal_diagnostic_text(self) -> None:
        text = "AssertionError: expected 3 but received 4 at tests/test_math.py:18"
        self.assertEqual(redact_text(text), text)


class PathPolicyTests(unittest.TestCase):
    def test_rejects_parent_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repo"
            root.mkdir()
            policy = PathPolicy(root)
            with self.assertRaises(SafetyError):
                policy.resolve("../outside.txt", must_exist=False)

    @unittest.skipIf(os.name == "nt", "Unprivileged Windows symlinks are not portable")
    def test_rejects_symlink_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "repo"
            root.mkdir()
            outside = base / "outside.log"
            outside.write_text("secret", encoding="utf-8")
            (root / "linked.log").symlink_to(outside)
            policy = PathPolicy(root)
            with self.assertRaises(SafetyError):
                policy.resolve("linked.log")

    def test_rejects_credential_filename(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / ".env.production"
            path.write_text("API_KEY=secret", encoding="utf-8")
            with self.assertRaises(SafetyError):
                ensure_not_sensitive(path)


class CommandPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = PathPolicy(REPOSITORY_ROOT)

    def test_blocks_shell_interpreters(self) -> None:
        with self.assertRaises(SafetyError):
            validate_command(["powershell", "-Command", "Write-Output hi"], self.policy)

    def test_blocks_destructive_git_subcommand(self) -> None:
        with self.assertRaises(SafetyError):
            validate_command(["git", "reset", "--hard"], self.policy)

    def test_blocks_inline_python(self) -> None:
        with self.assertRaises(SafetyError):
            validate_command(["python", "-c", "print('unsafe')"], self.policy)

    def test_blocks_windows_batch_shell_metacharacters(self) -> None:
        for character in '&|<>()^%!"\r\n':
            with self.subTest(character=repr(character)):
                with self.assertRaises(SafetyError):
                    _validate_windows_batch_arguments([f"test{character}injected"])

    def test_allows_ordinary_windows_batch_arguments(self) -> None:
        _validate_windows_batch_arguments(
            ["test", "--", "tests/unit.test.js", "--reporter=dot"]
        )

    @unittest.skipUnless(os.name == "nt", "Windows batch integration test")
    def test_batch_arguments_cannot_create_injection_marker(self) -> None:
        batch_root = REPOSITORY_ROOT / "tests" / "fixtures" / "windows-batch" / "root"
        batch_bin = REPOSITORY_ROOT / "tests" / "fixtures" / "windows-batch" / "bin"
        marker = batch_root / "injected.txt"
        if marker.exists():
            marker.unlink()
        original_path = os.environ.get("PATH", "")
        os.environ["PATH"] = f"{batch_bin}{os.pathsep}{original_path}"
        try:
            with self.assertRaises(SafetyError):
                run_bounded_command(
                    ["npm", "test", "&", "echo", "INJECTED>injected.txt"],
                    policy=PathPolicy(batch_root),
                    timeout_seconds=20,
                    max_output_bytes=4096,
                )
        finally:
            os.environ["PATH"] = original_path
        self.assertFalse(marker.exists())

    def test_blocks_repository_shadowed_interpreter(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as temporary:
            shadow = Path(temporary) / ("python.exe" if os.name == "nt" else "python")
            shadow.write_text("not an interpreter", encoding="utf-8")
            if os.name != "nt":
                shadow.chmod(0o755)
            original_path = os.environ.get("PATH", "")
            os.environ["PATH"] = f"{temporary}{os.pathsep}{original_path}"
            try:
                with self.assertRaises(SafetyError):
                    validate_command(
                        ["python", "tests/fixtures/passing_check.py"], self.policy
                    )
            finally:
                os.environ["PATH"] = original_path

    def test_refuses_secret_like_environment_name(self) -> None:
        with self.assertRaises(SafetyError):
            safe_environment(["GITHUB_TOKEN"])

    def test_runs_repository_script_and_redacts_output(self) -> None:
        result = run_bounded_command(
            ["python", "tests/fixtures/emit_secret.py"],
            policy=self.policy,
            timeout_seconds=20,
            max_output_bytes=4096,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("[REDACTED", result.output)
        self.assertNotIn("super-secret", result.output)

    def test_bounds_output(self) -> None:
        result = run_bounded_command(
            ["python", "tests/fixtures/emit_output.py"],
            policy=self.policy,
            timeout_seconds=20,
            max_output_bytes=512,
        )
        self.assertEqual(result.returncode, 0)
        self.assertTrue(result.truncated)
        self.assertLess(len(result.output.encode("utf-8")), 700)


if __name__ == "__main__":
    unittest.main()
