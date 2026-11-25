# NEURAL-047: cross-worm turn prediction

This is a source implementation for one conditional neuroscience task: predict dorsal versus ventral post-reversal turns in entirely held-out worms using processed SAAV calcium signals, recent behavior, or both. It contains the complete 27-file V3 operative source closure with corrections to clock and small-value arithmetic. The original runtime manifest, protocol, scientific contract and required gates retain their historical bytes; a separate current runtime manifest identifies the corrected source.

**Deployment is unconfigured. No authentic data preparation, candidate run, reference fit or scientific evaluation has been completed. This release adds no scientifically qualified or submission-ready benchmark.**

## Task and comparisons

Every independently verified eligible animal and reversal is required; the full cohort is currently unknown and must contain at least three animals. Each animal is held out once in the neural (N), behavior (B) and combined (NB) views. Mode F uses one frozen prediction program; mode I permits a precommitted investigation policy to develop a predictor within a fresh fold and view. These modes receive matched permitted information, with explicitly accounted tool use.

Three prospective references are implemented: fixed logistic regression, logistic regression selected using inner training animals, and a similarly selected boosted-tree model. These are unqualified reference implementations, not published performance results or SOTA claims.

The full programme requires `15 × n` contexts, `6 × n` candidate contexts, `9 × n` final reference fits and `27 × n × (n−1)` inner reference fits for `n` animals. It must not silently reduce the cohort, views or methods.

The neural view's animal-macro balanced accuracy is primary, with equal-animal binary log loss co-primary. All views and animals are reported. If any animal has one class, whole-panel balanced accuracy is undefined; that animal and all log losses remain in the report. Whole-animal bootstrap intervals are descriptive because training folds overlap.

## Source layout

- [SCIENTIFIC_CONTRACT.md](SCIENTIFIC_CONTRACT.md) defines the original input requirements, splits, references and estimands.
- [PROTOCOL.json](PROTOCOL.json) specifies the complete programme and dependency versions.
- [GATES.json](GATES.json) retains all 12 open qualification gates.
- [DEPLOYMENT.json](DEPLOYMENT.json) leaves all eight deployment authorities null.
- [RUNTIME_SOURCE_MANIFEST.json](RUNTIME_SOURCE_MANIFEST.json) preserves the 27 predecessor source pins.
- [CURRENT_RUNTIME_SOURCE_MANIFEST.json](CURRENT_RUNTIME_SOURCE_MANIFEST.json) pins the same 27 operative paths with the corrected history and feature arithmetic identified explicitly.
- `program/` implements input admission, native-clock mapping, preparation, references, execution accounting and protected scoring.
- `native_export/export_WB_fields.m` is benchmark-authored MATLAB source for a future admitted field conversion. MATLAB, data and external code are not bundled.

The source-only inspection interface is:

```sh
python3 -I -S -B run.py inspect
```

This publication audit did not execute that interface. Authentic preparation, native execution, provider access, candidate runs and scoring require separately qualified inputs and deployment. No downloader or automatic installer is supplied.

Python 3.11 and the exact NumPy, SciPy, scikit-learn, joblib and threadpoolctl versions in the protocol describe the intended reference environment. Native execution requires independently qualified Linux isolation. A separately licensed and qualified MATLAB environment is needed for the exporter; no equivalence with a substitute parser is claimed.

## Clock arithmetic correction

History membership, recording coverage and landmark selection compare the exact represented values of supplied Python integers and floats against the exact represented values of the existing binary64 constants `4.8` and `2.4`. Selected time differences are computed exactly before one conversion to float. The existing inclusive history interval and minimum landmark delay are unchanged; rounded absolute boundaries no longer determine membership.

This deliberately changes faulty boundary selections. The supplied float `495.2` is more than the existing `4.8` constant before `500.0` and is excluded. At an onset of `497.6`, `500.0` is earlier than the existing `2.4` delay and a later native timestamp is required. Five-second histories and two-second landmarks on coarse clocks remain outside the declared bounds. No epsilon, endpoint clamp, nominal frame rate or decimal reinterpretation is used. If distinct exact differences collapse to equal float offsets, preparation raises an error instead of silently dropping an event or animal. Existing missing-frame, behavior, target and full-panel rules remain in force.

The [current source descriptor](../../../../../integrity/current-closures/numeric-neural047/SOURCE.json) binds the correction, complete successor manifest and generated controls while preserving predecessor evidence. The existing runtime interface accepts an explicitly selected `programme_manifest_path` only when its bytes match the independently admitted runtime `source_manifest_pin`, which must also match the reference-numerics admission. A future qualified deployment can select `CURRENT_RUNTIME_SOURCE_MANIFEST.json` through that interface; no automatic selection or qualification is added. Both source authentication functions accept the complete current closure and reject the predecessor manifest against the corrected source.

Bounded generated controls cover extraction, strict feature validation, all three views of a three-animal panel, representability refusal and source authentication. They do not execute models or native operations. Run from the repository root:

```sh
python3 -I -S -B tests/benchmarks/test_neural047_clock_arithmetic.py -v
```

The clock correction establishes arithmetic consistency of supplied values only. Native clock lineage, physical precision, animal identity, authentic data, reference numerics and deployment qualification remain open.

## Small-value arithmetic corrections

The active reference feature map preserves a representable nonzero population standard deviation when squaring very small centered values would underflow to zero. A scaled calculation is used only in that case; constant histories and the normal arithmetic path are unchanged.

Post-reversal direction is determined from the sign of the exact sum of the two supplied binary64 or integer curvature values. This is the sign of their mathematical mean. It preserves a nonzero direction when halving each tiny value separately would produce zero, while exact cancellation retains the existing zero-direction exclusion. No epsilon, new threshold or different target window is introduced.

Generated controls cover strict JSON transport, the active feature-validation path, complete three-animal construction, tiny nonzero direction, exact zero exclusion and ordinary/large-value parity. These are source arithmetic checks, not authentic input qualification, reference fitting or model performance:

```sh
python3 -I -S -B tests/benchmarks/test_neural047_summary_underflow.py -v
python3 -I -S -B tests/benchmarks/test_neural047_direction_underflow.py -v
```

## Interpretation and provenance

The objective is a prospective analysis of retrospective processed signals. It is not reproduction of the paper's phase-warped event-level GRU result, an online-causal result, or an independent dataset replication of NEURAL-048. Original preprocessing may contain whole-recording information. Original clocks, anatomy, animal identities, native conversion fidelity, full resource feasibility and reference numerics remain unresolved.

[PROVENANCE.md](PROVENANCE.md) describes the source-only projection and upstream anchors. No original data, held-out targets, private identifiers, keys, model checkpoints, private audit history, upstream paper text or third-party implementation is included.

Project-authored source is covered by the repository's [MIT license](../../../../LICENSE). Dependencies and upstream scientific resources retain their own terms.
