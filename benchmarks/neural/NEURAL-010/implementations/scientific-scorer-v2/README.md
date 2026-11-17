# Scientific endpoint scorer for NEURAL-010

This task-local operator component computes the registered signed EEG-minus-matched-no-EEG person-macro event F1 from four complete frozen detector streams. It preserves the historical reconstruction implementation unchanged. It does not execute a detector or evaluate a participant's direct interpretation.

The scorer requires the exact CHB-MIT 1.0.0 `RECORDS` bytes (686 files), checks a one-to-one protected source-to-opaque-ID mapping, pools chb01/chb21 as one biological person, and refuses missing or substituted records. All 23 people must have reference events for the complete primary, as required by the current task. It pools counts within each person before calculating metrics, then averages paired person differences equally. It retains four absolute arm tables, all three candidate-minus-comparator contrasts, montage strata, undefined-person identities and exact false-alarm localization. A zero or negative primary is a valid result.

The preserved task event policy is loaded only after checking SHA256 `462afe5bb002df77567bda53c232607b86552a658f99515c283774635956599c`. It uses the existing 10 Hz quantization, gap <90 s merging, >300 s splitting, and 30 s/60 s tolerances. It does not switch to one-to-one event matching. False alarms are normalized to 24 observed hours; interfile gaps supply no exposure. Standard errors remain descriptive, and single-person montage support cannot identify a causal montage effect.

## Protected operator interface

All inputs below are operator-side files, including the source mapping and annotations. None is a participant observation packet. `evaluate()` accepts frozen bytes plus a target loader; the loader is called only after every arm's hash, complete support, identity and event canonicalization passes. The CLI reads bounded ordinary local files and prints the scientific report to stdout. Direct it to an external evidence location, never public Git.

The independent operator supplies an `--operator-pins` JSON object mapping `panel`, `targets`, `candidate`, `matched_no_eeg`, `signal_reference`, and `montage_only` to exact SHA256s. The candidate must not choose this file or the comparator bytes. The trusted launcher is responsible for selecting it and independently authenticating its source. Hash agreement establishes only the supplied bytes, not when fitting occurred, comparator competence, model isolation, or legitimate training-label access.

Call `scorer.py` with `--records`, `--panel`, `--targets`, `--operator-pins`, `--candidate`, `--matched-no-eeg`, `--signal-reference`, and `--montage-only`. All flags point to local operator files. The standard-library implementation needs no installation.

File schemas (all reject extra/duplicate fields):

- Panel: `{"schema":"neural010-scientific-panel-v2","records":[...]}`. Each record has `recording_id` and `patient_id` (24 lowercase hex), `source_record` (exact publisher path), `montage_id` (64 lowercase hex), and integral positive `duration_seconds`.
- Each stream: `{"schema":"neural010-scientific-events-v2","panel_sha256":"...","arm":"candidate","records":[...]}` with its exact arm name. Each row has `recording_id` and `events`, a sorted list of disjoint canonical half-open `[start_seconds,end_seconds]` intervals. An empty list is a complete no-alarm prediction, not a missing row.
- Targets: `{"schema":"neural010-scientific-targets-v2","panel_sha256":"...","records":[...]}` with the same row fields, integral-second source annotations, and all records including explicit negatives. Missing annotation evidence cannot be converted into an empty list by this component; upstream reconciliation remains required.

The upstream preparer must derive observed duration and montage identity from authenticated complete source records, retain duplicate derivations, and supply reconciled target intervals. This scorer consumes those admitted facts; it cannot infer them from predictions. The new schema is an operator scoring interface, not a replacement task or delivered access mode. Integration with the existing source preparer and independent fit/closure provenance remains outstanding.

## Controls and source lineage

`test_scorer.py` creates all numerical observations and predictions synthetically. It reads only the pinned public filename roster through `NEURAL010_RECORDS_FILE`; it uses no EEG, real annotation values, historical private answers, or model outputs. Tests cover person-vs-record weighting, alias grouping, negative contrasts, zero-event single-person montage support, observed-hour units, exact source support, comparator tampering, event boundaries and target-last rejection. Run only under the approved shared lightweight pool during this revision.

- [CHB-MIT 1.0.0](https://physionet.org/content/chbmit/1.0.0/) and [RECORDS](https://physionet.org/files/chbmit/1.0.0/RECORDS), SHA256 `72b640d6a3fef4b40de255933d1403823d1655c56f93d69761105a653798fc08`. Attribution: Guttag, J. (2010), DOI 10.13026/C2K01R. Public roster bytes are supplied externally and not copied here.
- [Official epilepsy2bids converter](https://github.com/esl-epfl/epilepsy2bids/blob/d3fb17526b8a483e292ae9ba2e51b02d5f9128ff/src/epilepsy2bids/bids/chbmit/convert2bids.py), revision `d3fb17526b8a483e292ae9ba2e51b02d5f9128ff`: chb21 alias mapping to person01/session02, already verified in preserved source audits.
- [Pinned timescoring source](https://github.com/esl-epfl/timescoring/blob/426f8d2b77974641dc9db71884e0812b249ba93b/src/timescoring/scoring.py), revision `426f8d2b77974641dc9db71884e0812b249ba93b`: source lineage for the task's existing event policy. This revision reuses the local policy; it does not claim new upstream numerical parity.

Qualification remains limited to this scoring component and its executed generated controls. No authentic corpus preparation, detector fitting, reference competence, held-person scientific performance, direct/viewer condition, or complete benchmark qualification is established here.
