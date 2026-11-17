# NEURAL-011 initial evaluator v1

This package implements complete selected-patient Siena event scoring, source
annotation normalization, a causal EEG line-length comparator and a timing-only
comparator. It is executable construction source. **Scientific qualification is
unknown; authentic detector performance, submission readiness and protected
evaluation are not established.** Generated checks are not Siena signal results.
The canonical task and historical admission statements remain unchanged.

## Exact source and scientific scope

The immutable contract is `task.json`, SHA256
`044340155db14895d22a711e2a892261d0377603714125502e911dd7181fd0ea`.
The dataset is [Siena Scalp EEG 1.0.0](https://physionet.org/content/siena-scalp-eeg/1.0.0/),
associated with [the dataset paper](https://doi.org/10.3390/pr8070846).
Publisher metadata establish 41 EDF recordings from 14 PN patients and 47
annotated seizures. The implementation freezes the 41 recording identifiers and
publisher EDF hashes in `source_inventory.json`; it does not contain EDF data.
All files for every selected PN patient are required in one partition. This
prevents selecting only favorable files or seizure windows and preserves each
complete recording's background in the false-alarm denominator.

Annotation semantics follow epilepsy2bids commit
`d3fb17526b8a483e292ae9ba2e51b02d5f9128ff`,
[`load_annotations/siena.py`](https://github.com/esl-epfl/epilepsy2bids/blob/d3fb17526b8a483e292ae9ba2e51b02d5f9128ff/src/epilepsy2bids/load_annotations/siena.py).
The parser handles midnight wrap, PN01's two-event block, the PN00-3 corrected
end clock `18.29.29`, PN10-7.8.9's spacing error, PN12's repeated file blocks,
and PN01/PN06/PN11 filename aliases. PN10-2 supplies alternative end clocks and
PN10-3 supplies clinical and electrical onset clocks: the pinned greedy parser
selects the **final** timestamp. This implementation follows that behavior and
reports a correction note; it does not resolve the clinical annotation ambiguity.
PN00-1 parses to 1143–1213 s; corrected PN00-3 parses to 765–825 s.
Absent file mentions and incomplete events fail rather than becoming background.
Durations must be supplied from independently verified EDF headers. All parsed
events must lie within those durations. The parser was checked against the pinned
parser for all 41 public metadata entries, recovering the same 47 events; no EEG
samples were read.

## Frozen event estimator

Event scoring follows timescoring commit
`426f8d2b77974641dc9db71884e0812b249ba93b`,
[`scoring.py`](https://github.com/esl-epfl/timescoring/blob/426f8d2b77974641dc9db71884e0812b249ba93b/src/timescoring/scoring.py)
and [`annotations.py`](https://github.com/esl-epfl/timescoring/blob/426f8d2b77974641dc9db71884e0812b249ba93b/src/timescoring/annotations.py).
Adopting its defaults is an explicitly **prospective construction policy**; the
canonical task links this source but did not itself freeze numerical tolerances.
The source-derived defaults are fixed in this implementation, not tuned on tests:

- Threshold complete per-sample scores with `score >= frozen_threshold`.
- Merge reference and predicted events when the gap is strictly less than 90 s.
- Split merged events longer than 300 s into at-most-300 s segments.
- Extend each reference 30 s before and 60 s after, clipped to recording bounds.
- Use 10 Hz masks, Python `round` for mask endpoints, and retain original float
  event endpoints for overlap denominators. A reference is detected when its
  relative overlap exceeds `1e-6` (the native zero-overlap default plus epsilon).
- A predicted segment is a false alarm if it has no overlap with the union of
  **detected** extended references. Matching is deliberately not one-to-one.
  A sub-tick predicted event can have an empty mask yet count as a false alarm,
  matching the pinned source.
- Aggregate TP, FP and processed reference counts across all files of each
  patient. Compute patient F1 as `2 TP / (TP + FP + reference_count)` and take
  the unweighted mean across patients. Sensitivity and false alarms per 24 hours
  are mandatory. False alarms use the entire rounded 10 Hz recording duration,
  including seizure time. Both patient-macro and pooled FA/24h are reported.

When a patient has no reference or predicted events, F1 is `null`; sensitivity
is `null` without references. Macro metrics average defined values and explicitly
list excluded patient IDs. These undefined-value semantics are documented
prospective aggregation choices. The source corpus's metadata contain seizures
in every listed recording; the undefined cases primarily guard malformed future
selections and null controls. Constant finite score vectors remain valid null
controls and are flagged; they never confer scientific admission.

With a supplied comparator, the evaluator computes paired patient F1 differences
and a seeded percentile bootstrap (2,000 draws, seed 0). This is a prospective
descriptive uncertainty policy for public development, resampling patients, not
files or events. Fewer than two jointly defined patients yields an explicit
insufficient-patients result. Missing or unmatched pairs fail or are disclosed.
Paired comparator artifacts must identify the same training manifest and patients.

## Operator inputs and executable path

Run with Python 3 and existing NumPy (engineering checks used Python 3.11 and
NumPy 2.4.6). From `implementations/initial-evaluator-v1/`:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
python3 siena_evaluator.py annotations Seizures-list-PN00.txt PN00/PN00-1.edf 2625 events.json
python3 reference.py fit train-private.json line-length.json --signals train-eeg.npz
python3 reference.py predict test-public.json line-length-scores.npz --signals test-eeg.npz --artifact line-length.json
python3 reference.py fit train-private.json timing-only.json --method timing_only_v1
python3 reference.py predict test-public.json timing-scores.npz --artifact timing-only.json
python3 siena_evaluator.py evaluate test-private.json line-length-scores.npz line-length.json report.json --comparator-predictions timing-scores.npz --comparator-frozen timing-only.json
```

Manifests have exactly `schema_version: 1`, `task_id: "NEURAL-011"`, `role`
(`train` or `test`), `patients` (unique selected source PN IDs), and `recordings`.
Each recording has exactly these fields:

```json
{
  "recording_id": "PN01/PN01-1.edf",
  "patient_id": "PN01",
  "sample_rate": 512,
  "n_samples": "operator must supply the actual integer from the EDF header",
  "source_sha256": "16e59f91fd3133b36c3ee9d5f2b63563b6128b906078843326b6d87d341a8e7d",
  "channels": ["FP1", "FP2"],
  "reference_events": [[10218, 10272], [46353, 46427]]
}
```

The deliberately nonnumeric `n_samples` placeholder makes this documentation
example non-executable until the operator verifies the header. EEG channels in
the example are illustrative, not a selected scientific montage. Training and
private evaluator manifests include `reference_events`; public prediction
manifests must omit it. Unknown fields are rejected, including answer-bearing
metadata such as seizure type, localization and timing labels. The source hash
declaration must match the frozen publisher inventory. This declaration check
does **not** hash or authenticate EDF payloads. Operator packet construction must
verify original EDF bytes, channel identities, sample counts/rates, conversions,
annotation bytes, and allowed-input/privacy separation independently.

NPZ files use full recording IDs as keys. Neural arrays have shape
`(n_samples, len(channels))`, values in microvolts, and only the preselected,
ordered EEG channels. Predictions are finite numeric vectors of length
`n_samples`. NumPy pickle loading is disabled. No resampling or EDF conversion
is silently performed. Any missing/extra recording, duplicate ID, incomplete
sample vector, nonfinite value, source hash mismatch, prohibited/ambiguous
channel, changed channel order or patient split overlap fails. EKG, SPO2, HR,
marker and unlabeled channel `1` are excluded; ambiguous EEG channel mappings
require operator review. The selected common channels must be frozen before
outcomes, and their actual EDF extraction remains a packet gate.

## Prospective comparator recipes

`line_length_v1` computes causal trailing one-second mean absolute differences
per channel. Each channel is normalized by its mean absolute difference across
training samples only, with a declared `1e-12` microvolt scale floor. The
per-sample score is the median across the fixed channel set. This is a transparent
signal-derived benchmark control, not a reproduction of an author detector or a
claim of clinical efficacy. Signal scale, causal window and aggregation are
prospective choices intended to test whether local EEG variation adds information
beyond recording time. Full-recording native resource cost is unmeasured.

`timing_only_v1` uses only training labels and elapsed recording time. It estimates
ictal occupancy in 60 s bins as ictal seconds divided by observed recording
seconds, then applies the frozen curve to new patients. Bins beyond training
exposure score zero. It accepts no neural arrays and receives no held-out labels.
This exposes timing/duration shortcuts; it is not a positive neural reference.

Both methods choose a threshold only on complete training-patient records from
65 pooled-score quantiles plus the smallest finite value above the maximum.
The selection criterion is training patient-macro event F1, with deterministic
ties resolved by lower macro FA/24h, higher sensitivity, then higher threshold.
The method, training manifest hash/patient IDs, channel set, parameters, threshold
rule and source scoring parameters are serialized and SHA256-bound before test
prediction. This digest detects accidental changes; it is not a signature or
proof that an operator honestly withheld labels. External execution isolation
and independent preparation audit remain necessary. The current constructors
fit these two controls; arbitrary external detectors need a separately reviewed
calibration/provenance adapter rather than mislabeling their scores as one of them.
The supported constructor is grouped **within-Siena public development**. The
CHB-training → Siena-confirmation branch is unimplemented: CHB identities/source
inventory and its locked montage/calibration policy have not been supplied.

## Validation, provenance and remaining gates

The package contains 20 generated unittest cases, including 12 independently
derived numerical scorer examples, all-negative/all-positive controls, macro
versus pooled counterexamples, complete inventory/coverage rejection, malformed
scores, channel/patient/label leakage, causal invariance and CLI round trips.
Independent review also compared 509 generated event cases against the exact
pinned scorer, checked 15 additional adversarial/integration cases, and matched
all 41 public annotation entries. Those checks establish source behavior only.
Exact source read hashes and policy boundaries are in `provenance.json`.

The following remain open: authentic EDF/header/payload equality and conversion;
complete patient selection and split freeze; cross-cohort CHB training versus
Siena confirmation policy if that variant is chosen; locked montage, calibration,
access/adaptation recipe and budget; actual signal-derived reference competence;
independent authentic scoring/reference replication; uncertainty/admission rules
frozen before agent outcomes; evaluator privacy/isolation; dataset/code rights
and redistribution review for future payload/native integration. Siena data are
CC BY 4.0 per the publisher. No upstream source code or signals are redistributed
here; epilepsy2bids's precise license was not established in this bounded read.
Clinical composition, medication, hardware and monitoring confounds remain.
The source implementation neither resolves those gates nor changes historical
`runnable`, `research_qualified`, or `submission_ready` declarations.
