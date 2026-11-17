# Complete held-person seizure-detection interface

This operator library connects genuine **event predictions** to NEURAL-010's
existing scientific scorer. A participant submits seizure intervals for every
held-person recording. It does not receive the annotation-bearing reconstruction
table and is not scored on copying that table.

The construction preserves all **686 recordings and 23 biological people**,
including the chb01/chb21 identity merge. It supplies an explicit projection from
the original preparer's metadata, complete outer-fold query and submission
schemas, a complete candidate freeze, and a target-last join to the unchanged
[scientific scorer](../scientific-scorer-v2/README.md). Existing preparation,
reference fitting and historical reconstruction code are unchanged.

**This is source construction, not a runnable qualified EEG study.** It does not
implement an EEG reader, image renderer, model provider or hostile-code sandbox.
The registered disposition and all access-mode qualification remain unchanged.
No authentic corpus, candidate detector or trained reference was executed here.

## Operator sequence

1. Independently authenticate the original preparation and its source/process
   lineage. Supply its public `panel.json`, target-free `metadata.json`, protected
   `SOURCE_PROVENANCE.json`, and the exact public CHB-MIT `RECORDS` roster to
   `project_preparation()`, with operator-selected byte/hash descriptors. This
   function has **no assessment or signal loader**. Its three returned byte
   documents are participant support, the protected scientific panel, and private
   projection bindings. Keep the latter two operator-side.
2. Freeze the participant method, fitting/tuning policy, input access, resource
   budget and reporting policy before evaluation. Create a separate outer context
   for each biological person. For a trained programme, `project_training_view()`
   accepts exactly the original final-fold `TRAIN.json`: all 22 other people,
   with their permitted training annotations. It rejects any held-person record.
   It does not choose hyperparameters or validate the actual training execution.
3. After freezing each fold's model or context state, call `make_query()` with
   its operator-owned method/state hashes and one declared mode. Deliver the
   resulting complete unlabelled query through a separately qualified provider.
   Private bindings resolve opaque signal handles to authenticated target-free
   projections; never mount the source provenance, assessment, another person's
   training context, or a parent directory containing them.
4. Collect one submission bound to each exact query hash. `freeze_candidate()`
   requires all 23 contexts and every recording exactly once. An explicit empty
   event list means no detections; a missing row or failed context is not empty.
   Persist both returned byte documents and all original query/submission bytes
   under the trusted launcher's custody before permitting target access.
5. An independent operator supplies the three reference streams and their
   preselected descriptors. Call `grade_frozen()` with these operands, the frozen
   candidate, original preparation panel/assessment pins, and a protected
   `assessment_loader`. It first revalidates every query, submission, candidate
   byte and complete reference stream. Only then does it call the loader once,
   authenticate the original assessment and deterministically convert its legacy
   carrier to the scorer's schema. The unchanged scorer computes all four arms,
   paired contrasts, montage strata and false-alarm locations.

Revalidation establishes byte and arithmetic consistency. A hash, receipt or
claimed method state cannot demonstrate when fitting occurred, what a participant
could access, actual execution closure or comparator competence. Those require
independent runtime and scientific evidence. This library does not upgrade such
claims based on caller-provided booleans.

## Participant observations and outputs

The common record projection contains only:

```json
{
  "recording_id": "24 lowercase hexadecimal characters",
  "patient_id": "24 lowercase hexadecimal characters",
  "duration_seconds": 3600,
  "montage_id": "64 lowercase hexadecimal characters",
  "channel_labels": ["FP1-F7", "F7-T7"],
  "signal_handle": "signal:<recording_id>"
}
```

Channel order and duplicates are preserved. No source filename, source EDF hash,
annotation, source header or annotation provenance is in this projection. A
support document binds all records to the scientific panel and original
preparation panel by SHA256. The private projection binding retains the precise
prepared signal byte identity and opaque relative path for the trusted provider;
it is not participant material. Authentic source conversion must retain calibrated
channel units and complete observed signal coverage. This component does not
inspect waveform bytes or prove provider delivery.

`make_query()` adds `schema="neural010-detection-query-v1"`, support hash,
`held_person`, `mode`, `method_sha256`, `fold_state_sha256`, and exactly that
person's complete record list. One campaign uses one method and one mode:

