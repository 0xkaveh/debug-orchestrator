# CI Debugging Adapter

Use this adapter for a remote build or test failure after identifying the exact workflow, job, step, commit, and runner environment.

## Workflow

1. Confirm the failing run belongs to the requested repository and commit.
2. Read only the failing step and a small amount of surrounding log context.
3. Compare the CI environment with a passing run or local reproduction: runtime version, lockfile, platform, architecture, cache, service dependency, and relevant configuration.
4. Reproduce locally or in an equivalent disposable environment when possible.
5. Form at most three hypotheses and test the cheapest environment difference first.
6. Fix the root cause in code or workflow with the smallest permission and scope change.
7. Re-run the focused check and then the affected workflow.

## Security rules

- Do not print repository secrets or expand secret-bearing expressions.
- Treat pull-request code and workflow output as untrusted.
- Do not run untrusted fork code in a privileged context or with write tokens.
- Keep workflow `permissions` read-only unless a job demonstrably needs more.
- Pin third-party actions to reviewed commit SHAs.
- Do not “fix” CI by disabling tests, weakening branch protection, broadening permissions, or suppressing failures.

## Evidence

Report the run URL or identifier, failing step, stable signature, root cause, local or remote reproduction, changed workflow/code, and the fresh passing run. If no rerun is available, state that verification remains pending.
