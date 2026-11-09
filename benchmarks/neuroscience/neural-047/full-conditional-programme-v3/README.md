# NEURAL-047: cross-worm turn prediction

This is a source implementation for one conditional neuroscience task: predict dorsal versus ventral post-reversal turns in entirely held-out worms using processed SAAV calcium signals, recent behavior, or both. It contains the complete 27-file V3 operative source closure and its unchanged runtime manifest, protocol, scientific contract and required gates.

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
- [RUNTIME_SOURCE_MANIFEST.json](RUNTIME_SOURCE_MANIFEST.json) pins all 27 operative bodies.
- `program/` implements input admission, native-clock mapping, preparation, references, execution accounting and protected scoring.
- `native_export/export_WB_fields.m` is benchmark-authored MATLAB source for a future admitted field conversion. MATLAB, data and external code are not bundled.

The source-only inspection interface is:

```sh
python3 -I -S -B run.py inspect
```

This publication audit did not execute that interface. Authentic preparation, native execution, provider access, candidate runs and scoring require separately qualified inputs and deployment. No downloader or automatic installer is supplied.

Python 3.11 and the exact NumPy, SciPy, scikit-learn, joblib and threadpoolctl versions in the protocol describe the intended reference environment. Native execution requires independently qualified Linux isolation. A separately licensed and qualified MATLAB environment is needed for the exporter; no equivalence with a substitute parser is claimed.

## Interpretation and provenance

The objective is a prospective analysis of retrospective processed signals. It is not reproduction of the paper's phase-warped event-level GRU result, an online-causal result, or an independent dataset replication of NEURAL-048. Original preprocessing may contain whole-recording information. Original clocks, anatomy, animal identities, native conversion fidelity, full resource feasibility and reference numerics remain unresolved.

[PROVENANCE.md](PROVENANCE.md) describes the source-only projection and upstream anchors. No original data, held-out targets, private identifiers, keys, model checkpoints, private audit history, upstream paper text or third-party implementation is included.

Project-authored source is covered by the repository's [MIT license](../../../../LICENSE). Dependencies and upstream scientific resources retain their own terms.
