# Contributing

Thank you for helping build a debugger that earns trust through evidence.

## Before opening a change

1. Search existing issues and pull requests.
2. For a large adapter or behavior change, open a proposal describing the debugging problem, security impact, context cost, and verification approach.
3. Keep external integrations optional. The core skill must remain useful without Chrome, DAP, MCP, or a background service.
4. Do not copy third-party source or skill text. Record conceptual influences and licenses in `NOTICE.md` when relevant.

## Development

Requirements:

- Python 3.10 or newer;
- no runtime third-party Python dependencies.

Run the checks:

```bash
python -m unittest discover -s tests -v
python -m compileall -q skill tests
python skill/debug-orchestrator/scripts/run_tests.py --root . -- python -m unittest discover -s tests
```

## Pull request standard

- Keep the change focused and explain the failure mode or capability gap.
- Add a regression or security test for behavior changes.
- Preserve path confinement, bounded reads/output, secret minimization, timeouts, and `shell=False` execution.
- Document any new permissions, executable, environment inheritance, network access, or persistent artifact.
- Use synthetic fixtures only.
- Update the skill or its progressively loaded reference, not both, when one source of truth is enough.
- Confirm temporary debugging artifacts are absent from the diff.

Pull requests should describe what changed, why it changed, user and security impact, and the exact validation commands used.

## Review priorities

Maintainers review changes in this order:

1. security boundary and data exposure;
2. correctness and evidence quality;
3. regression coverage;
4. context and runtime cost;
5. ergonomics.
