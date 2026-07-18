# Debug Orchestrator

An evidence-led, security-first debugging skill for coding agents.

Debug Orchestrator makes an agent prove what failed, localize the causal mechanism, apply the smallest fix, add a regression guard, and verify the result with fresh output. It routes to browser, runtime, or CI tooling only when the current hypothesis requires it.

> Status: early alpha. Use it on local or disposable environments before trusting it with sensitive systems.

## Why this exists

Coding agents are fast at changing code. That speed becomes a liability when the agent guesses, edits several files at once, or declares success without reproducing the bug. This project puts hard gates around that behavior:

```text
Scope → Reproduce → Collect → Hypothesize → Localize → Fix → Guard → Verify → Report
```

- No product-code edits before reproduction.
- At most three falsifiable hypotheses.
- One cheap discriminating experiment at a time.
- Minimal context and bounded logs.
- No completed fix without regression coverage and fresh verification.
- Evidence in the final report, not “probably fixed.”

## Lightweight architecture

```text
skill/debug-orchestrator/
├── SKILL.md                 # Small core protocol loaded on trigger
├── agents/openai.yaml       # Codex UI metadata
├── references/              # Browser, runtime, CI, evidence, and security adapters
├── scripts/                 # Dependency-free bounded helper tools
└── assets/                  # Evidence and verification templates
```

The first release is intentionally a single-agent skill. It does not bundle Chrome DevTools, a DAP server, a log server, or an agent framework. Existing tools are selected lazily through adapter guidance. This keeps installation small, avoids background services, and reduces the supply-chain and network attack surface.

## Security model

The helpers use Python’s standard library and default to:

- repository-root path confinement, including symlink resolution;
- refusal to read common credential and private-key files;
- secret-pattern redaction;
- shell-free argument execution with an executable/subcommand policy;
- a minimal child-process environment with no secret-like inherited variables;
- timeouts and bounded tail output;
- no telemetry, background service, or automatic network request.

These controls are not a sandbox. Tests and project scripts are executable code. Review unfamiliar code and use a disposable container or VM before running it. See [SECURITY.md](SECURITY.md) and the skill’s [security policy](skill/debug-orchestrator/references/security-policy.md).

## Install for Codex

Clone the repository, then copy the skill directory into your Codex skills directory.

PowerShell:

```powershell
Copy-Item -Recurse -Force .\skill\debug-orchestrator "$env:USERPROFILE\.codex\skills\debug-orchestrator"
```

macOS or Linux:

```bash
cp -R ./skill/debug-orchestrator "${CODEX_HOME:-$HOME/.codex}/skills/debug-orchestrator"
```

Restart or open a new Codex task after installation so the skill is discovered.

## Use

Invoke the skill explicitly:

```text
Use $debug-orchestrator to diagnose this failing test. Do not change code until the failure is reproduced.
```

Or ask naturally for a systematic diagnosis. The skill metadata is designed to trigger for failing tests, builds, runtime exceptions, intermittent behavior, frontend/browser failures, performance regressions, and GitHub Actions failures.

The helper scripts can also be used directly:

```bash
python skill/debug-orchestrator/scripts/collect_context.py --root . --include pyproject.toml
python skill/debug-orchestrator/scripts/inspect_logs.py --root . app.log
python skill/debug-orchestrator/scripts/run_tests.py --root . -- python -m unittest
python skill/debug-orchestrator/scripts/verify_fix.py --root . .debug-orchestrator/verification-plan.json
```

Copy the JSON and Markdown templates from `skill/debug-orchestrator/assets/` into an untracked `.debug-orchestrator/` directory while investigating.

## Contribute

Contributions are welcome, especially:

- adversarial security tests;
- adapters that remain optional and progressively loaded;
- evidence-quality evaluations across languages and frameworks;
- improvements that reduce context or tool calls without weakening verification.

Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request. Report vulnerabilities privately as described in [SECURITY.md](SECURITY.md).

## Provenance

This is an independent implementation informed by public debugging workflows and tools. No third-party source code or skill text is included. See [NOTICE.md](NOTICE.md) for the source and license audit.

## License

[MIT](LICENSE)
