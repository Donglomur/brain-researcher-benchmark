# Hybrid causal prediction: synthetic controls

This package tests a causal prediction interface and its scoring rules on invented behavioral observations. It contains no human data, fitted scientific reference, protected answers or candidate model result.

The 31 controls exercise a complete invented 20-by-4 group structure: serialized input, current-observation queries, committed four-action probabilities, full population coverage, grouped negative log likelihood, participant-level paired comparisons, source-derived cognitive forwards and small ridge fits. They also test missing/duplicate predictions, invalid probabilities, future-state perturbations, chronology, absent action classes and unequal trial lengths. All 31 test bodies are retained from the reviewed scientific implementation.

The primary score averages decisions within a session, sessions within a participant, then participants equally. Trial-balanced and decision-weighted scores are separate diagnostics. This is a recorded-trajectory next-action task, not a counterfactual simulator or an RL return evaluation.

## Run the complete controls

Use CPython 3.11 on Linux or macOS. NumPy is the only dependency beyond the standard library. The version is pinned to 2.2.6, matching the accepted earlier synthetic-control runtime; this does not imply identical binaries or cross-platform numerical parity.

In a disposable environment, install the public dependency:

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install --only-binary=:all: --no-deps -r benchmarks/neuroscience/hybrid-causal-controls-v1/requirements.txt
```

Create an output parent, then run from the repository root. The output leaf must not exist:

```sh
mkdir -p artifacts
.venv/bin/python -I -B benchmarks/neuroscience/hybrid-causal-controls-v1/run_controls.py \
  --out "$PWD/artifacts/hybrid-controls" \
  --selection-sha256 e9997b264cf7bd7a4f0e7be2d5847d84cc35d7f5db93bb2edd04256d3e16acbe
```

The runner authenticates the relative source lock, requires exactly the 31 named tests with no skipped cases, and preserves the complete outcome in `RESULT.json`. Test progress and tracebacks go to stderr. Any failure returns nonzero; rerunning requires a different fresh output directory. The original success deadline is 45 seconds. Managed source reads and the JSON report are each capped at 1 MiB; dependency imports and operating-system I/O are not included in the source ledger. There is no hard memory quota. CI adds an external 50-second timeout with five seconds for termination and retains the original exit status and both streams.

The six scientific/test modules are loaded from authenticated bytes. Four files are unchanged; `consumer.py` changes only its module documentation and the authentic-file admission constant, and `cognitive.py` changes only its module documentation. Every scientific function/class body and all test bodies remain byte-identical to the accepted source.

## What is deliberately unavailable

`consumer.MAIN_CASE_SHA256` is `None`. The original loader compares a hexadecimal string digest with that value, so no authentic file can be admitted. **The loader still opens and hashes an operator-selected file before refusing; filesystem access is not disabled.** The source population counts are retained contract metadata, not released participant records. The tests provide only invented files and in-memory decisions.

`pipeline.score_submission` consequently cannot admit an authentic case stream in this package. Its reference-composition function is retained as source, but the 31-control run does not fit or qualify a full empirical reference. `OnlineSession` is a trusted controller API: untrusted code must not receive that object or share evaluator memory/data. This package supplies no candidate sandbox or protected model-execution service.

These are source-derived Float64 calculations and a newly declared regularized statistical reference. They do not reproduce the original Julia loader, establish Float32 parity, recover missing sensory histories or validate a biological mechanism. Synthetic optimizer controls are not scientific fits. No benchmark count, scientific-readiness, full-paper reproduction, frontier-improvement or submission-acceptance claim follows from passing these controls.

See `ATTRIBUTION.md` for source provenance and rights boundaries.
