# Runtime Debugging Adapter

Use a live debugger when source inspection and focused tests cannot reveal a value, branch, race, or call path. Use temporary instrumentation only when attaching a debugger is impractical or changes the behavior.

## DAP or native debugger

1. Attach only to the target process in the user-approved workspace.
2. Place the smallest number of breakpoints around the predicted divergence point.
3. Inspect only relevant frames and variables; avoid broad memory dumps.
4. Record the observation that supports or rejects the current hypothesis.
5. Remove breakpoints and terminate the debug session after the experiment.

Do not expose a debug adapter beyond loopback. Do not evaluate expressions with side effects. Avoid attaching to production or unrelated processes without explicit authority.

## Temporary instrumentation

- Prefer structured events with an experiment identifier.
- Redact at the source rather than after collection.
- Bound payload size, event count, and retention.
- Never record credentials, authorization material, complete request bodies, or unnecessary personal data.
- Keep the collector local and authenticated if it accepts writes.
- Mark probes with `DEBUG_ORCHESTRATOR_TEMP` so cleanup is searchable.

## Verification

After the fix, search for the temporary marker, confirm all probes and endpoints are removed, stop collectors, and delete local evidence that is no longer required.
