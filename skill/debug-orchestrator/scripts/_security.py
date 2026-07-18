"""Shared safety primitives for Debug Orchestrator helper scripts."""

from __future__ import annotations

import os
import re
import shutil
import signal
import subprocess
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence


MAX_TIMEOUT_SECONDS = 900
MAX_OUTPUT_BYTES = 1_048_576

_SENSITIVE_ENV_FRAGMENT = re.compile(
    r"TOKEN|SECRET|PASSWORD|PASSWD|COOKIE|AUTH|CREDENTIAL|PRIVATE|API_?KEY|SESSION",
    re.IGNORECASE,
)

_PRIVATE_KEY = re.compile(
    r"-----BEGIN(?: [A-Z0-9]+)? PRIVATE KEY-----.*?-----END(?: [A-Z0-9]+)? PRIVATE KEY-----",
    re.DOTALL,
)
_GITHUB_TOKEN = re.compile(
    r"\b(?:gh[oprsu]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"
)
_AWS_ACCESS_KEY = re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")
_AUTH_HEADER = re.compile(
    r"(?im)\b(authorization\s*:\s*(?:bearer|basic)\s+)[^\s,;]+"
)
_BEARER = re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9._~+/=-]{12,}")
_CREDENTIAL_URL = re.compile(
    r"(?i)\b([a-z][a-z0-9+.-]*://)([^\s/@:]+):([^\s/@]+)@"
)
_ASSIGNMENT = re.compile(
    r"(?im)\b(api[_-]?key|token|auth[_-]?token|access[_-]?token|refresh[_-]?token|secret|password|passwd|cookie|session[_-]?id|client[_-]?secret)"
    r"(\s*[:=]\s*)(['\"]?)([^\s,'\";}]+)(['\"]?)"
)

_SENSITIVE_EXACT_NAMES = {
    ".npmrc",
    ".pypirc",
    "credentials",
    "credentials.json",
    "id_dsa",
    "id_ed25519",
    "id_rsa",
    "known_hosts",
    "secrets.json",
    "secrets.yaml",
    "secrets.yml",
}
_SENSITIVE_SUFFIXES = {
    ".der",
    ".jks",
    ".key",
    ".keystore",
    ".p12",
    ".pfx",
    ".pem",
}

_SAFE_ENV_NAMES = {
    "CI",
    "COMSPEC",
    "LANG",
    "LC_ALL",
    "NO_COLOR",
    "PATH",
    "PATHEXT",
    "SYSTEMROOT",
    "TEMP",
    "TERM",
    "TMP",
    "TMPDIR",
    "WINDIR",
}

_ALLOWED_EXECUTABLES = {
    "bundle",
    "bun",
    "cargo",
    "composer",
    "ctest",
    "dotnet",
    "go",
    "gradle",
    "gradlew",
    "make",
    "mvn",
    "node",
    "npm",
    "php",
    "pnpm",
    "py",
    "pytest",
    "python",
    "python3",
    "rspec",
    "ruby",
    "yarn",
    "git",
}


class SafetyError(ValueError):
    """Raised when an operation violates a helper safety boundary."""


class PathPolicy:
    """Resolve paths while preventing traversal or symlink escape from a root."""

    def __init__(self, root: str | os.PathLike[str]) -> None:
        self.root = Path(root).expanduser().resolve(strict=True)
        if not self.root.is_dir():
            raise SafetyError(f"Root is not a directory: {self.root}")

    def resolve(
        self, value: str | os.PathLike[str], *, must_exist: bool = True
    ) -> Path:
        raw = Path(value).expanduser()
        candidate = raw if raw.is_absolute() else self.root / raw
        resolved = candidate.resolve(strict=must_exist)
        try:
            resolved.relative_to(self.root)
        except ValueError as exc:
            raise SafetyError(f"Path escapes the configured root: {value}") from exc
        return resolved

    def relative(self, path: Path) -> str:
        return path.resolve(strict=False).relative_to(self.root).as_posix()


