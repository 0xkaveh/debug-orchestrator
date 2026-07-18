#!/usr/bin/env python3
"""Validate an evidence plan and run its regression and verification commands."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

try:
    from ._security import (
        PathPolicy,
        SafetyError,
        redact_value,
        run_bounded_command,
    )
except ImportError:
    from _security import (  # type: ignore
        PathPolicy,
        SafetyError,
        redact_value,
        run_bounded_command,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", help="Verification plan JSON inside the repository root")
    parser.add_argument("--root", default=".", help="Repository root")
    parser.add_argument("--timeout", type=int, default=120, help="Per-command timeout")
    parser.add_argument(
        "--max-output-bytes", type=int, default=131_072, help="Retained output per command"
    )
    parser.add_argument(
        "--inherit-env",
        action="append",
        default=[],
        metavar="NAME",
        help="Explicit non-secret environment variable to inherit",
    )
    return parser


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _command(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(
        isinstance(item, str) and bool(item) for item in value
    )


def validate_plan(plan: Any, policy: PathPolicy) -> list[str]:
    errors: list[str] = []
    if not isinstance(plan, dict):
        return ["Plan must be a JSON object"]
    if plan.get("schema_version") != 1:
        errors.append("schema_version must equal 1")

    reproduction = plan.get("reproduction")
    if not isinstance(reproduction, dict):
        errors.append("reproduction must be an object")
    else:
        if not _command(reproduction.get("command")):
            errors.append("reproduction.command must be a non-empty argument array")
        if reproduction.get("failed_before") is not True:
            errors.append("reproduction.failed_before must be true")
        if not _nonempty_string(reproduction.get("failure_signature")):
            errors.append("reproduction.failure_signature is required")

    hypotheses = plan.get("hypotheses")
    if not isinstance(hypotheses, list) or not 1 <= len(hypotheses) <= 3:
        errors.append("hypotheses must contain between one and three entries")
    else:
        identifiers: set[str] = set()
        supported = 0
        for index, hypothesis in enumerate(hypotheses):
            if not isinstance(hypothesis, dict):
                errors.append(f"hypotheses[{index}] must be an object")
                continue
            identifier = hypothesis.get("id")
            if not _nonempty_string(identifier) or identifier in identifiers:
                errors.append(f"hypotheses[{index}].id must be unique and non-empty")
            else:
                identifiers.add(identifier)
            if hypothesis.get("status") == "supported":
                supported += 1
                evidence = hypothesis.get("evidence")
                if not isinstance(evidence, list) or not any(
                    _nonempty_string(item) for item in evidence
                ):
                    errors.append(f"hypotheses[{index}] needs evidence when supported")
            elif hypothesis.get("status") != "rejected":
                errors.append(
                    f"hypotheses[{index}].status must be supported or rejected"
                )
        if supported != 1:
            errors.append("exactly one hypothesis must have status supported")

    root_cause = plan.get("root_cause")
    if not isinstance(root_cause, dict):
        errors.append("root_cause must be an object")
    else:
        if not _nonempty_string(root_cause.get("statement")):
            errors.append("root_cause.statement is required")
        evidence = root_cause.get("evidence")
        if not isinstance(evidence, list) or len(
            [item for item in evidence if _nonempty_string(item)]
        ) < 2:
            errors.append("root_cause.evidence requires at least two observations")

    fix = plan.get("fix")
    if not isinstance(fix, dict):
        errors.append("fix must be an object")
    else:
        if not _nonempty_string(fix.get("summary")):
            errors.append("fix.summary is required")
        files = fix.get("files")
        if not isinstance(files, list) or not files:
            errors.append("fix.files requires at least one repository-relative path")
        else:
            for file_value in files:
                if not _nonempty_string(file_value):
                    errors.append("fix.files entries must be non-empty strings")
                    continue
                try:
                    policy.resolve(file_value, must_exist=False)
                except SafetyError as exc:
                    errors.append(str(exc))

    regression = plan.get("regression")
    if not isinstance(regression, dict):
        errors.append("regression must be an object")
    else:
        if not _command(regression.get("command")):
            errors.append("regression.command must be a non-empty argument array")
        if regression.get("failed_before") is not True:
            errors.append("regression.failed_before must be true")

    checks = plan.get("checks")
    if not isinstance(checks, list) or not checks:
        errors.append("checks requires at least one verification command")
    else:
        for index, check in enumerate(checks):
            if not isinstance(check, dict):
                errors.append(f"checks[{index}] must be an object")
                continue
            if not _nonempty_string(check.get("name")):
                errors.append(f"checks[{index}].name is required")
            if not _command(check.get("command")):
                errors.append(f"checks[{index}].command must be an argument array")

    instrumentation = plan.get("instrumentation")
    if not isinstance(instrumentation, dict):
        errors.append("instrumentation must be an object")
    elif instrumentation.get("removed") is not True:
        errors.append("instrumentation.removed must be true before verification")

    return errors


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        policy = PathPolicy(args.root)
        plan_path = policy.resolve(args.plan, must_exist=True)
        with plan_path.open("rb") as handle:
            raw_plan = handle.read(262_145)
        if len(raw_plan) > 262_144:
            raise SafetyError("Verification plan exceeds 262144 bytes")
        plan = json.loads(raw_plan.decode("utf-8"))
        errors = validate_plan(plan, policy)
        if errors:
            print(
                json.dumps(
                    {"status": "FAIL", "validation_errors": errors},
                    indent=2,
                    ensure_ascii=False,
                )
            )
            return 2

        jobs = [
            ("original reproduction", plan["reproduction"]["command"]),
            ("regression", plan["regression"]["command"]),
            *[(check["name"], check["command"]) for check in plan["checks"]],
        ]
        results: list[dict[str, Any]] = []
        for name, command in jobs:
            result = run_bounded_command(
                command,
                policy=policy,
                timeout_seconds=args.timeout,
                max_output_bytes=args.max_output_bytes,
                inherit_env=args.inherit_env,
            )
            results.append({"name": name, **result.as_redacted_dict()})

        passed = all(result["returncode"] == 0 for result in results)
        report = {
            "status": "PASS" if passed else "FAIL",
            "root_cause": plan["root_cause"],
            "fix": plan["fix"],
            "results": results,
            "instrumentation_removed": True,
            "residual_risks": plan.get("residual_risks", []),
        }
        print(json.dumps(redact_value(report), indent=2, ensure_ascii=False))
        return 0 if passed else 1
    except (json.JSONDecodeError, OSError, SafetyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
