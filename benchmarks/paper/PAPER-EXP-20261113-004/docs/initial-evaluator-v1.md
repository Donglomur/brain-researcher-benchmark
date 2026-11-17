# Reward-relative chronological evaluation, initial construction source

This additive package implements the prospective improvement endpoint's protected split, candidate query projection, complete-support checks, and paired circular prediction scoring. It is useful executable construction source, **not a complete Figure 2–3 reproduction implementation or a scientifically qualified benchmark**. The canonical task and all historical source remain unchanged.

The implementation is original Python standard-library code. No upstream code or data is vendored. The official repository reports MIT licensing; Figshare and DANDI records in the canonical task report CC-BY-4.0. No authentic data, serialized objects, or native analysis pipeline were opened or executed during construction.

## Scientific identity and source decisions

The governing contract is `PAPER-EXP-20261113-004/task.json`, SHA256 `e90ae33da875213e1fa39479e32284a7997e6b91841f9cf2e6726e79ce2139be` (7,365 bytes). The paper is [Sosa, Plitt and Giocomo, 2025](https://www.nature.com/articles/s41593-025-01985-4), DOI `10.1038/s41593-025-01985-4`. The inspected official code commit is `adf0f9ed3defa22275d92fa0ed996f47008e05b3`; its relation to the historical published version remains unqualified. Exact inspected file pins are in the package's `provenance.json`.

The [pinned decoder](https://github.com/GiocomoLab/Sosa_et_al_2024/blob/adf0f9ed3defa22275d92fa0ed996f47008e05b3/src/reward_relative/decode.py) computes mean cosine of target minus predicted angle. Its contradictory “1 minus” docstring is not followed. Its projected-normal EM algorithm is not replaced with an ordinary sine/cosine least-squares fit. The package consumes independently supplied comparator predictions and leaves official calibration-only decoder qualification open.

The [Figure 3 notebook](https://github.com/GiocomoLab/Sosa_et_al_2024/blob/adf0f9ed3defa22275d92fa0ed996f47008e05b3/notebooks/Fig3_Decoder.md) identifies switch days 3, 5, 7, 8, 10, 12, and 14, and distinguishes its original occupancy-matched random block procedure from this task's prospective chronological split. No occupancy weighting or downsampling is silently inserted into the primary score: the canonical endpoint is the mean cosine within each held session, then session means within each animal, then an equal mean over animals. Occupancy-matched shuffle qualification remains open.

The current [dayData source](https://github.com/GiocomoLab/Sosa_et_al_2024/blob/adf0f9ed3defa22275d92fa0ed996f47008e05b3/src/reward_relative/dayData.py) supports the 11 switching IDs `GCAMP3`, `GCAMP4`, `GCAMP7`, `GCAMP11`, `GCAMP12`, `GCAMP13`, `GCAMP14`, `GCAMP15`, `GCAMP17`, `GCAMP18`, `GCAMP19`. The input must contain precisely these mice and every one of the seven days: 77 distinct mouse/day sessions. This checks expected structural coverage; authentic figure-specific inclusion still depends on admitted native records and cannot be inferred from a JSON roster.

Current source coordinate helpers use reward-zone start, track bounds 0–450 cm, circular wrapping, and trial slices tied to teleport indices. The native timeseries helper also applies speed and lick validity filtering. **This package does not implement or infer that transform**, nor reuse that behavior-filtered loader as a causal neural interface. An owner must supply already admitted radians in `[-π, π]`, with hashes pointing to transform and data-identity evidence. Such evidence fields are attestations, not an automatic authentication mechanism. Both supported admission labels (`engineering_control`, `owner_attested`) still yield unqualified construction results.

## Executable interface

Use Python 3.10 or newer; no installation is required. From the repository root:

```sh
python3 benchmarks/paper/PAPER-EXP-20261113-004/implementations/initial-evaluator-v1/evaluator.py prepare --owner-input owner-input.json --secret-file owner-secret.bin --candidate-output candidate/input.json --owner-output protected/plan.json
python3 benchmarks/paper/PAPER-EXP-20261113-004/implementations/initial-evaluator-v1/evaluator.py score --owner-plan protected/plan.json --candidate candidate-predictions.json --comparator official-predictions.json --output protected/score.json --bootstrap-repeats 2000 --seed 0
```

The owner supplies a secret of at least 32 bytes and keeps the owner input, secret, plan, targets, evidence, and scores outside candidate access. HMAC-derived opaque session, fold, trial, and sample IDs avoid exposing source names. Public sessions and folds are sorted by their opaque IDs, not source animal/day names. The plan's SHA256 catches accidental modification; it is **not a signature** against an attacker who can rewrite protected files. Actual filesystem isolation, submission freezing, network disabling, and authentic feature auditing remain owner responsibilities.

Owner input (`rr-owner-input-v1`) has exactly:

- `animals`: the 11 pinned switching IDs.
- `coordinate_evidence`: `admission`, `units` (`radians`), `source_commit`, `transform_evidence_sha256`, and `data_identity_sha256`.
- `sessions`: each has `session_id`, `animal_id`, `day`, `cell_ids`, `feature_evidence`, and chronological `laps`.
- `feature_evidence`: `kind` (`causal_neural`), `evidence_sha256`, and `fitted_sample_ids`. Every declared fit sample must belong to that session's calibration partition. This covers feature transformations and cell selection; a false receipt cannot be detected from numbers alone.
- Each lap: `lap_id`, `phase` (`pre` or `post`), `complete` boolean, and `samples`. Every sample has `sample_id`, strictly increasing `time_seconds`, `neural` with one finite value or `null` per channel, and owner-only `theta_rr`.

The top-level `schema` field is required. Unknown fields, duplicate IDs/JSON keys, NaN/Infinity, unexpected animals/days, missing sessions, incorrect channel dimensions, out-of-order clocks, missing pre-switch support, and insufficient complete post-switch laps fail closed. A calibration or evaluation window containing no observed neural value also fails. `null` values are retained as a missingness mask and filled with zero only in the candidate representation; observations and targets are never silently dropped.

For each session the split uses all pre-switch trials and the first `floor(N/2)` complete chronological post-switch laps for calibration, the next complete lap as a guard, and the remaining complete laps for evaluation. `N` counts complete post-switch laps. At least three complete post-switch laps are required. Incomplete post-switch laps are excluded and listed in owner-only traces. **Floor rounding for odd `N` is an explicit prospective engineering policy**, requiring scientific ratification; it is not claimed as an original paper convention. Guard and incomplete-lap samples never enter the candidate bundle.

Candidate input contains only opaque IDs, causal admitted neural values, required masks, clocks relative to the calibration/evaluation window, and separately admitted calibration angles. Evaluation angles and all source provenance stay private. The outer-fold plan groups all seven held sessions from a mouse and identifies the other 70 sessions eligible for algorithm selection. It is a split/interface implementation; it does not execute model selection or prove candidate code respected isolation.

Predictions (`rr-predictions-v1`) have `task_id`, the exact `candidate_input_sha256`, and all 77 sessions. Each session contains `session_id`, `predictions` (exact sample IDs and finite `theta_rr`), and `fit_receipt`. The receipt has exact complete `calibration_sample_ids`, `selection_session_ids` restricted to other mice, and `artifact_sha256`. Candidate and comparator must cover precisely the same evaluation observations and admitted calibration support. The complete generated fixture and prediction builder in `tests/test_evaluator.py` are executable schema examples, clearly marked engineering controls.

Scores report session results, 11 paired animal effects, their equal-weight means and paired gain. A seeded paired mouse bootstrap produces a prospective 95% percentile interval; 77 sessions never become 77 independent replicates. This interval has not been calibrated against an authentic reference and is not the paper's original statistical procedure.

## Verification and remaining holds

Run the bounded engineering controls:

```sh
python3 -B -m unittest discover -s benchmarks/paper/PAPER-EXP-20261113-004/implementations/initial-evaluator-v1/tests -v
```

The controls include analytically exact perfect/antipodal and wrap-seam scores, unequal sample-count aggregation, paired bootstrap determinism, minimum/odd/incomplete-lap handling, guard and target exclusion, opaque ordering/secret rotation, missing cohort or predictions, malformed receipts, nonfinite values, and held-mouse leakage. An independent reviewer additionally tested an unequal-count 77-session corpus against hand-derived mouse-level scores. Generated controls establish engineering behavior only.

Historical code identity; individual native file and cell membership; safe authenticated serialization; exact authentic coordinate/teleport and causal feature policies; complete Figure 2–3 reproduction including census, exclusions, shuffles, seeds and statistics; independently rebuilt official reference; calibrated tolerances; official matched decoder and occupancy shuffle; full-population runtime/memory; and protected scored execution all remain unresolved. No baseline competence, effect-size reproduction, scientific qualification, pretraining independence, or submission readiness is claimed. Public-data contamination remains an intrinsic limit. The implementation loads JSON in memory; it makes no validated streaming or full-cohort memory claim.
