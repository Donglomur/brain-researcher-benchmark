# Complete-support Helsinki EEG evaluator

This source implements the registered `NEURAL-EXP-005` probability endpoint and
causal packet interface. It preserves all **79 recordings**, all three expert
annotation streams, and every primary timestamp in the selected
`helsinki_full_timestamp_quality_flags_v1` protocol. Windows, folds, experts,
quality strata and access modes remain parts of one task.

It accepts an independently normalized, source-admitted recording description.
It does not parse EDF files, establish authentic annotation alignment, train a
seizure detector, run an agent, or establish scientific readiness. The
[registered task](../../task.json) remains authoritative. Use the corrected
`annotations_2017_A_fixed.csv` source alignment; the presence of three arrays
alone does not verify that correction or their original expert identities.

## Scientific endpoint

For each recording with `N` samples at native rate `num/den` Hz, duration is the
exact rational value `T = N * den / num`. Sample zero must align with annotation
second zero in this normalized interface. A nonzero or unverified alignment
cannot be silently rounded away.

The primary cases are every integer `k = 29, ..., floor(T)-1`. At decision time
`k+1`, the participant receives exactly `[k-29, k+1)` and returns a probability
for the final interval `[k, k+1)`. This is recognition using the final second's
signal, not prediction before that second. The first 29 complete seconds and
any final fractional second are outside this fixed prediction support and remain
accounted for. No quality flag removes a case. A required recording with no
primary case holds the complete outcome; it cannot be omitted from the infant
macro average or assigned an invented zero loss.

Native indices are selected with exact integer arithmetic:

```text
start = ceil((k - 29) * num / den)
stop  = ceil((k + 1) * num / den)       # exclusive
samples = recording[start:stop]
```

The right endpoint is excluded. Fractional sampling rates can produce different
sample counts in successive 30-second windows. Relative timestamps retain the
native phase: sample index `n` has tick numerator
`n * den - (k - 29) * num`, with denominator `num`. The first selected sample is
not necessarily at relative time zero. No padding, interpolation, resampling,
amplitude normalization or channel substitution is performed by this interface.

For expert labels `a1, a2, a3`, the target is `q=(a1+a2+a3)/3` and primary loss is
`(p-q)^2`. Loss is averaged over every primary timestamp within each infant,
then equally over all 79 infants. Pooling timestamps across infants changes the
estimand and is not the primary score. Expert-specific Brier losses and their
mean are reported separately:

```text
mean expert Brier = soft-vote Brier + q * (1 - q)
```

Expert disagreement is therefore retained, not treated as an extra set of
independent cases or unique clinical truth. Event sensitivity and false
positives/hour are not implemented as substitutes for the primary endpoint;
the registered event-matching and operating-point definitions remain pending.

## Trusted normalized inputs

`protocol.py` exports `ContractError`, the exact pinned 18-channel `MONTAGE`,
`PROTOCOL`, `fold_map`, `prepare_reference`, `Reference`, and `packet`.
`evaluate.py` exports `evaluate` and `compare`. Only standard-library Python is
required by these source interfaces. There is no command-line campaign launcher.

The description uses schema `helsinki-complete-support-description-v1` and has
these exact fields:

| Field | Meaning |
| --- | --- |
| `schema` | Exactly `helsinki-complete-support-description-v1`. |
| `assessment_id` | Owner-selected assessment identifier. |
| `protocol_id` | The selected quality-flag protocol identity. |
| `source_version` | Exactly `zenodo:4940267-v4`. |
| `fold_seed` | Published, frozen seed for infant-grouped fold assignment. |
| `representation_sha256` | Independently supplied representation identity. |
| `detector_sha256` | Frozen original-input quality-detector identity. |
| `source_admission_sha256` | Identity of external source-admission evidence. |
| `montage` | Exactly `list(MONTAGE)`, in its fixed order. |
| `development_by_fold` | Mapping from string fold numbers to selected development recording IDs. |
| `recordings` | The complete 79-recording roster described below. |

SHA-256 fields use 64 lowercase hexadecimal characters. A validly shaped hash
is not evidence that the original source, montage, annotations or detector has
been scientifically admitted. These identities must come from the trusted
owner and remain bound to the reviewed inputs.

Each recording has exactly `recording_id`, `eeg_sha256`, `sample_rate`,
`sample_count`, `sample_zero_annotation_second`, `units`, `labels`, and
`quality_flags`. `sample_rate` contains positive coprime integer `num` and `den`;
`sample_count` is a positive integer; `sample_zero_annotation_second` is exactly zero.
Units are explicitly one of `uV`, `mV`, `V`, or `digital_count`. The source does
not convert an admitted digital count into a physical voltage by assumption.
Native calibration and units remain part of authentic source admission.

`labels` contains three complete binary arrays, one value per complete original
second. `quality_flags` is a Boolean array with that same temporal extent.
The trusted callback `read_samples(recording_id, start, stop)` returns exactly
the selected sample-major rows as a list or tuple, with each row a list or tuple
of all 18 finite numeric channel values in the
admitted order. It supplies the authentic normalized signal; it is not a route
for a participant to request arbitrary recordings or future samples. ECG is
excluded from this primary EEG montage.

Whole recordings remain together in five hash-assigned folds. Development
recordings are selected within each training fold and must not overlap its held
recordings. Authentic biological-identity verification, seizure-support audit,
and train-only fitting/calibration remain prerequisites for an empirical
comparison. Source IDs must not be recycled to put the same infant in both
training and held groups.