def is_sensitive_path(path: Path) -> bool:
    """Return True for filenames that commonly contain credentials or keys."""

    for part in path.parts:
        lowered = part.lower()
        if lowered == ".ssh" or lowered == ".aws" or lowered == ".gnupg":
            return True
        if lowered == ".env" or lowered.startswith(".env."):
            return True
    name = path.name.lower()
    return name in _SENSITIVE_EXACT_NAMES or path.suffix.lower() in _SENSITIVE_SUFFIXES


def ensure_not_sensitive(path: Path) -> None:
    if is_sensitive_path(path):
        raise SafetyError(f"Refusing to read a likely credential file: {path.name}")


def redact_text(value: str) -> str:
    """Redact common credentials without attempting to classify arbitrary data."""

    redacted = _PRIVATE_KEY.sub("[REDACTED PRIVATE KEY]", value)
    redacted = _GITHUB_TOKEN.sub("[REDACTED GITHUB TOKEN]", redacted)
    redacted = _AWS_ACCESS_KEY.sub("[REDACTED AWS ACCESS KEY]", redacted)
    redacted = _AUTH_HEADER.sub(r"\1[REDACTED]", redacted)
    redacted = _BEARER.sub(r"\1[REDACTED]", redacted)
    redacted = _CREDENTIAL_URL.sub(r"\1[REDACTED]:[REDACTED]@", redacted)

    def replace_assignment(match: re.Match[str]) -> str:
        return f"{match.group(1)}{match.group(2)}[REDACTED]"

    return _ASSIGNMENT.sub(replace_assignment, redacted)


def redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_value(item) for item in value)
    if isinstance(value, dict):
        return {str(key): redact_value(item) for key, item in value.items()}
    return value


def safe_environment(inherit: Iterable[str] = ()) -> dict[str, str]:
    """Build a minimal child environment and reject secret-like inherited names."""

    requested = set(inherit)
    unsafe = sorted(name for name in requested if _SENSITIVE_ENV_FRAGMENT.search(name))
    if unsafe:
        raise SafetyError(
            "Refusing to inherit secret-like environment variables: " + ", ".join(unsafe)
        )

    names = _SAFE_ENV_NAMES | requested
    child = {name: os.environ[name] for name in names if name in os.environ}
    child.update(
        {
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_TERMINAL_PROMPT": "0",
            "NPM_CONFIG_FUND": "false",
            "NPM_CONFIG_UPDATE_NOTIFIER": "false",
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        }
    )
    return child


