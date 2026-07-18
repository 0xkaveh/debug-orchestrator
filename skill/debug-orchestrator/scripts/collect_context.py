#!/usr/bin/env python3
"""Collect a small, redacted debugging context packet."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from ._security import (
        MAX_OUTPUT_BYTES,
        PathPolicy,
        SafetyError,
        ensure_not_sensitive,
        read_head,
        redact_value,
        run_bounded_command,
    )
except ImportError:
    from _security import (  # type: ignore
        MAX_OUTPUT_BYTES,
        PathPolicy,
        SafetyError,
        ensure_not_sensitive,
        read_head,
        redact_value,
        run_bounded_command,
    )


MANIFESTS = (
    "Cargo.toml",
    "Gemfile",
    "go.mod",
    "package-lock.json",
    "package.json",
    "pnpm-lock.yaml",
    "poetry.lock",
    "pom.xml",
    "pyproject.toml",
    "requirements.txt",
    "uv.lock",
    "yarn.lock",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root")
    parser.add_argument(
        "--include",
        action="append",
        default=[],
        metavar="FILE",
        help="Explicit repository-relative text file to include; repeat as needed",
    )
    parser.add_argument(
        "--max-file-bytes", type=int, default=16_384, help="Per-file read limit"
    )
    parser.add_argument(
        "--max-total-bytes", type=int, default=65_536, help="Total included content limit"
    )
    return parser


def collect(args: argparse.Namespace) -> dict[str, object]:
    policy = PathPolicy(args.root)
    if not 1 <= args.max_file_bytes <= MAX_OUTPUT_BYTES:
        raise SafetyError("--max-file-bytes is outside the supported range")
    if not 1 <= args.max_total_bytes <= MAX_OUTPUT_BYTES:
        raise SafetyError("--max-total-bytes is outside the supported range")

    status = run_bounded_command(
        ["git", "status", "--short", "--branch"],
        policy=policy,
        timeout_seconds=15,
        max_output_bytes=32_768,
    )

    manifests: list[dict[str, object]] = []
    for name in MANIFESTS:
        candidate = policy.root / name
        if candidate.is_file():
            manifests.append({"path": name, "size_bytes": candidate.stat().st_size})

    selected: list[dict[str, object]] = []
    remaining = args.max_total_bytes
    for requested in args.include:
        path = policy.resolve(requested, must_exist=True)
        ensure_not_sensitive(path)
        if not path.is_file():
            raise SafetyError(f"Included path is not a file: {requested}")
        if remaining <= 0:
            break
        limit = min(args.max_file_bytes, remaining)
        content, truncated = read_head(path, limit)
        consumed = len(content.encode("utf-8"))
        remaining -= consumed
        selected.append(
            {
                "path": policy.relative(path),
                "size_bytes": path.stat().st_size,
                "truncated": truncated,
                "content": content,
            }
        )

    packet: dict[str, object] = {
        "schema_version": 1,
        "root": ".",
        "git": {
            "returncode": status.returncode,
            "status": status.output,
            "truncated": status.truncated,
        },
        "manifests": manifests,
        "selected_files": selected,
        "warnings": [
            "No environment variables, ignored files, or credential stores were collected.",
            "Review this redacted packet before sharing it; pattern redaction is not a guarantee.",
        ],
    }
    return redact_value(packet)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        packet = collect(args)
    except (OSError, SafetyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(packet, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