This implementation's prospective split rule sorts recordings by SHA-256 of
the canonical JSON array `[fold_seed, recording_id]` (ties by recording ID), then
assigns successive recordings to folds `index % 5`. Fold sizes are therefore
16, 16, 16, 16 and 15. This is a versioned construction choice, not a claim that
an authentic seizure-support audit has selected these partitions. Freeze the
seed, identity roster and development membership before examining outcomes.

## Reference and packet API

Create the reference only in the trusted preparation environment:

```python
from protocol import prepare_reference, packet

# descriptor and read_samples come from the trusted normalization pipeline.
# case_key is an evaluator-held bytes value with at least 32 bytes.
reference = prepare_reference(descriptor, read_samples, case_key)

# recording_id and k are trusted-side selectors, not participant metadata.
public_packet = packet(reference, recording_id, k, read_samples)
```

`prepare_reference` freezes the full support, input hashes and key commitment.
`Reference(document, case_key)` validates those complete bindings when restoring
a prepared reference. Keep the reference document and key evaluator-private.
The HMAC key must never be distributed with participant source or packets.
Neither an opaque ID nor a hash proves that the dataset was absent from model
pretraining.

A packet exposes the selected 18-channel window, relative native timing, units,
montage, the original 30 one-second quality flags, and immutable assessment/input
bindings. It excludes expert labels, original infant IDs, source filenames,
clinical reports and absolute recording offsets. The input hash is checked
against the frozen reference; changed source values cannot silently become a
new version of the same admitted case.

Every arm and control must receive identical original quality flags. The flag
for the final second is distinct from earlier context flags. Noise or
amplitude-only controls must not recompute flags from their replacement signal.
The three descriptive strata are: no flagged context; flagged earlier context
with an unflagged final second; and flagged final second. Empty strata are
undefined, and no stratum replaces the full primary result. These flags are
input-derived quality indicators, not verified pause intervals or missingness.

This packet constructor freezes the source-signal representation. It does not
construct noise, amplitude-only, phase or ECG control inputs. Those require
their own admitted representation procedure while preserving the same support,
labels and original flags; they cannot pass a changed signal under an existing
source packet hash. Valid constant probabilities can be scored as software
controls, but are not presented as a qualified trained/calibrated comparator.

The caller must create a fresh participant context/process for every case and
restrict it to that packet and immutable training-derived artifacts. This pure
source interface does not enforce process isolation, model-memory deletion,
network restrictions or callback custody. Overlapping windows do not authorize
cross-case state or access to subsequent signal.

## Complete prediction and comparison interfaces

`reference.case_rows()` yields the complete ordered prediction bindings:
`case_id`, `assessment_id`, `protocol_id`, `representation_sha256`, `fold`, and
`input_sha256`. Each submitted row retains those exact fields and appends one
finite numeric `probability` in `[0,1]`.

This full binding stream belongs to the assessor/coordinator. Do not expose it
as participant metadata: its order and grouping carry information about the
complete evaluation support. The participant receives only the current causal
packet and returns its binding with its probability. The coordinator retains
the full ordered stream for scoring. Score reports also contain private
recording IDs and must stay outside participant access.

Pass the complete ordered prediction stream to `evaluate(reference, rows)`.
Missing, extra, duplicate, reordered, malformed, nonfinite or wrong-binding
rows prevent a full primary score. They cannot be dropped to reduce the
scoring denominator. The result includes the infant-macro soft-vote Brier,
three expert-specific scores and their mean, disagreement, per-infant and
quality-stratum results, and excluded-time accounting.

`compare(left, right)` compares complete evaluation results with the same frozen
reference and returns paired per-infant and infant-macro `right - left` loss
differences. A negative value favors the right arm. Pass the original reports
from `evaluate`, rather than hand-assembled summaries. It does not manufacture a confidence interval,
significance claim, SOTA result or independently sampled population. Grouped
uncertainty and empirical reference competence require separate evidence.

## Remaining qualification

The official [montage source](https://github.com/ktapani/Neonatal_Seizure_Detection/blob/1a59e4b414f28aba52e61c3360fdc324199071b4/Neonatal_Seizure_Detection_Algorithm/neonatal_sez_det/read_data_montage.m)
was authenticated at the task's pinned revision, with SHA-256
`57196447f307d35e981b57fab8179dd9bddde9be02badaad5db654e4adfef4dd`;
this does not establish native EDF/header parity for all 79 recordings. Full
corrected annotation joins, source rights/provenance, original calibration,
quality-detector validity, all authentic source extents and train-only baseline
membership still require verification. A public pretrained model is not assumed
uncontaminated merely because its code is available.

This package supplies no competent fitted seizure comparator and no authentic
model result. Generated controls can verify causal bounds, complete-support
accounting, bindings and arithmetic; they do not validate the original dataset
or clinical interpretation. All annotations are public, so held-infant local
folds do not establish contamination-resistant model evaluation. No task count,
readiness state or scientific qualification changes with this source delivery.

## Generated source tests

From the repository root:

```sh
python3 -B -m unittest discover -s benchmarks/neural/NEURAL-EXP-005/implementations/complete-support-evaluator -p 'test_*.py' -v
```

The standard-library fixtures invent all 79 recordings. Independent rational
expectations check rater disagreement, unequal recording durations and quality
strata. Packet tests enumerate native sample times independently, retain
fractional clock phase, check label noninterference, and reject modified inputs,
future samples, incomplete bindings, held/development overlap and malformed
comparison reports. These are implementation controls, not neuroscience results.
