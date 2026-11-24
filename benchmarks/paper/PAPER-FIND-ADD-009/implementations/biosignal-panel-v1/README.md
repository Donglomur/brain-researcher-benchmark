# Complete biosignal control assessment

The source's Extended Data Fig. 5c uses 240 simultaneous-recording trials, five modalities and ten-fold cross-validation. The existing day195/session-holdout evaluator cannot represent this control experiment. This operator-side component scores every declared held-out prediction for all five modalities, the author baseline, and the two information conditions. It retains all 3,600 trial/modality/system scores and 40-band values, fold and session summaries, and trial-paired differences. It calls the existing feature evaluator's `score_trial` directly, without changing its acoustic mathematics.

This is **secondary-panel assessment only**. It does not establish authentic trial/fold membership, reproduce the primary 956-trial result, supply the separate 30-trial listener analysis, run the original rank-sum comparison, or admit either scientific outcome. An improvement assessment still requires the canonical whole panel, author replay qualification, effect and uncertainty rules, and enforced matched access and budgets. Sample and population SD are both explicitly labelled; neither is silently declared to match the unresolved historical SD convention.

From the repository root:

```sh
python3 -B -m unittest discover -s benchmarks/paper/PAPER-FIND-ADD-009/implementations/biosignal-panel-v1/tests -v
python3 -B benchmarks/paper/PAPER-FIND-ADD-009/implementations/biosignal-panel-v1/assess_panel.py \
  --plan /operator/original-control-plan.json \
  --reference /operator/control-mel-reference.json \
  --prediction /operator/three-system-predictions.json \
  --output /operator/new-control-assessment.json
```

Python standard library only. No network, neural model, waveform frontend or speech model is executed. Outputs cannot replace an input or an existing output. Input-byte SHA-256 receipts and the imported feature evaluator hash identify the exact supplied artifacts. They do not verify authentic provenance. `--max-dtw-cells` retains the existing per-trial DTW limit.

## Operator input contract

The plan contains `schema_version: "voice-biosignal-panel/v1"`, `task_id: "PAPER-FIND-ADD-009"`, `data_release: "441124"`, `source_panel: "extended_data_5c_240"`, and `original_support_sha256`, the externally verified original membership/provenance artifact's content hash. A supplied digest is a declaration, not an authenticity check. Original source trial identities, fold identities and model artifacts must be recovered and admitted independently before authentic use; this package includes none.

- `source_input_features` maps `neural: 512`, `microphone: 40`, `stethoscope: 40`, `imu: 240`, and `combined_biosignals: 320`; `source_feature_bin_ms` is 10 and `source_context_ms` is 600. These describe the original source input route, not the 40-band scoring output. `vocabulary` lists all 50 distinct source word identities. Tokens, targets and operator vocabulary declarations must never become neural inference input.
- `acoustic_profile` uses the existing evaluator contract: `mel_power_db`, 40 bands, 16,000 Hz, 50 ms Hann window, its existing DTW policy, explicit `hop_ms` of 10 or 40, and frozen `mel_filterbank_id`, `db_reference_id` and `silence_policy_id`. The historical hop interpretation and feature/mask equivalence remain unresolved.
- `trials` enumerates 240 unique `trial_id` and `original_trial_id` values, each with `participant_id: "T15"`, `session_id` and `sentence_id`. Repeated sentence text is not confused with a repeated physical trial.
- `folds` enumerates ten distinct `fold_id` records with nonempty `test_trial_ids` and `training_trial_ids`. Test memberships partition the full cohort; each training set is its held set's complement. Equal fold sizes and session holdout are not assumed. The original shared fold assignment is an external prerequisite for this matched assessment, not a fact established by trial counts or by this software.
- `systems` has exactly `author_baseline`, `paper_data` and `paper_data_author_code`. Each supplies a common `vocoder_sha256`, a matched `external_speech_resources` list of `resource_id`/`sha256` records (possibly empty), and all 50 `models`. Each model specifies `signal`, `fold_id`, `decoder_sha256`, the full fold `training_trial_ids`, and explicit `selection_trial_ids` (possibly empty) contained within that training set. This audits declared training/selection support; it cannot detect undeclared exposure or prove a decoder was fit as declared. Internal validation allocation and model recipes remain external provenance.

The shared reference is a 240-row array of `trial_id`, `mel_db` and boolean `speech_mask`, with the existing evaluator's feature shape and finite-value requirements. Prediction JSON maps the same three system names to arrays of 1,200 rows each: the same feature fields plus `signal`, `fold_id` and `decoder_sha256`. A model may predict a trial only from its declared held-out fold. Duplicate, absent, unknown and wrong-fold predictions fail before scoring. Undefined correlations fail the entire assessment; no trial is dropped.

For each modality, `descriptive_paired_contrasts` reports both arm-minus-author deltas and code-arm-minus-paper-data deltas. All are calculated using the same reference, trial identities, folds and acoustic profile. They are descriptive correlation differences, not separate reproduction/improvement decisions or a statistical substitute for the source rank-sum procedure. Per-session and per-fold records preserve dependence rather than treating frames, Mel bands or overlapping training folds as independent replications.

The output is operator assessment material and includes granular performance records. Reference features, source text and target masks are never included in output. This script is not an isolation sandbox; protected evaluation material and the operator command must not be exposed to participant code.

Source: [primary manuscript, Methods “Decoding non-invasive biosignals” and Extended Data Fig. 5](https://pmc.ncbi.nlm.nih.gov/articles/PMC12369848/). The paper explicitly states the 240 trials, 50-word vocabulary, five modality feature counts, ten-fold procedure, 10 ms bins and 600 ms context. It does not disclose the original fold membership in that passage. No scientific contract or historical provenance file is changed by this component.
