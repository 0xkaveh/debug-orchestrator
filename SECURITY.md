# Security Policy

Security is a release requirement for Debug Orchestrator, not a future enhancement.

## Supported versions

Only the latest release and the current `main` branch receive security fixes during the alpha period.

## Report a vulnerability

Do not open a public issue for a suspected vulnerability or include exploit details in a pull request.

Use GitHub’s private vulnerability reporting feature on this repository. Include:

- the affected file or version;
- a minimal reproduction using synthetic data;
- realistic impact and required preconditions;
- suggested mitigation, if known.

Do not include real credentials, personal data, production logs, or customer code. You should receive an acknowledgement within seven days. A disclosure timeline will be coordinated after triage and remediation.

## Security boundaries

The project’s Python helpers reduce accidental secret exposure and unsafe command composition. They do not isolate executed project code from the host operating system or network. Use a disposable container, VM, or restricted CI runner for untrusted repositories and pull requests.

Out of scope as standalone reports:

- denial of service that requires intentionally overriding documented size or timeout limits;
- redaction misses for arbitrary high-entropy strings with no recognizable secret context;
- malicious behavior in external debuggers, MCP servers, browsers, runtimes, or package managers that are not distributed by this repository.

These may still be accepted when they reveal a defect in our boundary claims or default configuration.

## Maintainer release checklist

- Run the complete test suite on supported Python versions.
- Review changes to command policy, path handling, redaction, CI permissions, and network behavior.
- Confirm no secrets, raw logs, dumps, browser profiles, or `.debug-orchestrator/` evidence are committed.
- Pin GitHub Actions to reviewed commit SHAs.
- Update the threat model when a new executable, network listener, or external integration is introduced.