def _normalized_executable_name(value: str) -> str:
    name = Path(value).name.lower()
    for suffix in (".exe", ".cmd", ".bat"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    return name


def _require_subcommand(argv: Sequence[str], allowed: set[str], tool: str) -> None:
    if len(argv) < 2:
        raise SafetyError(f"{tool} requires an explicit safe subcommand")
    subcommand = argv[1].lower()
    if subcommand not in allowed:
        raise SafetyError(f"Blocked {tool} subcommand: {subcommand}")


def _validate_python(argv: Sequence[str], policy: PathPolicy) -> None:
    if len(argv) < 2:
        raise SafetyError("Python requires a module or repository-local script")
    if argv[1] == "-m":
        if len(argv) < 3 or argv[2] not in {"pytest", "unittest"}:
            raise SafetyError("Only pytest and unittest modules are allowed")
        return
    if argv[1] in {"--version", "-V"}:
        return
    if argv[1].startswith("-"):
        raise SafetyError("Inline Python and interpreter control flags are blocked")
    script = policy.resolve(argv[1], must_exist=True)
    if script.suffix.lower() != ".py" or not script.is_file():
        raise SafetyError("Python must execute a repository-local .py file")


def _validate_node(argv: Sequence[str], policy: PathPolicy) -> None:
    if len(argv) < 2 or argv[1].startswith("-"):
        raise SafetyError("Node must execute a repository-local script file")
    script = policy.resolve(argv[1], must_exist=True)
    if script.suffix.lower() not in {".cjs", ".js", ".mjs"} or not script.is_file():
        raise SafetyError("Node must execute a repository-local JavaScript file")


def _validate_local_script(
    argv: Sequence[str], policy: PathPolicy, suffixes: set[str], tool: str
) -> None:
    if len(argv) < 2 or argv[1].startswith("-"):
        raise SafetyError(f"{tool} must execute a repository-local script file")
    script = policy.resolve(argv[1], must_exist=True)
    if script.suffix.lower() not in suffixes or not script.is_file():
        raise SafetyError(f"{tool} must execute a supported repository-local script")


def validate_command(argv: Sequence[str], policy: PathPolicy) -> list[str]:
    """Validate a test command and return a subprocess-ready argument list."""

    if not argv or not all(isinstance(item, str) and item for item in argv):
        raise SafetyError("Command must contain non-empty string arguments")
    if any("\x00" in item for item in argv):
        raise SafetyError("Command arguments may not contain NUL bytes")

    tool = _normalized_executable_name(argv[0])
    if tool not in _ALLOWED_EXECUTABLES:
        raise SafetyError(f"Executable is not in the verification allowlist: {tool}")

    if tool in {"python", "python3", "py"}:
        _validate_python(argv, policy)
    elif tool == "node":
        _validate_node(argv, policy)
    elif tool == "php":
        _validate_local_script(argv, policy, {".php"}, tool)
    elif tool == "ruby":
        _validate_local_script(argv, policy, {".rb"}, tool)
    elif tool == "git":
        _require_subcommand(
            argv, {"diff", "log", "rev-parse", "show", "status"}, "git"
        )
    elif tool in {"npm", "pnpm", "yarn", "bun"}:
        _require_subcommand(argv, {"run", "test"}, tool)
    elif tool == "cargo":
        _require_subcommand(argv, {"check", "test"}, tool)
    elif tool == "go":
        _require_subcommand(argv, {"test"}, tool)
    elif tool == "dotnet":
        _require_subcommand(argv, {"test"}, tool)
    elif tool in {"gradle", "gradlew"}:
        _require_subcommand(argv, {"check", "test"}, tool)
    elif tool == "mvn":
        if not any(arg in {"test", "verify"} for arg in argv[1:]):
            raise SafetyError("Maven command must include test or verify")
    elif tool == "composer":
        _require_subcommand(argv, {"run-script", "test"}, tool)
    elif tool == "bundle":
        _require_subcommand(argv, {"exec"}, tool)
        if len(argv) < 3 or _normalized_executable_name(argv[2]) != "rspec":
            raise SafetyError("bundle exec is limited to rspec")
    elif tool == "make":
        _require_subcommand(argv, {"check", "test", "verify"}, tool)

    executable = argv[0]
    if any(separator in executable for separator in ("/", "\\")):
        if tool != "gradlew":
            raise SafetyError("Explicit executable paths are blocked except for gradlew")
        executable_path = policy.resolve(executable, must_exist=True)
        executable = str(executable_path)
    else:
        located = shutil.which(executable, path=safe_environment().get("PATH"))
        if located is None:
            raise SafetyError(f"Executable was not found on PATH: {executable}")
        located_path = Path(located).resolve(strict=True)
        try:
            located_path.relative_to(policy.root)
        except ValueError:
            pass
        else:
            if tool != "gradlew":
                raise SafetyError(
                    f"Refusing repository-shadowed executable on PATH: {tool}"
                )
        executable = located

    return [executable, *argv[1:]]


@dataclass(frozen=True)
class CommandResult:
    command: list[str]
    returncode: int
    output: str
    duration_seconds: float
    timed_out: bool
    truncated: bool

    def as_redacted_dict(self) -> dict[str, Any]:
        return redact_value(asdict(self))


def _terminate_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        if os.name == "nt":
            process.kill()
        else:
            os.killpg(process.pid, signal.SIGKILL)
    except (OSError, ProcessLookupError):
        process.kill()


def run_bounded_command(
    argv: Sequence[str],
    *,
    policy: PathPolicy,
    cwd: Path | None = None,
    timeout_seconds: int = 120,
    max_output_bytes: int = 262_144,
    inherit_env: Iterable[str] = (),
) -> CommandResult:
    """Run an allowlisted command without a shell and retain bounded tail output."""

    if not 1 <= timeout_seconds <= MAX_TIMEOUT_SECONDS:
        raise SafetyError(f"Timeout must be between 1 and {MAX_TIMEOUT_SECONDS} seconds")
    if not 1 <= max_output_bytes <= MAX_OUTPUT_BYTES:
        raise SafetyError(f"Output limit must be between 1 and {MAX_OUTPUT_BYTES} bytes")

    effective_cwd = policy.resolve(cwd or policy.root, must_exist=True)
    if not effective_cwd.is_dir():
        raise SafetyError("Command working directory must be a directory")

    command = validate_command(list(argv), policy)
    environment = safe_environment(inherit_env)
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    started = time.monotonic()
    process = subprocess.Popen(
        command,
        cwd=effective_cwd,
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        shell=False,
        creationflags=creationflags,
        start_new_session=os.name != "nt",
    )
    assert process.stdout is not None

    chunks: deque[bytes] = deque()
    kept_bytes = 0
    observed_bytes = 0

    def drain_output() -> None:
        nonlocal kept_bytes, observed_bytes
        while True:
            chunk = process.stdout.read(8192)
            if not chunk:
                break
            observed_bytes += len(chunk)
            chunks.append(chunk)
            kept_bytes += len(chunk)
            while kept_bytes > max_output_bytes and chunks:
                overflow = kept_bytes - max_output_bytes
                first = chunks[0]
                if len(first) <= overflow:
                    chunks.popleft()
                    kept_bytes -= len(first)
                else:
                    chunks[0] = first[overflow:]
                    kept_bytes -= overflow

    reader = threading.Thread(target=drain_output, daemon=True)
    reader.start()
    timed_out = False
    try:
        process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        _terminate_process(process)
        process.wait(timeout=5)
    finally:
        reader.join(timeout=5)
        process.stdout.close()

    duration = time.monotonic() - started
    truncated = observed_bytes > kept_bytes
    output = b"".join(chunks).decode("utf-8", errors="replace")
    output = redact_text(output)
    if truncated:
        output = "[earlier output truncated]\n" + output
    if timed_out:
        output += f"\n[command timed out after {timeout_seconds} seconds]"

    return CommandResult(
        command=[Path(command[0]).name, *command[1:]],
        returncode=124 if timed_out else int(process.returncode),
        output=output,
        duration_seconds=round(duration, 3),
        timed_out=timed_out,
        truncated=truncated,
    )


def read_head(path: Path, max_bytes: int) -> tuple[str, bool]:
    if not 1 <= max_bytes <= MAX_OUTPUT_BYTES:
        raise SafetyError(f"Read limit must be between 1 and {MAX_OUTPUT_BYTES} bytes")
    with path.open("rb") as handle:
        data = handle.read(max_bytes + 1)
    truncated = len(data) > max_bytes
    decoded = data[:max_bytes].decode("utf-8", errors="replace")
    if truncated:
        decoded += "\n[later content truncated]"
    return redact_text(decoded), truncated


def read_tail(path: Path, max_bytes: int) -> tuple[str, bool]:
    if not 1 <= max_bytes <= MAX_OUTPUT_BYTES:
        raise SafetyError(f"Read limit must be between 1 and {MAX_OUTPUT_BYTES} bytes")
    size = path.stat().st_size
    with path.open("rb") as handle:
        if size > max_bytes:
            handle.seek(-max_bytes, os.SEEK_END)
        data = handle.read(max_bytes)
    decoded = data.decode("utf-8", errors="replace")
    truncated = size > max_bytes
    if truncated:
        decoded = "[earlier content truncated]\n" + decoded
    return redact_text(decoded), truncated
