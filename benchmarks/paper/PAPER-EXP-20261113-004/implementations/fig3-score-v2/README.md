# Original Fig. 3b scoring component

This component computes the original paper's **session mean cosine decoding scores** from externally frozen folds, and exports the pinned author's native array layout into an explicit JSON panel. It addresses the missing original-endpoint scorer; the predecessor `initial-evaluator-v1` remains a separate chronological extension. No canonical task or improvement contract is changed.

Every panel requires the eleven switching mice and seven days, all three native cell categories (`rr`, `track`, `nonreward_remap`), and all five native model conditions. The `train0_test0` and `train0_test1` conditions supply the 462 Fig. 3b session/condition rows. The remaining 693 rows retain the author's after/after, after/before and whole-session random controls. Neither the 1,155 rows nor the ten folds are independent biological replicates.

The metric is mean cosine across samples **within each fold**, followed by an equal mean of the ten fold scores. Unequal fold sizes must retain this weighting. Each session's shuffle score averages the original 100 repeats and ten folds. The source array is `[repeat, fold, model] = [100, 10, 5]`; it is not model-first. A standardized effect such as 2.7 is rejected as a cosine score.

This is an executable arithmetic component, not authenticated source preparation or a qualified benchmark. It does not create folds, sample occupancy, choose cells, fit a model, load pickles, or determine a paper win. It does not compute the separate Fig. 3c position-bin z-score curves or Fig. 2 calibration outputs. Those companion endpoints remain required for full qualification.

## Frozen owner inputs

All native exports, targets, predictions, identities, receipts and results belong outside Git and outside participant access. The schemas here are **owner-side**, not candidate delivery schemas. No authentic target or historical private answer was opened to build this component.

`reward-relative-fig3-panel-v2` has exactly `schema`, `source_commit`, `preparation_sha256`, `fold_receipt_sha256`, and `rows`. Each row has `animal`, `day`, `cell_type`, `model`, `folds` and `shuffle_scores`. Each of ten folds has ordered `sample_ids`, `actual` angles, and `predicted` angles, all in radians. Shuffle scores are `[100,10]`. The generated fixture in `tests/test_fig3_score.py` gives a complete software example.

The two SHA256 fields identify frozen owner preparation and fold receipts. They are assertions of identity, **not authentication**. The external owner protocol must bind native data versions, full cohort, retrospective cell memberships, permitted observations, preprocessing, occupancy selection, source training indices, stochastic protocol and execution custody. It must match candidate and author privileges. The source helper chooses 90% of the training index pool without replacement after excluding each test fold; this component consumes that frozen protocol and does not substitute a new split. Historical RNG state is not required if a protocol-equivalent rerun is admitted.

Sample IDs must be assigned by that owner preparation from actual observation indices. The scorer checks that fold lengths follow the source `np.array_split` rule; samples are unique across folds; both training conditions and all cell populations sharing a test set have identical ordered test samples and targets; and before/after test sets are disjoint. It cannot establish that supplied IDs correspond to real records, nor verify training access from predictions. Exact fold identity includes order and target values. A target change or receipt mismatch rejects a paired comparison.

The native adapter takes a JSON object containing `pred`, `actual`, `scores`, and `scores_shuffle` from the source decoder output, with arrays converted to lists and day keys to strings by an already admitted loader. It also needs a separate support JSON map `day -> animal -> model -> ten ordered sample-ID lists`. It does not synthesize IDs from angles or positions in prediction arrays. It validates all source dimensions and recomputes each stored real fold score with a numerical consistency tolerance of `1e-10`; this is an arithmetic tolerance, not a paper calibration margin. Nonfinite values fail instead of silently reducing the panel with `nanmean`.

## Commands

From this implementation directory, using Python 3.10+ with no dependencies:

```sh
python3 -B fig3_score.py export-native --native /owner/native.json --support /owner/support.json --preparation-sha256 SHA256 --fold-receipt-sha256 SHA256 --output /owner/author-panel.json
python3 -B fig3_score.py score --panel /owner/author-panel.json --output /owner/author-scores.json
python3 -B fig3_score.py compare --candidate /owner/candidate-panel.json --author /owner/author-panel.json --output /owner/paired-scores.json
```

Outputs are created exclusively, so frozen results cannot be overwritten. Duplicate JSON keys, malformed dimensions, missing companion conditions, repeated observations, mismatched targets, nonfinite predictions and invalid cosine scores reject before output. The comparison returns all session gains and seven-session means for each mouse and condition. It supplies no confidence interval, significance test, pooled headline score or superiority decision; these need the original-score distribution and an admitted meaningful-effect/multiplicity rule.

## Source table and comparison roles

`score` also returns `figure3b_source_table`: all 924 real/shuffle records for the 462 published train-before conditions, using the source columns `mouse`, `switch`, `day`, `ct`, `model`, `score_type`, `score`, and `sess_id`. Switch numbers follow the seven declared days; session IDs are `mouse_day`. Source notebook lines 843–877 define these keys and the two-model filter. Export order is canonical day/mouse/class/score-type/model order; the historical `include_ans` order has not been authenticated. The original 1,155 condition records remain present and mandatory, including all 693 controls.

This table covers the scorer's existing **finite input domain only**. Source `nanmean` behavior is not implemented here; missing or nonfinite source inputs still reject. Table construction does not qualify historical references, missingness handling, or source fitting.

Scored and paired session/mouse records now carry `figure3b` and `score_role`. Only true-label `train0_test0` and `train0_test1` scores are directional performance targets. Gains for the other three native model conditions remain descriptive control differences. Shuffle scores and the separately required Figure 3c profiles are fidelity/protection companions, even if their values increase. No target/control values are dropped, and no new scalar, uncertainty rule or win criterion is introduced. All seven sessions remain together within each mouse summary. This reporting applies equally to either assistance condition and cannot establish an outcome for either arm.

The CLI JSON route holds the supplied arrays in memory. No authentic corpus memory/runtime estimate has been established. Streaming native preparation and safe serialization custody remain separate unresolved work.

## Source and qualification

The cached [author notebook](https://github.com/GiocomoLab/Sosa_et_al_2024/blob/adf0f9ed3defa22275d92fa0ed996f47008e05b3/notebooks/Fig3_Decoder.md) and [decoder](https://github.com/GiocomoLab/Sosa_et_al_2024/blob/adf0f9ed3defa22275d92fa0ed996f47008e05b3/src/reward_relative/decode.py) match the predecessor hashes. Notebook lines 344–377 define the five model conditions; 388–512 define 100 shuffles and their axes; 843–878 define the Fig. 3b aggregation and two plotted model conditions. Decoder lines 103–150 define cosine arithmetic, ten ordered test folds and stochastic training selection. Exact pins and source scope are in `provenance.json`.

The current source commit is not proven to be the historical publication revision. Exact published scores, authentic complete native input and fold receipts, safe loading, original preprocessing/cell selection, qualified author inference, full companion results and a justified improvement decision remain unresolved. Generated controls demonstrate software behavior only. No training, inference, candidate trial, scientific improvement, or current-SOTA result is claimed.
