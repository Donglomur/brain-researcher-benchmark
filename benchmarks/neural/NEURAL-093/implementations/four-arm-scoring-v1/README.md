# Recovered four-arm scoring and target definition

This component restores the existing NEURAL-093 numerical source that was
missing from the public package. Six files in `recovered/` are byte-identical
copies of the archived four-arm implementation; `scorer.py` captures and checks
their complete source closure locally. It needs Python 3.10+ and NumPy with the
`quantile(method=...)` API. No historical workspace path, installation, source
download, model, or participant process is needed to import it.

The recovered target is **left stronger (0), equal (1), right stronger (2)**.
Only finite released contrasts in [0,1] are valid. Equal includes both blank and
equal nonzero stimuli; it is not behavioral choice. `targets.target_classes`
implements the recovered mapping. `targets.partitions` uses original row
boundaries `floor(3N/5)` and `floor(3N/5)+floor(N/5)` before eligibility. For N=214
these are 128 and 170; computing `floor(4N/5)` would change the original split.
`eligible_split_rows` intersects already justified eligibility with these
boundaries; it does not establish eligibility or recording coverage.

Recovered observation facts are [0,0.1) seconds from stimulus onset, temporal
bins at 0/.02/.04/.06/.08/.1 seconds with native within-bin event timing, source
QC 2/3 clusters, context `u=original_row/max(N-1,1)` and `u²`, and wheel values in
encoder ticks relative to the first observed trial sample. The archived source
does **not** supply behavioral-history covariates. Sparse wheel timestamps must
be interpolated across zero-based sample-index anchors; this package does not
restore the full binary exporter or execute that interpolation.

Use `scorer.load_sources()` to access the recovered source modules. In particular,
`sources['packet_plan'].prepare(original_raw, binding_raw, contexts_raw, export_raw)`
authenticates the original immutable metadata binding and prepares all four
views. Its binding pin is retained; arbitrary replacement cohorts cannot enter
that public preparation API. These original metadata operands are operator
dependencies and are not distributed here. Context controls remove neural
events and unit metadata through an exact file allowlist while retaining the
same case tokens and permitted common files.

For operator scoring, call:

```python
report = scorer.score_study(
    panel, plan, commit, captured_prediction_bytes, protected_reader, numpy)
```

`panel` and `plan` are the recovered planner's outputs. `commit` follows
`recovered/comparison.py::validate_commit`. Prediction byte keys are
`(session_token, arm)`; each body follows the preserved
`neural093-candidate-predictions-v1` schema in
`recovered/trusted_metrics.py::validate_outputs`. `protected_reader(descriptor)`
returns the exact bytes of an operator-only SESSION mapping, including its
target labels. The mapping hash, identities, source-row uniqueness and ordered
query tokens are verified by the recovered scorer. No paths are opened by the
scoring API; the operator supplies and isolates this callback.

All 39 sessions, 10 mice, 2,042 query tokens per arm and 156 prediction tables
are mandatory. Every output is validated before the first target callback.
The adapter also restores the original controller's full-plan checks before
the recovered kernel, whose `zip` loop assumes that gate has already run.
Missing sessions/arms, duplicate/extra tokens, Boolean or nonfinite
probabilities, and sums outside 1e-8 fail. Probability normalization occurs
only inside that tolerance; a true-class zero retains infinite log loss.

The current contract's absolute joint-arm natural-log loss is returned in
`primary` (lower is better). `recovered_four_arm_summary` preserves the archived
summary unchanged: all four absolute losses, sum-of-three Brier and top-1
accuracy, both conditional neural increments, and the separate ln(3)-minus-
joint diagnostic. Each metric averages queries within session, sessions within
mouse, then the ten mice equally. The wheel/context-minus-joint log-loss
companion uses the original 10,000 paired-mouse PCG64 draws, seed 20261102 and
linear 2.5/97.5 percentiles. Its interval is conditional on fitted models, not
training uncertainty. Nonfinite mouse effects make the interval undefined;
they are never removed. The recovered summary retains its original
`prospective_primary` annotation for historical fidelity; the outer `primary`
implements the later canonical metric ordering.

This is executable scoring source with generated software controls. The caller
must authenticate source metadata and operator commitments independently:
Boolean chronology assertions and hashes supplied by a candidate are not
custody evidence. No authentic panel was prepared, no protected targets were
read, no four-arm candidate ran, and no participant isolation was qualified.
The returned session and mouse records remain operator evidence. Direct,
viewer, tool-assisted and frozen-program participation remain undelivered by
this package. Existing public exposure, within-session fitting, noncorresponding
units and possible movement in the fixed window still preclude unseen-cohort,
held-mouse, premovement, causal or native-understanding claims.

The adjacent generated test exercises a complete-shaped panel with invented
data, including unequal session counts and query counts, shuffled prediction
rows, malformed final output, shortened plan, target hash/identity mismatch,
control-view exclusion, true-class zero and exact original split boundaries.
Run it through the project's shared lightweight test pool. It provides no
biological performance estimate. Canonical task files and historical sources
remain unchanged; integration can use this recovery to correct the currently
stated missing-mapping/scorer dependency without promoting runtime readiness.