- `typed_viewer`: the provider may return only declared EEG renders and typed
  navigation results, then accept event marks. Signal handles do not authorize
  raw-array or filesystem access. This library declares the shared identity and
  output interface; it supplies no viewer implementation or provider proof.
- `frozen_program`: a separately isolated programme may process the permitted
  target-free projections using its frozen fitting/adaptation recipe. Legitimate
  22-person training annotations stay in that outer context only.

A zero-shot viewer and a programme trained on 22 people's labels have different
information budgets. Shared recording IDs and scoring do not establish a matched
tool-use effect. An information-matched comparison needs its own frozen delivery
and demonstration policy. There is no no-tools direct-observation implementation
in this package.

Every participant submission has exactly this shape:

```json
{
  "schema": "neural010-detection-submission-v1",
  "query_sha256": "the exact operator query hash",
  "records": [
    {"recording_id": "<opaque ID>", "events": [[100.0, 110.0]]},
    {"recording_id": "<another opaque ID>", "events": []}
  ]
}
```

The example shows shape only; real submissions must include all recordings for
their held person. Raw intervals must be finite, sorted, disjoint and within each
record's observed duration. The preserved event policy then quantizes boundaries
at 10 Hz, merges gaps under 90 seconds, and splits events over 300 seconds. Its
30-second start and 60-second end tolerances and non-one-to-one overlap matching
remain unchanged. Both access modes use this same policy. Interfile gaps add no
exposure; false alarms are normalized to 24 observed hours.

Inputs are bounded byte documents with exact fields, duplicate-key rejection and
strict numeric types. Campaign query bytes and submission bytes each have a
16 MiB aggregate limit; at most 200,000 raw events are admitted before any
canonicalization. The scorer's existing 200,000 canonical-event bound remains.
These interface bounds are not a substitute for execution CPU, RAM or wall-time
limits enforced by a runtime supervisor.

## Scientific comparison and remaining gaps

The unchanged scorer reports all absolute candidate, matched-no-EEG,
montage-only and fixed-signal metrics. Its signed candidate-minus-no-EEG mean is
computed over 23 people, not recordings or folders; zero and negative contrasts
are valid. It retains descriptive standard errors and single-person montage
flags. Overlapping training folds do not create independent replication, and
montage associations do not establish causal montage effects.

The independently supplied no-EEG stream must genuinely match the candidate's
learner family, allowed metadata, tuning and fitting rules before the difference
can be interpreted as an **EEG ablation effect**. An arbitrary new detector
compared with the historical fixed no-EEG learner supports only the declared
detector-versus-baseline comparison until that matching is established. The
candidate cannot submit, select or weaken reference streams through the
participant schema. A reference pin establishes byte identity, not independent
ownership, legitimate fitting or empirical competence.

Remaining work includes authentic complete preparation, independently frozen and
qualified references, actual nested fitting and threshold lineage, separate
outer-context custody, concrete viewer/programme providers, frozen inference
rules and scientific evaluation. The existing nine-setting inner-person reference
schedule is not executed or replaced here. It excludes both outer and inner
people; the new final-training projection does not expose an outer person's
labels to that selection. A participant must not carry labels or mutable state
from one outer context into another.

## Construction controls

`test_interface.py` reads only the exact public filename roster in
`fixtures/CHBMIT_RECORDS.txt` (or an explicit `NEURAL010_RECORDS_FILE` override);
all numerical observations, labels and predictions are generated. The fixture is
a byte-identical copy of the public [CHB-MIT 1.0.0 RECORDS](https://physionet.org/files/chbmit/1.0.0/RECORDS)
metadata, SHA256 `72b640d6a3fef4b40de255933d1403823d1655c56f93d69761105a653798fc08`.
It contains filenames only, without EEG or annotations, and is never a participant
query operand. Attribution: Guttag, J. (2010), DOI 10.13026/C2K01R.
Controls exercise a fixed threshold detector on generated observations,
complete preparation projection, both event-output modes, training exclusion,
candidate/reference freeze failures and the actual unchanged scientific scorer.
These are software controls, not seizure-detection performance results.

Run the module with Python 3.11+ through the project's authorized lightweight
test pool. It has no package installation or scientific data dependency. The
scorer and event policy remain external sibling source dependencies, checked at
their exact preserved hashes. Source provenance and the executed control history
are recorded in `SOURCE_MANIFEST.json` and `CONSTRUCTION_EVIDENCE.json`.
