# Finite paired sleep-stage scorer

This restores the numerical component of NEURAL-008 for its original **two exposed development people**, with 2,780 and 2,670 full-clock epochs. It recovers the original paired scoring source from repository history and gives it a portable local entrypoint. It does not replace the historical bridge, alter the canonical task, or adopt the proposed 153-night successor.

`neural008_vendor/candidate_adapter.py` is the unchanged registered source. `neural008_vendor/paired_core.py` differs from its recovered source only by a package-relative import. The original fixed-five-class metrics, complete support checks, optional claim arithmetic, and signed `EEG_EOG_clock − EEG_clock` contrasts are retained. Both probability panels validate before the target loader runs once. Source identities are in [PROVENANCE.json](PROVENANCE.json).

## Run

Use an existing Python environment with NumPy; no models or extra packages are needed. The submission contract is the existing [finite instructions](../registered-runtime/instructions.md): exactly `EEG_clock.npz`, `EEG_EOG_clock.npz`, and `claims.json`. Each uncompressed NPZ includes both people, their canonical epoch IDs, and five probabilities per epoch. A no-claim JSON is valid. Candidate code is never imported or run.

From this directory, public-only validation is:

```sh
python3 -I -B score.py --submission /operator/committed-submission \
  --validate-only --output /operator/new-validation.json
```

An operator with the separately authorized historical target files can score:

```sh
python3 -I -B score.py --submission /operator/committed-submission \
  --targets /operator/private-target-directory --output /operator/new-score.json
```

The target directory must contain exactly `manifest.json`, `development-001_labels.npz`, and `development-002_labels.npz`, matching the original byte counts, SHA-256 digests, and lineage manifest in `target_identity.json`. There is no CLI option for replacement target pins or a smaller panel. The output is a fresh JSON file in an existing directory; existing files are refused. Invalid inputs return a nonzero exit code and a failure report without target values or paths.

The operator must stop the prediction producer before invoking the scorer, control permissions to both input directories, and run grading separately from candidate execution. Stable-file checks and per-file hashes bind the bytes read; this command does not attest producer absence, sandbox a program, or authenticate how predictions were produced. It does not inherit the historical Docker worker's isolation claim or cost authorization.

## Interpretation

The result retains both arms' absolute per-person confusion matrices, support, F1, recall, and balanced accuracy. The primary result is an equal-person mean of the fixed-five-stage macro-F1 differences. REM recall remains null when a required person has no true REM; that person is never removed from the primary endpoint. Negative and zero differences are valid. No scalar optimization reward, scientific success floor, population interval, or p-value is returned.

Finished predictions cannot establish EEG-only access, matched training, or a physiological mechanism. In particular, shared YASA caches contain different information and pretrained weights and do not establish the prescribed EOG ablation. This scorer is neither direct interpretation nor viewer interpretation. It supplies no reference predictions, fitted models, recording preparation, or paired program runner.

## Verification and remaining gaps

`tests/test_score.py` uses generated probability arrays and generated targets only. Its independent arithmetic controls distinguish equal-person from epoch-pooled aggregation, retain negative differences, enforce undefined REM, exercise tie and mask semantics, and demonstrate rejection before target access for malformed second panels and claims. It also checks source recovery pins, modified files, linked inputs, strict target hashes/lineage, and public-only CLI behavior. Run these controls through the project's shared lightweight test pool.

All 14 controls passed with existing Python 3.11.6 and NumPy 2.4.6. The sanitized software-control record is [TEST_RESULTS.json](TEST_RESULTS.json); it records no authentic evaluation result.

No authentic target values, recordings, predictions, or model outputs were opened during this restoration. The preserved historical execution evidence is not rerun evidence. Authentic target replay and independent peer review remain necessary before updating the registered runtime. Modality-separated paired execution and reference replay are separate missing components. This source does not make NEURAL-008 a fully qualified benchmark.
