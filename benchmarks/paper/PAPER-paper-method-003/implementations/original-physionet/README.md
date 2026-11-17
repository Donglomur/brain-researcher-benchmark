# Original REVE PhysioNet-MI operator route

This route acquires the original EEGMMIDB v1.0.0 imagery EDFs, prepares the complete participant panel, emits label-free signal shards and evaluator targets, runs an explicitly frozen predictor, and computes the original four-class metrics. It is additive to the preserved `reve-s8` proposal; that historical package remains unchanged.

The original panel is **all 109 participants**, runs **04, 06, 08, 10, 12, 14**, split **1–70 train / 71–89 validation / 90–109 test**. No missing files are skipped and no split is inferred from present folders. The author describes **9,837 four-second examples**. Actual boundary drops and observed counts are retained, even if they disagree with that number.

## What is comparable

The selected primary is pooled test-epoch balanced accuracy (mean recall of four classes). Cohen kappa and support-weighted F1 are required companions. The published REVE-Base result is **0.6480 ± 0.0140** balanced accuracy, **0.5306 ± 0.0187** kappa and **0.6484 ± 0.0170** weighted F1. Those are published aggregates, not measurements from this implementation.

The pinned released preprocessing average-references, high-passes at 0.3 Hz, notches 60 Hz and resamples directly to 200 Hz. Paper Appendix C.5 instead describes an intermediate 128 Hz stage with a 64 Hz low-pass, then 200 Hz resampling. `panel.py` deliberately exposes only `released-06a7059-direct200`. A count match does not identify which historical recipe produced the score. Historical seeds, repeat count and SD denominator are also unbound. No source-code result here is automatically a paper reproduction or improvement.

## Acquire and prepare

Run from this directory using Python 3.11+. Store every output outside the repository. Reserve download/disk and native resources with the enclosing operator's resource controls before these commands. The acquisition bound covers exactly 654 EDFs, each capped at 4 MiB; the default total cap is 4 GiB. Peak external storage including prepared float64 arrays is about 6 GiB. Acquisition uses only the standard library, four download workers, HTTPS and the official SHA-256 manifest. It resumes only checksum-valid completed files.

```sh
python3 panel.py acquire --root "$REVE_DATA"
python3 panel.py inspect --root "$REVE_DATA" --output "$REVE_INSPECTION"
python3 panel.py prepare --root "$REVE_DATA" --output "$REVE_PREPARED"
```

Preparation needs NumPy, SciPy and MNE. It processes one recording at a time. The selected installed runtime has MNE 1.13.2, NumPy 2.4.6 and SciPy 1.17.1; these versions are not asserted to be the historical author environment. Every preparation receipt records its runtime. All 64 channels and 800 samples are retained. Microvolt arrays stay float64 because the author loader divides by 100 **before** casting to float32. There is no added z-score, clipping, spatial filtering, subject exclusion or epoch padding.

`inputs/panel.json` binds every signal shard, event ID, source identity, split, runtime and target-manifest hash. `operator/targets.json` contains labels; `operator/epoch-accounting.json` contains every annotation/drop. The preparation directory must be fresh, so a partial failed run cannot silently become a completed panel. Invalid or missing recordings fail explicitly. A source bad-channel flag requires authenticated interpolation geometry; none is guessed.

## Observed complete-panel preparation

The 2026-11-16 operator qualification authenticated all 654 official EDFs (1,668,148,896 bytes) and prepared **9,837 epochs: 6,300 train, 1,734 validation, 1,803 test**. Every original participant and imagery run was retained. The EDF headers show 636 recordings at 160 Hz and 18 at 128 Hz; the latter belong to participants 88, 92 and 100. The released MNE epoch rule drops one final imagery annotation in S104R08 because its four-second window exceeds the recording. This drop was recorded, not repaired by padding or cohort changes.

Preparation took 64.92 seconds with numerical-runtime thread limits set to six and a measured maximum resident set of 495,370,240 bytes, using the versions above. The preceding interpreter-path failure was recorded before data processing; the successful run used an explicit existing interpreter. A constant-output software control then exercised the real scorer and paired comparator on all 1,803 original test events. It verified exact event joins and expected metric behavior; it ran no model and supplies no scientific performance evidence.

The official checksum manifest has SHA-256 `7f5d16957d8ee7bce86cc7ccba0e5994f63f33781607eb3f838392d49311a208`. The prepared panel identity is `7d67c330bbd111b393c7ab72a5008e0b6fb6b90e891045336f15d3c3437b3ee9`. Matching the published epoch count resolves source completeness for this released-code profile. Historical filtering identity, downstream checkpoint identity, original run aggregation and author-model performance remain unresolved. This result does not change the task's scientific readiness or establish a paper win.

## Frozen prediction interface

`author_adapter.py` is the concrete author REVE-Base classifier adapter. Set `REVE_AUTHOR_SOURCE` to the unpacked pinned author source. It verifies exact imported source files and geometry, uses the source four-patch 64-channel classifier, divides microvolts by 100 before float32 conversion, and requires a complete **downstream classifier** state dictionary with strict loading. It never substitutes random classifier weights or an encoder-only checkpoint. CPU float32 SDPA math is explicit; backend and historical numerical parity remain qualification questions. Its declared dependencies must be available in a task-local or existing environment; the adapter never installs packages or downloads weights.

