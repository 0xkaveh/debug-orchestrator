# Agent instructions

These instructions apply to the entire repository.

- Keep all source, comments, documentation, fixtures, commit messages, and pull-request text in English.
- Preserve the evidence gates in `skill/debug-orchestrator/SKILL.md`.
- Keep the runtime dependency-free unless a proposal demonstrates why a dependency is essential and how its supply-chain risk is controlled.
- Treat security boundary changes as high risk. Add adversarial tests for path traversal, symlinks, secret handling, command execution, environment inheritance, timeouts, and output bounds as applicable.
- Do not copy third-party code or prose. Update `NOTICE.md` when a new conceptual source materially influences the design.
- Keep adapters optional and one reference level below `SKILL.md`.
- Never commit `.debug-orchestrator/`, raw logs, dumps, credentials, browser profiles, or generated evidence.
- Run `python -m unittest discover -s tests -v` and `python -m compileall -q skill tests` before completion.
- Keep CodeQL enabled with SHA-pinned actions and resolve security alerts before release.
