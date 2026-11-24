# Audit the original within-time decoding panel from predictions

This operator component reconstructs Figure 2h's complete within-time accuracy panel from held prediction exports. It supplies the within-time counterpart to the existing [cross-time prediction audit](../cross-time-prediction-audit-v1/README.md). The existing [source reducer](../source-decoding-metrics-v1/README.md) receives precomputed full-panel accuracies and can score only an isolated threefold window from predictions. This component verifies every declared within-time held fold and reconstructs all 9,550 mouse/state/repeat/window cells.

The publication [processSession_decoding.m](https://github.com/eabhorrocks/Horrocksetal24_TemporalDynamics/blob/e3796c13fe7afe7a84854cd5a02c36de268e88f4/Decoding/processSession_decoding.m) calls [do_cvDA.m](https://github.com/eabhorrocks/Horrocksetal24_TemporalDynamics/blob/e3796c13fe7afe7a84854cd5a02c36de268e88f4/NeuralDataAnalysis/do_cvDA.m) separately for each state, each of five repeats, and each of 191 overlapping 100 ms windows. Each call draws its own threefold `cvpartition`. Within one call the same positions are shared across the six classes. Training and testing indices are ordered `find()` results. The source averages the three fold accuracies equally; pooling correct counts across unequal folds changes that metric. The frozen manifest therefore records a separate partition for every call, and the audit retains fold counts and denominators before equal-fold averaging. It does not invent seeds or force the cross-time shared-draw policy onto within-time decoding.

## Operator inputs

The manifest has schema `horrocks-within-time-audit-manifest/v1`, the task ID, pinned publication commit, three source binding digests (`observations_sha256`, `eligibility_recipe_sha256`, `source_class_mapping_sha256`), and all five original named sessions. Each session supplies `n_trials`, integer `class_order` 1 through 6, and both `stat` and `run` states. Each state supplies the ordered full `unit_ids`, six ordered `trial_ids` lists, and `partitions[repeat][time][fold]`. Each fold has ordered one-based `train_positions` and `test_positions`. The three held folds must partition all positions exactly once, their sizes must differ by at most one, and each training set must be the exact testing complement. The unit roster must agree between states; class/state trial reuse is rejected. See `fixture()` in the tests for a generated example, never an authentic roster.

The selected endpoint requires three folds. The implementation refuses fewer than three trials per class rather than silently switching to the source function's lower-trial leave-one-out fallback. It also refuses more than 10,000 trials per class. This is a construction resource ceiling, not permission to subsample authentic inputs.

Prediction JSONL starts with a `horrocks-within-time-predictions/v1` header containing `audit_manifest_sha256`, `method_sha256` and `condition` (`paper_data` or `paper_data_author_code`). Each following record supplies `session`, `state`, `repeat` (1–5), `time_index` (1–191), and three `folds`. Every fold contains `held_trial_order_sha256` and six `predicted_classes` lists in source true-class order. The held digest is SHA256 of compact sorted-key JSON for the six ordered held trial-ID lists. Every held trial must have one integer prediction in 1–6. Extra fields, duplicate cells, and incomplete support are rejected.

**Operator only:** grouping predictions by true class reveals scoring labels. Do not expose this export, its manifest, trial map or evaluator to participants. Fabricated predictions can pass arithmetic and support checks; source authenticity, protected capture, fitted-model/training-access verification and access-condition isolation require a separate trusted execution boundary. Hashes bind declared files and do not prove those properties.

## Invocation and output

```sh
python3 -I -S -B within_time_audit.py \
  --manifest operator-manifest.json --manifest-sha256 <frozen-manifest-sha256> \
  --predictions predictions.jsonl --predictions-sha256 <frozen-predictions-sha256> \
  --output audited-within-time.json
```

The audit checks both complete input digests before writing a new output; existing output files are not overwritten. Manifest input is capped at 32 MiB, prediction input at 128 MiB, and individual JSONL lines at 1 MiB. A complete authentic export exceeding a cap must be reviewed for a prospective resource adjustment, never trimmed. Duplicate JSON keys, nonfinite values, blank lines, missing final newlines and trailing records are refused.

For each original session/state the output retains `correct_counts`, `trials_per_fold` and `fold_accuracy` in repeat × time × fold order, plus `within_time` in repeat × time order. The full 191 time centers run from −150 to 1750 ms in 10 ms steps. No favorable window, mouse, state or repeat is selected. The separate within-time audit schema cannot be supplied directly to the full source reducer, which also needs separately authenticated cross-time arrays. Combining independently authenticated endpoints and evaluating candidate/author pairs remain future operator responsibilities.

## Validation and scientific limits

The maintained tests use generated in-memory full panels. They check unequal-fold weighting, distinct state/window partitions, ordered exact complements, exhaustive held support, missing/duplicate cells, held-identity mismatches, invalid predictions, complete stream hashes and trailing-data rejection. A mocked output checks CLI write ordering and exclusive creation; no successful authentic disk export or MATLAB execution is claimed.

This module does not prepare authentic spike arrays, fit the GammaOne decoder or inner delta tuning, recover the native source reference, establish a paper outcome, freeze superiority thresholds, or change task readiness. Training-fold variance filtering and actual fitting provenance remain outside the audit. Both declared information conditions retain unknown reproduction and improvement outcomes. Full-panel effect/uncertainty and protected relative-generalization policies remain unresolved.
