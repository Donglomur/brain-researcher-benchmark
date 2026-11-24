# Exact JSON interface

Unknown fields and duplicate JSON keys are rejected. Numeric labels are integers 0/1, never booleans. IDs use 1–64 ASCII letters, digits, underscores, periods or hyphens, beginning with a letter or digit. Hashes use 64 lowercase hexadecimal characters.

Owner keys are exactly `schema`, `task_id`, `mode`, `provenance`, `mice`, `trials`, `historical`.

- `schema`: `rem-dmm-owner-v1`.
- `task_id`: `PAPER-SCOPE-20261114-REM-DYNAMICS`.
- `mode`: `historical_fig5e` or `prospective_onset`.
- `provenance`: exactly `article_sha256`, `official_code_commit`, `data_manifest_sha256`, `annotation_join_sha256`, `cohort_join_sha256`. Article and observed code pins are fixed by `score.py`. The other three bind externally reviewed metadata; valid syntax alone does not authenticate those documents. No provenance field is a grant of data access or scientific admission.
- `mice`: five distinct IDs.
- `trials`: exactly 45 objects with `trial_id`, `mouse_id`, `nrem_at_onset` (true), `rem_within_60s` (owner-only 0/1). Every mouse must contribute and exactly 20 trials have target 1. These checks verify supplied structural consistency, not actual animal or event identities.
- `historical`: null in prospective mode. Otherwise an object with `split_realization_sha256`, `train_count`, `bonferroni_factor`, `splits`. `train_count` is 31 or 32; `bonferroni_factor` is null or an explicitly admitted positive integer up to 10,000. The exact source family is unresolved, so null is presently the appropriate authentic-preparation value. `splits` has exactly 220 unique `(pc, repeat)` objects, each containing `pc` (1–22), `repeat` (0–9), `train_ids`, `test_ids`. Each split partitions all 45 trials without overlap/duplication and its training set has both classes. The code neither creates nor reuses a split automatically.

Candidate keys are exactly `schema`, `task_id`, `mode`, `case_plan_sha256`, `predictions`. Schema is `rem-dmm-predictions-v1`; task and mode match owner. The hash is SHA-256 of the UTF-8 bytes from `json.dumps(public_plan(owner), sort_keys=True, separators=(",", ":"), allow_nan=False)`. The public plan contains task, mode, five mice, trial/mouse ID pairs and historical split specification, never assessment outcome labels or private provenance.

Historical prediction rows contain exactly `pc`, `repeat`, `trial_id`, `predicted_label`. Every held trial in every cell occurs once; no training-only row is accepted. Row ordering is immaterial. The plan's list ordering is part of its hash and must not be silently rewritten.

An optional frozen comparator uses the identical prediction schema and plan hash: `score(owner, candidate, baseline)` or `python score.py OWNER.json CANDIDATE.json --baseline BASELINE.json`. This option is accepted only in `historical_fig5e` mode. Candidate and baseline are independently checked against the owner; neither can select a subset, supply target labels or substitute a training trial. The CLI records the raw baseline-file SHA-256. Freeze source identities, baseline generation and participant conditions externally: the case-plan hash binds declared support, not source provenance or authentic computation.

Prospective prediction rows contain exactly `trial_id`, `probability_rem_within_60s`. All 45 distinct trials are mandatory and probabilities must be finite within [0,1]. Historical split material is forbidden in this profile. Scientific causality and held-mouse isolation are external responsibilities, not inferred from the absence of a split list.

Reports contain all 220 confusion/accuracy cells and 22 summaries for historical mode, or all five mouse losses for prospective mode. One-sided t probabilities use a bounded incomplete-beta calculation with df=9. Degenerate zero-variance samples have null t/p values. No printed result is a learned improvement, admission certificate or score against an authentic native reference. Author-pipeline parity, research qualification and information isolation are explicitly false in every report from this source component.

Historical reports also retain each PC's ten `accuracies`, all five `mice` within each cell, and all 45 `trial_support` rows with `trial_id`, `mouse_id` and `held_split_uses`. Usage counts PC/repeat assessment cells, not unique independent observations. A mouse absent from a cell has zero confusion counts and null accuracy; a trial never held remains in the census with zero uses. These are coverage diagnostics and never change the pooled-trial weighting.

With a comparator, `comparison_present` is true. Each cell and mouse row adds `baseline_correct`, `baseline_accuracy`, `candidate_only_correct`, `baseline_only_correct` and `paired_accuracy_delta` (candidate minus baseline); absent-mouse baseline accuracy and delta are null. Each PC adds `baseline_accuracies`, `baseline_summary` using the same source chance-test calculation, `paired_accuracy_deltas` and their arithmetic `mean_paired_accuracy_delta`. A baseline chance test is not a candidate-versus-baseline test. No cross-PC selection, animal-level interval, paired p-value or superiority decision is supplied. Reused-trial resampling and unresolved source support prevent those stronger claims.

The file loader rejects static symlink components, hard links, FIFOs, directories, empty files, oversized files, duplicate keys, nonfinite constants, invalid encoding and excessive JSON depth. It compares descriptor size/times across the read. This is a bounded parser for owner-controlled evaluation: it is not a race-proof filesystem sandbox, credential scanner, hostile-code executor or proof of candidate isolation. The operator must mount the private owner outside every candidate context. The program writes only stdout and never mutates either input.

All reports are owner-only until the complete set of assessment submissions has been frozen. Never expose adaptive intermediate scores, confusion matrices, per-mouse losses or refusal details to candidates. The CLI does not implement a query budget or enforce this release boundary.
