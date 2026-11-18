# Published prior-decoding metrics

This component computes the paper's prior-decoding effect sizes from operator-supplied out-of-fold predictions. It closes a specific gap in the preserved `initial-evaluator-v1`: the generic author script uses a mean across runs and a difference of regional medians, whereas the journal specifies a median across ten runs and a mean of session corrections. This version does not alter the historical evaluator, reconcile the executed author pipeline, recover the publication's numerical baseline, or establish benchmark readiness.

For every neural region-session or matched movement comparator, `metrics.py`:

1. Computes R² from all held-out trial predictions within each run, pooling trials before scoring. It checks five balanced outer folds for Ephys and fifty for WFI.
2. Takes the median of ten run R² values, separately for the real session and every one of 1,000 pseudosessions. It does not score the average predicted prior, which belongs to a different analysis in the paper.
3. Subtracts the median of those 1,000 pseudosession scores from the real-session score.
4. Takes the mean of the session corrections for each region, keeping Ephys and WFI separate. A region with one eligible session is retained, as in the paper. No scalar across regions/modalities is invented.

The frozen declared cell roster must match exactly. Duplicate cells, changing original trial identities, fewer than 250 retained trials, fewer than five neural features, missing nulls/repeats and incompatible folds are rejected. `optBay/pLeft` is required; the experimental block's `probabilityLeft` is a different target. Input-object and target-generator receipts are required, but receipts and a target name do not independently prove correct preparation or fitting.

Movement comparisons use an explicitly declared Ephys subset, with seven features, matching region-session ownership, ordered real trials and target values. Every supplied movement cell needs a neural counterpart. Neural cells without movement observations remain in the neural result. The paper has 414 Ephys region-level sessions and a separate 171-session / 806-region-session embodiment subset; requiring movement for every neural cell would incorrectly narrow the main endpoint. Repeated movement cells from one session must reuse the same actual predictions and partitions across neural regions, preserving the session-level movement fit. The component reports whether movement and neural outer partitions match but does not impose shared random partitions that the original study did not establish. These differences are descriptive; they do not implement residual decoding or causal attribution.

## Operator input

Use safe JSON for the manifest and one JSONL prediction file per cell. Each JSONL file has exactly 1,001 records; their order is arbitrary. Records have `pseudo_id` (`-1` for real, `1..1000` for null), `trial_ids`, `target` (scalar Bayes-optimal prior per trial), and `runs`. Each run has `run_id` (`0..9`), `prediction` and `test_fold` arrays of the retained trial length. The fold array gives each trial's outer test-fold number. All ten run records are required for every draw. Predictions may lie outside [0,1]; regression predictions are not clipped. Targets must lie in [0,1]. Constant targets have undefined R² and are rejected rather than replaced by a finite score.

The manifest contains `schema: "paper-find-004/journal-metrics-v2"`, `expected_cells` and `cells`. `expected_cells` is the frozen identity roster; each identity has `modality` (`ephys` or `wfi`), `subject`, `eid`, `region` and `predictor` (`neural` or `movement`). Each `cells` entry additionally has:

- `n_features`, ordered `trial_ids`, `target_model: "optBay"`, `target: "pLeft"`;
- `input_manifest_sha256`, `target_generator_sha256`;
- `prediction_file` relative to the manifest, and `prediction_file_sha256` of its exact bytes.

```sh
python3 metrics.py /operator/path/manifest.json --output /operator/path/metrics.json
```

Files are consumed one draw at a time, and their exact bytes are hashed while being scored. Output contains session/regional metrics and identity receipts, without target or prediction arrays. SHA-256 for structured objects uses compact UTF-8 JSON with sorted keys and `allow_nan=False`; ordered draw/run receipts are lists, avoiding numeric JSON-key ordering ambiguity. Duplicate JSON keys, nonfinite values, missing cells and file digest changes are rejected. Inputs and output belong in external operator evidence, never in the public repository.

## Scientific limits and validation

### Trusted native prediction export

`export_native_draw(fits, ordered_trial_ids=..., modality=..., pseudo_id=...)`
converts ten already-loaded native fit dictionaries into one draw accepted by
this component. This fills the transport gap left by the historical exporter,
whose fixed fifty-fold Ephys and 200-null assumptions belong to a different
protocol. The original exporter is unchanged.

The adapter checks actual train/test index arrays: five outer Ephys folds or
fifty WFI folds, exact complementary training sets, balanced complete test
coverage, ten distinct run IDs, a fixed draw identity and targets, and reported
R² against the pooled predictions. An exported `n_folds` scalar cannot override
those arrays. One scalar prior and prediction per retained trial is required;
time-binned or multi-target arrays are rejected rather than flattened. Native
NumPy-like values are accepted through `tolist()`/`item()` only at this trusted
operator boundary; no files, pickle, models or external services are opened.

The operator must supply original trial IDs in the order of this draw's actual
retained mask. The adapter cannot establish that this mapping or the fit is
truthful. The returned draw can be serialized as one JSONL record; the existing
cell scorer still requires the real draw and all 1,000 null draws, unchanged
trial identities, source receipts and complete metadata. A successful one-draw
conversion is not whole-cell, whole-cohort, nested-fitting or paper readiness.

The new focused controls exercise both modality partitions, real/null IDs,
false fold scalars, leakage, missing/duplicate test coverage, changed targets,
wrong reported scores, malformed scalar outputs and immutable exported data.
They use generated dictionaries only; no authentic fits or predictions were
loaded.

[Export provenance and source-route findings](native-export-provenance.json)
record the unchanged native field contract and the limits of the source lookup.

### Remaining scientific qualification

The original cohort (414 Ephys sessions / 2,289 region-sessions / 242 regions; 51 WFI sessions / 1,539 region-sessions / 32 regions), immutable input objects and original fold identities remain unrecovered. Counts alone cannot authenticate that cohort. A declared subset stays a declared subset, regardless of numerical outputs. This component validates supplied outer assignments, but cannot establish that fitting respected them or used the published nested inner folds, feature windows, QC and reaction-time selection. It neither fits models nor generates authentic Bayes targets/pseudosessions.

It deliberately does not implement a paper significance claim: the journal's quantile description does not resolve every finite-sample/tie convention, and the pinned generic script uses a distinct protocol. It also does not define paired uncertainty, a minimum improvement, an overall scalar ranking, or a paper-win decision. Movement residual and other companion analyses remain required for complete source comparison. The unchanged source improvement contract remains `source_unresolved`.

The generated tests distinguish median-of-scores from mean-of-scores and score-of-mean-predictions; distinguish mean session corrections from the old regional median rule; exercise Ephys/WFI folds, complete null grids, roster integrity and movement matching; and run the actual JSONL/manifest CLI on a generated complete grid. They establish software arithmetic and transport only. Run them through the coordinator's reviewed test pool, with one thread, at most 1 GiB and 180 seconds. No authentic data, fitting or model trials are part of these tests.

Source locations and cached source hashes are in [provenance.json](provenance.json). No third-party source text or authentic arrays are redistributed.
