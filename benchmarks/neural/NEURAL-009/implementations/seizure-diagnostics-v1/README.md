# Seizure-event diagnostic supplement

This operator component adds the raw-event miss and timing diagnostics deferred by
[seizure-events-v1](../seizure-events-v1/README.md). It also identifies where the
pinned scorer obtains processed-event credit. The complete 686-record, 23-person
primary evaluation is returned unchanged under `primary_evaluation`; the original
source, prospective scoring policy, task and understanding contract are preserved.

It does not prepare authentic EEG, fit a detector or deliver a participant mode.
Direct observation, typed viewer, tool-assisted investigation and frozen-program
access remain unqualified. Software controls cannot establish clinical usefulness,
causal execution, prompt seizure detection or scientific benchmark readiness.

## Diagnostic definitions

Every interval is half-open on the existing 10 Hz grid. Record boundaries reset
all analysis; no between-record gaps contribute exposure or permit matching.

**Raw annotations.** Each original normalized reference interval is retained,
without source merge or split. For every interval, the output reports whether a
threshold-positive bin intersects it, the first such bin, and its decision
endpoint. Bin `i` covers `[i/10, (i+1)/10)` and its score may use EEG through
`(i+1)/10` seconds. Thus a positive bin beginning exactly at the annotated onset
has a decision delay of **0.1 seconds**, not zero. This is grid availability,
with no processing or hardware latency modeled. The delay is conditional on
in-event positivity and is null for misses; misses remain in the event denominator.

A prediction already active before onset receives an explicit flag and a signed
positive-run start offset. It is not reported as a new alarm. Adjacent positive
segments are joined for this transition check. A continuous all-positive detector
therefore has many already-active alarms even when its conditional delay is short.
The output does not perform one-to-one alarm matching, infer seizure prediction,
or impute a delay for a missed event. Nearby seizures can share one positive run.

**Processed score credit.** The exact, hash-verified upstream `timescoring`
implementation first merges/splits both reference and prediction as in v1. The
supplement reads those processed intervals and independently counts their overlap
with each source-extended reference window. The source's strict `minOverlap +
1e-6` rule is preserved; the credited total must agree with the upstream total.
Credit is partitioned into:

- `within_processed_reference`: processed prediction intersects the processed
  reference interval, which may itself include merged inter-seizure gaps.
- `early_only`, `late_only`, or `early_and_late_only`: all credited processed
  support lies in tolerance extensions, with no processed in-interval support.
- `not_credited`: the source overlap rule is not met.

The output separately counts raw prediction overlapping raw seizure support
inside each processed reference interval. `credited_without_raw_seizure_overlap`
therefore exposes both tolerance credit and credit involving merged gaps; the
location field shows which kind of processed support exists. Another field
records whether the source overlap rule would fail without prediction merging.
None of these flags rejects a valid submission or changes the primary score.

**Aggregation.** All recording rows are required and aliases are inherited from
the v1 admission validator (`chb21` belongs to `chb01`). Raw misses, already-active
alarms, processed credit counts and conditional delay summaries are reported per
person and pooled. The supplemental raw-event overlap fraction also receives an
equal-person macro; any person without raw events makes that macro null, with the
undefined person explicitly retained. Conditional delay summaries always expose
their detected-event denominator. There is no latency macro or confidence interval.
All-negative and all-positive controls receive the same diagnostics and exposure.

## Operator interface

The Python entrypoints are `diagnose_record(reference, prediction, observed_ticks)`
and `evaluate(admission, policy, candidate, expected_policy_sha256=..., limits=...)`.
The former is a record-local audit helper and assumes operator-controlled memory
budgets, as does the predecessor's record helper. The complete evaluator enforces
all predecessor cohort, policy, tick, channel, recipe, coverage and segment checks.

The command below uses the same JSON artifacts as the predecessor. Choose an
existing Python environment containing NumPy; no dependency is installed here.

```sh
python3 -B diagnostics.py \
  --admission /operator/admission.json \
  --candidate /operator/candidate.json \
  --policy /operator/policy.json \
  --support /operator/support.json \
  --limits /operator/limits.json \
  --expected-policy-sha256 FROZEN_CANONICAL_POLICY_SHA256 \
  --max-input-bytes 20000000 \
  --max-output-bytes 40000000 \
  --output /operator/fresh-diagnostics.json
```

Those byte budgets are examples, not measured full-task output bounds. Resource
limits must be frozen by the operator for the actual admitted cohort. The CLI
reuses the predecessor's reviewed bounded regular-file JSON loader, duplicate-key
and nonfinite-value rejection, fresh private output writer, and public candidate
preflight before opening references. Results contain targets and are operator-only;
never expose this output as participant feedback. The supplement performs an
additional scorer pass for each arm. It is not a resource-isolating runner.

## Source and qualification

The component reuses the exact v1 source closure (manifest SHA-256
`6e97b56bd2043184f53e9e9be13317ce312bae10ee213dfdd54edaeb5b32fb62`)
and [timescoring commit 426f8d2](https://github.com/esl-epfl/timescoring/tree/426f8d2b77974641dc9db71884e0812b249ba93b).
The pinned [record roster](https://physionet.org/files/chbmit/1.0.0/RECORDS) remains
686 recordings and 23 biological people. Existing exact source bytes and prior
review evidence were reused; no new source download, EEG/annotation preparation,
private target read, candidate trial or model inference occurred for this change.

The local `test_diagnostics.py` contains generated endpoint and whole-roster
controls. Its values are deliberately invented. Test execution receipts and exact
file hashes are recorded separately in the wave handoff. Remaining scientific gaps
include authentic waveform/annotation normalization, competent EEG and nuisance
comparators, physical causal/target isolation, paired uncertainty, and independently
frozen clinical alarm-matching or timeliness criteria if such claims are desired.
