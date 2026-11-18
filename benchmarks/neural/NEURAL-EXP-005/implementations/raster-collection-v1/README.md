# Complete Helsinki raster-response collection

This operator component closes the gap between a single raster `Session.finish()`
and the existing complete-support evaluator. It freezes the exact existing
case-binding sequence, admits only the next case, and withholds a complete
prediction export until every frozen case has committed its final probability.
It does not open labels, compute scores, choose a new cohort or change the
infant-macro soft-vote Brier endpoint.

The existing `Reference` remains the schedule authority. `freeze_reference`
projects only its `record_ids()`, `case_rows()` and `reference_sha256`; it never
calls `record()` or copies its private document/labels. All 79 infants and all
five existing folds remain required, with every supplied original case in its
original order. Case-count and hash checks alone cannot establish authentic
biological identities or completeness of an arbitrary caller-supplied object.
Use the trusted, source-admitted existing `Reference`, not a participant-created
roster. The accepted original source has 400,534 primary cases; that authentic
complete-source execution has not been performed for this component.

## Trusted operator sequence

```python
from collector import Collector, freeze_reference, admit_collection, protocol

schedule = freeze_reference(reference)
schedule_pin = protocol.digest(schedule)  # Protect before participant responses.
owner = Collector(schedule, expected_schedule_sha256=schedule_pin)

for public_packet in original_ordered_packet_iterator:
    session = owner.open_case(public_packet)
    # Separate admitted host delivers only this session's typed action responses.
    # It obtains one final probability through session.act({"action": "answer", ...}).
    owner.commit_current()  # Calls accepted Session.finish(); no row injection API.

complete = owner.finish()  # Refuses missing cases or an uncommitted current case.
collection_pin = protocol.digest(complete)  # Protect before opening scoring labels.

rows = admit_collection(
    schedule, complete,
    expected_schedule_sha256=schedule_pin,
    expected_collection_sha256=collection_pin,
)
if complete["source_reference_sha256"] != reference.reference_sha256:
    raise ValueError("wrong scoring reference")
# In a separately authorized scoring step:
# report = existing_evaluate(reference, rows)
```

Keep both expected digests in operator-controlled storage. Accepting an edited
document together with its newly recomputed digest does not preserve a prior
commitment. Readback checks both external commitments, exact per-row identity,
full original order, finite probabilities and internal row integrity. The row
format is exactly the existing scorer's case/assessment/protocol/representation/
fold/input binding plus `probability`; no new loss function is introduced.

`open_case` validates the packet through the byte-pinned accepted raster
`Session`. A second case cannot open while a current case remains uncommitted.
Wrong, repeated, skipped or reordered packets fail against the next frozen
binding. `commit_current` accepts no caller-authored row and refuses before a
final probability exists. The returned commit receipt contains only the current
case ID, input hash and row hash; it exposes no future cases, labels, correctness
or scores. `finish()` exports once, only after complete collection. Returned
documents and later caller mutations cannot change the owned snapshots.

The full schedule, collector, raw packets, returned session objects and complete
export are operator-only. Participants receive only the existing session's
allowlisted PNG/metadata/answer messages through an external transport. In
particular, giving them Python object or process access would expose private
state. Sequential collection does not erase a participant's memory or enforce
fresh processes: those original per-case requirements remain external.

## Validation and remaining qualifications

Ten new generated controls cover exact projection without gold access, all
79 invented infants with 80 cases, the unchanged scorer's known `1/144` loss,
partial/active/unanswered refusal, wrong and repeated packets, current-only
receipts, snapshot ownership, malformed schedules, final export immutability,
tampering despite self-rehashed rows, and invalid probabilities/extra labels.
These are engineering fixtures, not neuroscience results. The original raster
viewer controls are unchanged and were not replayed.

From the repository root:

```sh
python3 -B -m unittest discover -s benchmarks/neural/NEURAL-EXP-005/implementations/raster-collection-v1 -p 'test_*.py' -v
```

The shared integrator must register this new component and its focused CI
command. The four accepted phase-one files remain unchanged. No task, readiness
classification, central authority, biological split or other access condition is
modified by this private construction.

This is an in-memory collection adapter, not a participant process/stream
harness or crash-durable artifact writer. Full authentic-corpus memory/runtime,
protected persistence, source custody/preparation, quality-detector calibration,
training-only comparator competence, identical required controls, PNG readability
and fresh-process/OS isolation are not established. Complete rows and consistent
hashes do not prove that an external model viewed images. No authentic EEG,
model trial, trained detector, scientific comparison, native-understanding or
SOTA result is claimed.
