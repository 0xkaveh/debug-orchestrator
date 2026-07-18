#!/usr/bin/env python3
"""Run an allowlisted verification command with bounded, redacted output."""

from __future__ import annotations

import argparse
import json
import sys

try:
    from ._security import PathPolicy, SafetyError, run_bounded_command
except ImportError:
    from _security import PathPolicy, SafetyError, run_bounded_command  # type: ignore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root")
    parser.add_argument("--cwd", default=".", help="Working directory inside the root")
    parser.add_argument("--timeout", type=int, default=120, help="Timeout in seconds")
    parser.add_argument(
        "--max-output-bytes", type=int, default=262_144, help="Retained tail output"
    )
    parser.add_argument(
        "--inherit-env",
        action="append",
        default=[],
        metavar="NAME",
        help="Explicit non-secret environment variable to inherit",
    )
    parser.add_argument("--json", action="store_true", help="Emit a JSON result")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    try:
        policy = PathPolicy(args.root)
        cwd = policy.resolve(args.cwd, must_exist=True)
        result = run_bounded_command(
            command,
            policy=policy,
            cwd=cwd,
            timeout_seconds=args.timeout,
            max_output_bytes=args.max_output_bytes,
            inherit_env=args.inherit_env,
        )
    except (OSError, SafetyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result.as_redacted_dict(), indent=2, ensure_ascii=False))
    else:
        if result.output:
            print(result.output)
        print(
            f"[exit={result.returncode} duration={result.duration_seconds:.3f}s "
            f"timed_out={str(result.timed_out).lower()} "
            f"truncated={str(result.truncated).lower()}]"
        )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
