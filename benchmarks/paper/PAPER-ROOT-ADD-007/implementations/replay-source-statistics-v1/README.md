# Retained-source replay statistics

This independent component reconstructs the **active temporal-permutation statistics** in retained `Replay_analysis.ipynb` source cell27 at commit`039228a3f1e079f5230fbb2bd794a714ab264b5c`. It adds a missing source-rule evaluator, not a new benchmark or an admitted paper outcome. The existing initial-evaluator cell-identity/re-decoding kernel remains a different prospective null.

`score_event(event, condition)` consumes one complete10-bin source window, source positions, decoded positions, declared all-zero-posterior flags and the exact500 caller-supplied temporal permutations. It removes zero-posterior columns, applies the original outward source-position-jump crop, then uses at least5retained bins. It recomputes average-rank correlation, literal inclusive uncorrected tails and population-standard-deviation Z. It does not sample a new RNG, import author code, construct a decoder or read files.

`score_stratum(context, selected_event_ids, events)` requires the exact ordered declared roster for one mouse/phase/cluster/decoder-side/condition stratum. Every selected event remains in the source fraction denominator, including skipped events. Tested-only fraction is an explicitly separate diagnostic. Empty selection returns null fractions. Constant trajectories and zero null spread stay visible; nonfinite source statistics are represented by null plus a status, never non-standard JSON NaN/Infinity. Literal comparison tails are retained for undefined constant trajectories; that is not a valid significance inference.

All500 temporal draws must be complete bijections after filtering. Duplicate draws are permitted because source sampling is with replacement across repetitions. This validates supplied draws, not independence, randomness, original RNG identity or source preprocessing. Mathematical arithmetic is independently implemented and not claimed bitwise identical to a historical NumPy/SciPy environment.

The source-selected roster, posterior-zero flags, rate maps, source cluster definitions, truth coordinates and final-paper panel mapping still require authentication. Truth-dependent outward cropping is reported explicitly and cannot be silently reused as a candidate superiority criterion. No across-mouse panel or candidate-versus-paper improvement rule is invented. The component returns reproduction/improvement null and qualification unresolved. Both paper/data and paper/data/author-code conditions must use the same eventual evaluator; no access condition is admitted here.

Source details and unresolved differences are in `SOURCE_OBSERVATIONS.json` and `../../docs/replay-active-source-recovery-v1.md`. No author source or authentic observations are redistributed.

Run the15 generated controls with:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -I -S -B benchmarks/paper/PAPER-ROOT-ADD-007/implementations/replay-source-statistics-v1/tests/test_replay_statistics.py
```

Tests cover analytic forward/backward ranks, ties and literal tails, population Z, silent-column removal, outward cropping, missing/extra roster records, selected-versus-tested denominator, undefined cases and malformed inputs. They establish engineering arithmetic only.
