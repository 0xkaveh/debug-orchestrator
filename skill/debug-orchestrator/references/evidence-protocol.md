# Evidence Protocol

Use this protocol when a failure is intermittent, several hypotheses survive initial inspection, or the root-cause chain is not yet defensible.

## Evidence ledger

Maintain at most three active hypotheses. Give each a stable identifier and record:

- the proposed mechanism;
- observations it predicts;
- existing supporting and contradicting evidence;
- one cheapest experiment that can distinguish it from the alternatives;
- the experiment result;
- status: `active`, `rejected`, or `supported`.

Reject hypotheses when their predictions fail. Do not rewrite a failed prediction after seeing the result; create a new hypothesis if the mechanism materially changes.

## Experiment rules

1. Change one causal variable at a time.
2. Prefer read-only observation before instrumentation.
3. Prefer a focused test before a full suite.
4. Capture the exit code and a stable failure signature, not a wall of output.
5. Repeat timing-sensitive experiments enough to distinguish a signal from noise.
6. Restore configuration or code after each temporary experiment.

## Root-cause standard

A root-cause statement must connect an input or state, the responsible code path, and the observed symptom. Support the statement with at least two links in the chain, such as:

- a reproduction that reliably reaches the path;
- a trace, variable observation, or log event at the divergence point;
- a focused test that changes outcome when the mechanism is controlled;
- source history explaining when the behavior was introduced.

Correlation, proximity to an error line, and “this looks wrong” are not enough.

## Intermittent failures

- Record frequency and conditions before changing code.
- Stabilize time, randomness, concurrency, network, and external dependencies one at a time.
- Prefer deterministic fakes at the system boundary for the regression test.
- If the issue cannot be reproduced, preserve a bounded diagnostic plan and state the missing evidence. Do not ship speculative changes as a fix.

## Final evidence packet

Keep the final packet concise:

1. symptom and expected behavior;
2. exact reproduction and failure signature;
3. supported root cause and decisive evidence;
4. minimal fix and changed files;
5. regression test before/after result;
6. verification commands and exit codes;
7. instrumentation cleanup;
8. residual risk.
