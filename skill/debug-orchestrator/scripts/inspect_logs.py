#!/usr/bin/env python3
"""Read bounded tails of explicitly selected log files with secret redaction."""

from __future__ import annotations

import argparse
import sys

try:
    from ._security import (
        MAX_OUTPUT_BYTES,
        PathPolicy,
        SafetyError,
        ensure_not_sensitive,
        read_tail,
    )
except ImportError:
    from _security import (  # type: ignore
        MAX_OUTPUT_BYTES,
        PathPolicy,
        SafetyError,
        ensure_not_sensitive,
        read_tail,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", metavar="LOG")
    parser.add_argument("--root", default=".", help="Repository root")
    parser.add_argument(
        "--max-file-bytes", type=int, default=32_768, help="Tail bytes per file"
    )
    parser.add_argument(
        "--max-total-bytes", type=int, default=131_072, help="Total output bytes"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        policy = PathPolicy(args.root)
        if not 1 <= args.max_file_bytes <= MAX_OUTPUT_BYTES:
            raise SafetyError("--max-file-bytes is outside the supported range")
        if not 1 <= args.max_total_bytes <= MAX_OUTPUT_BYTES:
            raise SafetyError("--max-total-bytes is outside the supported range")

        remaining = args.max_total_bytes
        for requested in args.paths:
            if remaining <= 0:
                print("[total output limit reached]")
                break
            path = policy.resolve(requested, must_exist=True)
            ensure_not_sensitive(path)
            if not path.is_file():
                raise SafetyError(f"Log path is not a file: {requested}")
            content, _ = read_tail(path, min(args.max_file_bytes, remaining))
            rendered = f"--- {policy.relative(path)} ---\n{content}"
            encoded = rendered.encode("utf-8")
            if len(encoded) > remaining:
                rendered = encoded[-remaining:].decode("utf-8", errors="replace")
            print(rendered)
            remaining -= min(len(encoded), remaining)
    except (OSError, SafetyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