The official `brain-bzh/reve-base` pretrained release is an encoder. It does not supply the missing trained PhysioNet head. No exact Table 12 classifier checkpoint was located in the examined pinned source or official model listings, so an author inference run has **not** been qualified. A prospective source-recipe refit would require a separate frozen protocol and must retain validation-only selection; the released Optuna route's test-based objective is unsuitable for protected candidate selection.

```sh
python3 panel.py predict --panel "$REVE_PREPARED/inputs/panel.json" \
  --adapter author_adapter.py --adapter-sha256 "$REVE_ADAPTER_SHA256" \
  --checkpoint "$REVE_CLASSIFIER" --checkpoint-sha256 "$REVE_CLASSIFIER_SHA256" \
  --split test --batch-size 16 --output "$REVE_PREDICTIONS"
```

Another trusted operator adapter may export `load_predictor(checkpoint)` returning an object with `predict(signals_uv, channel_names) -> finite N×4 logits` in class order left fist, right fist, both fists, feet. The prediction runner gives it signals and channel names, never targets. It validates frozen adapter/checkpoint hashes before model construction and checks each selected signal shard immediately before its batches are passed to the predictor.

**This is trusted operator execution.** Python adapters run in the operator process. The `inputs/` and `operator/` directories are an interface separation, not an OS sandbox. Untrusted candidate code must run in an external isolated transport with only the permitted input view mounted. Do not expose this parent directory to a candidate. Public source annotations are already exposed in the original dataset; local file restrictions cannot undo that fact.

## Score and compare

Only the evaluator reads the target file. Predictions must contain exactly one row for every original test event, no duplicates, omissions or extras. Pooled metrics require all 20 test participants and all four classes. The wrapper authenticates the full original target manifest against the preparation identity, then joins by event ID.

```sh
python3 panel.py score --panel "$REVE_PREPARED/inputs/panel.json" \
  --targets "$REVE_PREPARED/operator/targets.json" \
  --predictions "$REVE_PREDICTIONS" --output "$REVE_SCORE"

python3 panel.py score --panel "$REVE_PREPARED/inputs/panel.json" \
  --targets "$REVE_PREPARED/operator/targets.json" \
  --predictions "$CANDIDATE_PREDICTIONS" --author-predictions "$REVE_PREDICTIONS" \
  --bootstrap-samples 2000 --bootstrap-seed 0 --output "$REVE_COMPARISON"
```

`metrics.py` also exposes `score_predictions`, `compare_predictions` and `aggregate_runs`. Participant summaries do not replace pooled scoring. Paired bootstrap intervals resample participants, recompute pooled metrics and omit training-seed uncertainty; they are descriptive, not an admitted paper-win rule. Run summaries require explicit independent seeds and report both population and sample SD rather than guessing the paper's denominator. The published score, measured author score and measured candidate score remain separate. Comparison outputs leave `paper_win` null and historical qualification false.

Acquisition, preparation, numerical software controls, a calibrated author rerun and scientific improvement are separate outcomes. Surpassing a published number alone does not establish improvement or current SOTA. Final targets must not influence preprocessing, checkpoint, candidate or hyperparameter selection.

## Primary source evidence and rights

- [REVE NeurIPS 2025 paper](https://proceedings.neurips.cc/paper_files/paper/2025/file/20a917f77773ac0fa8bea2bdd6606b66-Paper-Conference.pdf), Table 12 and Appendix C.5.
- [Pinned released preprocessing](https://github.com/elouayas/reve_eeg/blob/06a7059a07c3dabd80aee60c3dbc1eca4bdbe1c7/preprocessing/preprocessing_physio.py).
- [Pinned task configuration](https://github.com/elouayas/reve_eeg/blob/06a7059a07c3dabd80aee60c3dbc1eca4bdbe1c7/src/configs/task/physio.yaml), [loader](https://github.com/elouayas/reve_eeg/blob/06a7059a07c3dabd80aee60c3dbc1eca4bdbe1c7/src/downstream_tasks/dataloaders.py), [pooled evaluation](https://github.com/elouayas/reve_eeg/blob/06a7059a07c3dabd80aee60c3dbc1eca4bdbe1c7/src/dt.py).
- [Official EEGMMIDB v1.0.0](https://physionet.org/content/eegmmidb/1.0.0/), published checksum manifest under its files endpoint.
- [Frozen pretrained encoder revision](https://huggingface.co/brain-bzh/reve-base/tree/33841986f6cc1438d9dcdbca5a2137d60f6007d9): encoder model SHA-256 `8ecc650619598748286c2457f81f5c6bd12e8bb59db44f7b02af1955c44de8fe`, 276,773,456 bytes. This identity is not a downstream-classifier identity.

No dataset, targets, weights, author-source archive or prediction arrays are redistributed here. Check official dataset and checkpoint terms separately; the author's source MIT license does not automatically license all data or weights. Benchmark-owned source uses the repository license.
