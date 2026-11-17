# NEURAL-017 adaptive broker component

This package provides the accepted revision-v2 trusted protocol state machine for comparing a frozen prediction program with an adaptive policy on one complete NEURAL-017 panel. The source is an operator library; it has no experiment CLI or concrete backend. See the existing [NEURAL-017 source and scientific scope](../../neural-017/README.md).

The two arms must share explicit limits, public packet identity, permitted tools/checkpoints and a frozen reservation policy. Preparation is charged within the total budget. Training access can precede controller commitment; observed-query access requires a durable commitment of the actual program or policy. Each public operation reserves work before dispatch, retains reservations on failures and records measured overruns. Fixed-arm replies must identify the committed program; adaptive replies must identify the committed policy.

The contract fixes all 574 query trials, 140 time bins and 45 withheld units. This is one historical biological session, not 574 independent biological replicates. The broker carries identifiers and contract metadata; this package contains no authentic neural arrays, fitted models, private targets or scientific results.

## Integration boundary

Use distinct trusted `Backend` implementations for `Session(mode="frozen_program", ...)` and `Session(mode="case_adaptive", ...)`, and construct `PairedStudy` before preparation. The operator must serialize requests and authenticate their controller origin. Candidates must not receive the operator's `Session` object or supply trusted usage receipts.

The backend must enforce the public field boundary and real resource limits, isolate candidate execution, meter all work, durably capture controller source, and stop/reap resources. Finalization must stop the producer, capture immutable output through the still-live trusted holder, then remove the holder and volume. The backend must commit those bytes and the receipt before invoking the existing public-only numerical validator. Both full outputs must be committed and validated before either private grade is released to the operator. The broker checks trusted receipts; it does not implement isolation, hard preemption, NPZ validation or scientific scoring itself.

Always attempt cleanup of both arms, including when an earlier cleanup fails:

```python
try:
    # Perform preparation, controller commitments and permitted requests.
    fixed.finish()
    adaptive.finish()
    result = paired.grade()
finally:
    try:
        fixed.close()
    finally:
        adaptive.close()
```

This wiring fragment assumes an already constructed pair and qualified operator backends; it is not a runnable study. Failed cleanup still requires outer-runtime recovery. This source publication supplies no operational authority, backend qualification, matched experiment result or readiness promotion.

## Existing controls

From the repository root, using Python 3.11.18:

```sh
python -I -S -B -m unittest discover -s benchmarks/neuroscience/components/neural017-adaptive-broker-v1 -p 'test_adaptive_protocol.py' -v
```

The 20 existing unittest controls use invented scalar payloads, fake controller bytes, 574 invented trial IDs and opaque bytes explicitly not valid scientific NPZ files. They exercise access, accounting, controller binding, lifecycle failures, immutable commitment and the paired grading barrier. Fake validator/scorer responses are test fixtures, not numerical validation or neuroscience evidence.

Before this public package was assembled, 14 controls had executed against revision v2 and six text-identical prior behaviors were reused. Those are 20 unique retained controls, not 20 newly executed revision-v2 controls. Package assembly did not rerun tests. The appended public CI job is configured to authenticate all four component files and execute the complete 20-control suite; a passing run must be assessed from its own exact revision and artifact.

[PROVENANCE.json](PROVENANCE.json) records the frozen Python identities and that limited validation scope. No catalog, benchmark count, scientific metric or qualification status changes with this component.
