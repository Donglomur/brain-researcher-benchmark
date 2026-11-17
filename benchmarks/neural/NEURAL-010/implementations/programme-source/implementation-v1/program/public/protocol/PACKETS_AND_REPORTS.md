# Exact historical and matched-diagnostic interfaces — V2

This design explicitly preserves the original **three-arm** `analysis_core.validate_packet`, `reconstruct` and `grade` interface. A four-arm record would fail that original schema. The successor therefore requires a new protected release/projection adapter; it cannot pass the four-arm corpus to the old `prepare_analysis.py` or represent that preparer's three-method seal as the new all-stream barrier.

All JSON below uses strict duplicate-key/nonfinite rejection. Canonical packet bytes are UTF-8 JSON with sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(',',':'), followed by one newline, matching the existing `io_contract.encoded` convention. Descriptors contain exact positive integer `bytes` and lowercase64hex `sha256`; a permitted namespace path is bound separately wherever needed. Actual raw-byte hashes, not reserialization of a parsed replacement, bind supplied artifacts.

## 1. Master seal and original prediction ABI

One independently admitted complete four-stream seal binds: original NEURAL009-format full panel bytes; independent prepared assessment-target descriptor; all92 held-person outputs and their merged all686-record streams; fitted source/config/scaler/model/threshold/support/seed lineage; the fixed event-source identity; exact runtime/access/resource/closure evidence and all9706 logical fit dispositions. Its stream names are exactly `candidate`, `signal_reference`, `montage_only`, `matched_no_eeg`. No assay or target read is authorized by a subset seal.

The original panel, private target and merged prediction carrier retain their original **NEURAL-009** wire task ID and schema_version1, because the pinned vendor `scorer.py` and `io_contract.py` require it. NEURAL-010 is the enclosing investigation task. Do not substitute NEURAL-010 inside that unchanged wire ABI. Every prediction carrier has exactly schema_version/task_id/records; each record has recording_id/scores/events; all686 records, complete integral-second score arrays and independently recomputed canonical events must pass the original `predictions` validator before the assessment reader is invoked. Original labels then pass the original `targets` validator against the same panel SHA, using the newly captured private body after the global barrier.

The master seal's canonical byte descriptor and its separately trusted original-observer/release authority are distinct. Its SHA supplies legacy identity fields, but the outer adapter must authenticate the actual complete master body and authority; a string hash alone cannot assert that four streams or closures existed.

## 2. Deterministic unchanged historical packet H

After full four-stream admission and the sole authorized assessment capture, the adapter creates H with **exactly**:

- `schema_version`: strict integer1;
- `task_id`: `NEURAL-010`;
- `phase`: `post_prediction_analysis`;
- `sealed_inputs`: exactly six lowercase64hex values, keyed `panel`, `targets`, `candidate`, `signal_reference`, `montage_only`, `phase1_seal`;
- `records`: all686 rows sorted by opaque recording_id.

The first five sealed-input values are SHA256 of the exact original panel/assessment/three historical merged prediction bytes. `phase1_seal` is SHA256 of the **complete four-stream master seal**, not a fabricated legacy three-stream substitute. The outer release adapter additionally enforces that all six values agree with the authenticated master. The unchanged original H validator validates format, not that outer authority; both layers are mandatory.

Each H row has exactly the existing seven keys: recording_id, patient_id, montage_id, duration_seconds, signal, annotations, arms. Copy identities/duration/signal descriptor from the admitted original panel. Signal has exactly path/bytes/sha256; path remains `signals/<recording_id>.h5`. Derive montage_id from the separately authenticated exact channel-label multiset, not from the model vocabulary. `annotations` is that record's admitted original assessment intervals. `arms` has exactly candidate/signal_reference/montage_only with their already validated canonical event lists. Preserve all original type/support/bounds/null/event semantics. There is no fourth arm or new seal key inside H.

H is canonically serialized once. Its exact bytes and SHA are shared across **all12** analytical executions and both views. The waveform-withheld condition changes mount/tool authority through the separate view manifest; it does not strip H.signal, change H bytes or give the original grader a different input identity. Those signal descriptors remain as provenance while actual sample access is denied. Public original schema validation does not imply that absent-withheld signals were physically supplied.

## 3. Separate matched packet M

