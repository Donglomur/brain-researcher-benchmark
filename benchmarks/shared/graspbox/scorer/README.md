# GraspBox full-cohort probability scorer

This is the authored scorer for the existing GraspBox full-cohort offline scalp-EEG grip-recognition endpoint. It contributes zero new benchmark IDs and zero scientific qualifications. There are no authentic prediction results, model fits, native reads, downloads, installed dependencies, model/API calls or official decoding-parity claims. The official MATLAB sources implement descriptive analyses and do not define a held-person decoding score.

Dataset provenance: Lomele et al., [Scientific Data article](https://www.nature.com/articles/s41597-026-07242-y), [official raw release](https://osf.io/rsv4z/) and [official code/processed release](https://osf.io/g6yta/). This independent authored component includes no article text, official MATLAB implementation, native data or labels. The official nodes declare CC0, while the article has its separate license; dependencies and data provenance still require their own admission. The full native reader/census and operation evidence remain outside this portable component. This component does not read MAT files or reinterpret native labels, channels, units or events.

## Evaluation and input trust

The command-line entrypoint consumes one evaluator-owned private JSON manifest and one candidate JSONL prediction file. The root/evaluator selects the expected manifest SHA-256 independently of the candidate. The CLI hashes the complete bounded manifest bytes before parsing. The private manifest includes labels and original row joins and must never be sent to a participant or model, published, or mounted writable in a candidate environment. A digest supplied by a candidate would not establish this trust boundary.

The stdlib Python API `evaluate(manifest, header, records, manifest_sha256)` performs structural/scientific-contract checks on already-decoded objects. Its digest argument is a caller assertion; it cannot authenticate bytes that it did not receive. Use the CLI for file admission, or authenticate the original bytes separately before calling the API. No code path reads native scientific arrays or executes candidate code. The CLI reads the separately admitted private manifest and frozen predictions.

The manifest's semantic-review hashes and `verified` gates are trusted evaluator declarations. The scorer validates their syntax and consistency; it does not establish that a referenced census/review exists or that its assertions are true. A separately reviewed converter must join all 14 accepted census sidecars to the reviewed class/channel/time mappings, emit the complete private manifest, preserve row provenance, and independently authenticate the references before authentic use. The current accepted census itself reports `scientific_admission: false`; it cannot directly satisfy these semantic gates. Fixtures use `evidence_kind: invented_control` and invented hashes and cannot qualify native admission.

Similarly, fold receipts are structural provenance declarations. Declaring network disabled, unique isolation/conversation namespaces and no cross-fold state does not prove process isolation, an LLM conversation reset, undeclared preprocessing absence, or absence of public-data contamination. A later protected runner must enforce and observe these facts, freeze all learned artifacts and protocol choices before query/label access, supply complete receipts, and independently authenticate logs and assets. This scorer is not that runner. A candidate can lie in a receipt; receipt validation alone cannot detect that.

## Exact manifest schema

All objects reject unknown or missing fields. Identifiers contain 1–96 ASCII letters, digits, underscores or hyphens. SHA-256 values are exactly 64 lowercase hexadecimal characters. The top-level fields are:

| Field | Required value |
|---|---|
| `schema` | `graspbox_scoring_manifest_v1` |
| `class_order` | `["PG","UG","WH"]` |
| `evidence_kind` | `invented_control` or `admitted_native_census` |
| `protocol_sha256` | Evaluator-frozen authored protocol digest |
| `admission` | `census_sha256`, `semantic_review_sha256`, and `gates` |
| `participants` | Exactly 14 records |
| `trials` | Exactly 1,558 records |
| `folds` | Exactly 14 outer folds, each with 13 inner folds |

`admission.gates` has exactly `native_census`, `scalp_eog_reference_map`, `physical_units`, `performed_label_mapping`, `frame_alignment`, `session_repeat_grouping`, `opaque_query_mapping`, `evaluator_label_isolation`, each set to the string `verified`. Ambiguous performed/instructed semantics must block this version; a weaker released-label claim needs an explicitly reviewed contract revision.

Each participant has `participant_id`, integer `cohort_index` 1–14, and `source_sha256`. Cohort indices bind the accepted paper roster and are private; the 14 source hashes must be distinct and must later join the exact 14 acquired originals. Each trial has `query_id`, `participant_id`, `block_id`, `session_id`, `source_row_one_based`, `label` and Boolean `event_complete`. Query IDs have syntax `q_` followed by 32 hexadecimal characters. Actual IDs must be generated independently of labels, people and row order; syntax checking cannot prove randomization. Invented fixture IDs are deterministic and are not a deidentification recipe.

Block and non-null session IDs are evaluator-assigned globally unique opaque identifiers. A repeated native block code in different people therefore receives different opaque block IDs. Block IDs may not cross people or sessions; sessions may not cross people. `session_id: null` means the release provides no separate session subdivision. Original row indices must be the complete, unique one-based range for that person's accepted source; labels are the reviewed native mapping to PG/UG/WH, not an assumed numeric order. Source-file identity is inherited from the participant record. No block is forced to contain 30 trials.

Per-person `(blocks, all trials, event-complete trials)` must be:

```
1:(5,148,148)  2:(4,120,104)  3:(4,120,100)  4:(3,90,88)
5:(3,90,80)    6:(3,90,83)    7:(3,90,45)    8:(4,120,110)
9:(4,120,109) 10:(4,120,120) 11:(4,120,115) 12:(4,120,120)
13:(4,120,120) 14:(3,90,38)
```

The total is 14 people, 52 blocks, 1,558 trials, 1,380 event-complete trials and 178 retained incomplete-event trials. Every person must have all three labels. The manifest cannot replace primary rows with the event-complete subset. A real mismatch is a release/protocol discrepancy requiring review, not permission to shrink the cohort. Person 2's missing rest and person 14's handedness do not create exclusions; the scorer needs neither resting arrays nor demographic fields.

Each outer fold contains `fold_id`, `held_out_participant_id`, `training_participant_ids`, `test_query_ids`, and `inner_folds`. The 13 training IDs are exactly all other participants; test IDs are exactly every query for the held person. Each inner fold contains `held_out_participant_id` and `training_participant_ids`, with one of the 13 outer-training people held out and the other 12 training. All 13 inner held-out people appear once. Training trial support is **derived from the participant roster**, never independently supplied or selected; every block, session and row of a person moves together. The manifest checks the complete outer test partition and rejects wrong person/block/session/trial membership. Repeated appearance of the same person in training across outer folds is intended LOPO; persistence across their isolated executions is prohibited.

## Exact prediction schema

One UTF-8 JSONL header followed by exactly 1,558 records; at most 2 MiB per manifest/prediction file and 1 MiB per JSONL line. No blank lines, NaN/Infinity, overflowed JSON floats, duplicate JSON keys, executable formats or final-operand symlinks/devices/FIFOs. Nested JSON deeper than 32 is rejected. Final input byte identity is checked during each read; trusted parent-path custody and protection from concurrent writers remain external requirements.

The header has exactly `schema: graspbox_predictions_v1`, `class_order: [PG,UG,WH]`, `manifest_sha256`, `protocol_sha256`, `fold_receipts`. Both digests must match the selected manifest/protocol. Each prediction record has exactly `query_id`, `fold_id`, `probabilities`, `prediction`. The query ID set must equal the full manifest, with no duplicates. Its fold must be the query participant's held-out fold. A probability vector has exactly three numeric, non-Boolean, finite entries in [0,1] and sum within 1e-6 of one. Vectors are never renormalized. `prediction` must equal argmax, resolving all ties in PG,UG,WH order. A wrongly declared class order is rejected; a candidate that falsely labels permuted numbers cannot be detected from numbers alone and is scored as submitted in the declared order.

Every fold receipt has exactly `fold_id`, `held_out_participant_id`, `training_participant_ids`, `isolation_id`, `conversation_id`, `input_modalities`, `network_enabled`, `cross_fold_state_reused`, `query_updates`, `fit_records`. All 14 folds appear once with exact held/training people. Isolation and conversation identifiers are distinct across folds. Modalities are exactly `["scalp_EEG"]`; the three Boolean state/network flags must be false. Both interfaces must start from isolated fold preparation and no query-derived updates; case-reset implementation remains a future runner obligation.

Each fit record has `fit_id`, `stage` (`inner` or `outer`), `inner_held_out_participant_id` (null for outer), `training_participant_ids`, `artifact_id`, `artifact_sha256`, `input_modalities`. Inner fit people are exactly the 12 permitted people, outer fit people the 13. Fit IDs are unique within the fold; artifact IDs are globally unique. Hashes may coincide for independently produced identical bytes; this does not authorize artifact reuse. All learned normalization, feature selection, CSP, covariance reference, classifiers, calibration and early-stopping decisions must be represented by complete external provenance, and all their receipts must respect these support sets. Fixed uniform prediction legitimately has no fits. At most 2,048 fit records per fold are admitted, subject also to the total byte/line limits. These limits accommodate the contract's 1,134 primary-panel fits but do not select or validate any fit.

## Metrics and independent controls

For person h and class c, recall is correct(h,c)/count(h,c). Primary BA is `(1/14) sum_h [(1/3) sum_c recall(h,c)]`. Secondary log loss is `(1/14) sum_h [-(1/n_h) sum_i ln(max(p_i,true,1e-15))]`, after input validity. Thus a valid zero probability receives finite loss; an invalid vector never receives a repaired score. Pooled accuracy is labeled diagnostic only. Per-person and participant-macro recalls, true-by-predicted confusion matrices, class counts and complete/incomplete-event counts are retained.

Authored calibration diagnostics are multiclass Brier **sum across three classes** averaged within person then across people, and ECE with ten equal-width maximum-probability bins. Bins are [0,.1), …, [.9,1]; empty bins have null confidence/accuracy and contribute zero. ECE is computed within each person before macro averaging. These choices are explicit additions to the contract's unspecified calibration diagnostics, not official MATLAB parity or a new primary metric. Counts for the event subset are diagnostics; no subset-only result replaces primary scoring.

Optional comparison fully validates both submissions against the same manifest/protocol. It reports all 14 first-minus-second BA and log-loss differences, means, medians, and a fixed-seed (`20261115`) 10,000-resample paired participant-cluster percentile interval. Each draw resamples 14 people; BA and loss use the same draws. Quantiles use linear interpolation at `(n-1)*p`. Positive BA and negative log-loss differences favor the first submission. It resamples frozen predictions, not trials, and excludes retraining and method-selection uncertainty. Python's stdlib RNG implementation/version is part of reproducibility. No inferential claim or multiplicity correction is implied.

`test_graspbox_score.py` creates invented full-cohort metadata/probabilities only. Analytic checks include uniform BA=1/3, loss=ln(3), Brier=2/3; perfect BA=1/loss=Brier=ECE=0; cyclic wrong BA=0/loss=15ln(10)/Brier=2/ECE=1. A first-person-only perfect result has BA=1/14 versus pooled 148/1558. A single correct first-person PG trial has BA=1/42 versus pooled 1/1558. A separate log-loss oracle distinguishes person weighting from trial weighting. Constant paired improvements give point-mass bootstrap intervals. Adversarial schema, coverage, nonfinite, wrong-class/tie, split, event-retention, source-row, block/session, fit-leakage, receipt and actual CLI/file-admission controls exercise meaningful failures. These are software controls, not biological observations or LLM evaluations.

## Operation

Run the tests from this directory with `python3 -B test_graspbox_score.py`. For a separately authorized, fully admitted evaluation:

```
python3 -B graspbox_score.py --manifest /path/to/admitted-manifest.json \
  --manifest-sha256 EVALUATOR_SELECTED_SHA256 \
  --predictions /path/to/frozen-predictions.jsonl
```

Add `--compare-predictions /path/to/second-frozen-predictions.jsonl` for the paired comparison. Standard output is the complete JSON result; invalid input produces only an invalid-run object and exit status 2. The code creates no output files. Caller-controlled redirection/retention must preserve diagnostics privately. A malformed argparse invocation is an invocation failure rather than a scored run.

The current authored implementation passes 55 invented control test methods. A UTF-8-only regression covers Python JSON byte auto-detection of other encodings. Controls create no authentic scientific observation or qualified native result. Tests need only Python standard-library modules and may run locally without downloads.

## Remaining scientific work

Complete native input admission and census remain prerequisites; this portable scorer does not select or perform acquisition or a native census. After one separately selected full intake and independent review: resolve channel/EOG/reference/unit mapping, performed/instructed labels and repeats, timing and session provenance; build/review an EEG-only candidate converter and authenticated manifest; implement protected fold/case execution; implement and validate the three competent reference families under all 1,092 inner and 42 outer primary-panel fits; then perform complete authentic scoring and independent scientific review. Peripheral/nuisance/window/permutation comparisons and contamination limits remain as the original contract requires. No score threshold or source commit completes these gates.