M has exactly `schema_version`=1, `task_id`=`NEURAL-010`, `phase`=`post_prediction_matched_diagnostic`, `historical_packet`, `four_stream_seal`, `matched_prediction`, and `records`. The three descriptor fields bind the exact H bytes, complete master-seal bytes and original all686 matched_no_eeg merged prediction bytes. `records` is exactly686 sorted rows, each with only `recording_id` and `events`, equal to the matched predictions already validated at the global barrier. No second copy of labels, durations, person IDs or montage IDs can diverge: these are obtained only by joining M to its exact H. Duplicate/missing/extra IDs or a different H/master hash refuse the whole context.

The matched diagnostic reconstructs per-person and per-person×montage metrics from H annotations/support and M matched events using the unchanged event arithmetic. Candidate comparison values are from the exact candidate arm in H; no newly supplied candidate table replaces them. Thus historical and matched comparisons refer to the same recordings, targets and candidate stream. M is serialized once and is identical across all12 contexts/views. Four-stream report support is established by outer joins, not by weakening the original H validator to accept arbitrary extra arms.

## 4. Execution envelope and both submissions

The immutable common analysis envelope identifies schema `neural010-four-stream-analysis-v1`, task NEURAL-010, full four-stream seal descriptor, exact H and M descriptors, original event/source identity, full686/23 support and the realized sealed detector descriptions. It has no private expected report. A per-context view manifest separately binds this envelope, mode, replication, fixed/adaptive author identity, actual allowed tool/runtime/source and either `full_waveform` or `waveform_withheld` authority. The full view binds all686 projection bodies; the withheld view has no sample/cache/model accessor. No view manifest may change H/M or detector outputs.

Each final whole-context submission has one exact context/source/envelope/view/mode/replication binding and two subordinate submissions:

- `historical_submission` is the original schema1 object with exactly schema_version, task_id, input_sha256 and report. Its input_sha256 is H's exact SHA. After full outer admission, call the unchanged original `analysis_core.grade(H,H_sha,historical_submission)`; its returned metric remains maximum_scaled_reconstruction_error, lower better, and its1e-8 software tolerance remains the historical primary.
- `matched_submission` has exactly schema_version=1, task_id=NEURAL-010, historical_packet_sha256=H_sha, input_sha256=M_sha and report. Its separately reviewed reconstruction uses H/M and the same `numeric_error` arithmetic conventions. Its error/tolerance are a named diagnostic, not a replacement or aggregate primary.

The matched report has exactly `patients`, `candidate_minus_matched_no_eeg`, `montages`, `false_alarm_localization`, `recordings`, `biological_patients`, `observed_seconds`, `interfile_gaps_included`, `artifact_class_or_causal_attribution_supported`. The final two flags are False, counts are686/23 and observed_seconds is the same H sum. For each opaque person, `patients[person]` has one `matched_no_eeg` entry containing the unchanged event.summarize fields. The comparison has the three original endpoint names and unchanged paired-summary n/mean/SE/positive/negative/zero fields. Every montage has its complete `patients` matched table, same comparison, biological_patients and single_patient_support flag, with membership from H. Localization contains one sorted row per recording, exactly recording_id/arm=`matched_no_eeg`/intervals. All empty lists/nulls remain.

The historical report contains2,058 localization rows; the diagnostic contains686. They are required together and never counted as two independent benchmarks. Every context's historical and diagnostic errors are reported separately. A whole-study protected grading invocation validates all12 contexts and exact subordinate schemas/lineage before calculating any expected report or exposing any reward; it then performs12 unchanged historical grade-function evaluations and12 matched diagnostic reconstructions. This is one complete grading phase with24 subordinate numerical sections, not24 independent experiments. No grade or interpretation score is fed back into a still-open author/investigator context.

## 5. Data-free versus realized descriptions

The three earlier data-free authoring episodes receive protocol/family/grid equations, original public event source and the future H/M/envelope/view/submission schema. They do not receive an instantiated H/M, authentic rows or IDs, realized montage vocabulary/counts, selected configurations/thresholds, models/statistics, detector outputs or metrics. Any example used in a future author interface must be explicitly invented and independently authorized; none is created by this zero-fixture design phase.

The six fixed-program executions receive the realized envelope and selected view only after their sources are irrevocably frozen. The six adaptive episodes receive the same realized descriptions/data for their selected view, with the distinct allowed adaptive timing of model/tool use. Stage-specific access is essential: saying 'both modes receive the same descriptions' cannot license data-dependent selected settings during data-free authoring.
