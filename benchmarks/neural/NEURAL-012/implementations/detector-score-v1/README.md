# Independent frozen-detector scoring

This component makes the existing NEURAL-012 scientific endpoint executable
without an analyst reconstruction submission. The preserved `score.py` computes
`grade(packet, submission)` before `detector_outcomes(packet)`, so a missing or
malformed report prevents it from emitting detector performance. This separate
entry point computes only the latter outcome. It checks eight exact preserved
source hashes, then executes their unchanged validation and arithmetic.

From the repository root:

```sh
python3 -I -B benchmarks/neural/NEURAL-012/implementations/detector-score-v1/score_detector.py \
  --input /operator/private/analysis.json \
  --input-sha256 EXACT_SHA256 \
  --output /operator/private/detector_outcomes.json
```

The input is the existing **post-prediction** analysis packet from the trusted
operator, including its selected clock profile, frozen arm events, annotations
and phase evidence. It is not a candidate-facing input. Output is bound to the
input bytes and scorer-source identity. Existing outputs cannot be overwritten.
The CLI makes no network requests and needs only Python's standard library.

The operator-private result retains every person's arm metrics, all target
record-by-arm false-alarm intervals (including empty lists), and total observed
seconds. These mandatory companions come from the unchanged reconstruction
function; the original primary and secondary projections remain unchanged.
The wrapper repeats deterministic reconstruction on the already parsed packet
to retrieve these fields. It does not reopen inputs or execute a detector.

The original endpoint is preserved: all 686 CHB and 41 Siena records, 23 and 14
disjoint people, four arms, 96 logical jobs and 192 declared phases. Counts pool
within each person before equal-person averaging. Siena arm differences remain
paired; source-to-target shifts remain unpaired. Sensitivity and false alarms
per 24 observed hours remain mandatory. The wrapper also requires the original
198 CHB and 47 Siena raw annotation entries, as required by the preserved
`annotation_binding.py` and `combine_panels.py` preparation paths. These are counts
of source entries before the fixed merge/split event policy, whose canonical event
counts can differ. Reconstruction accuracy is a separate
outcome and is absent from this result.

The software controls construct a full synthetic 727-record packet with 198 CHB
and 47 Siena raw event entries. Hand-calculated unequal event/person support distinguishes
person pooling from recording averages and pooled-cohort F1. Controls also
exercise missing records/arms/phases, person overlap, noncanonical events,
changed input/source hashes, duplicate JSON keys, and output preservation.
Lost or added annotation entries are rejected even when all records and people
remain. Separate controls preserve raw counts while changing event identity or
merging canonical events, making the count check's limits explicit.
They do not read authentic EEG, private solver targets or historical predictions.
Run `test_score_detector.py` through the shared reviewed test pool during this
revision; ordinary serial execution is sufficient outside that coordinated wave.

This is **packet recalculation**, not new source authentication or execution
admission. A digest authenticates selected bytes, not their scientific origin. Matching the
two raw annotation totals likewise does not verify event identity, placement or
original label content; count-preserving alterations remain outside this guard.
The inherited serialized evidence validator checks consistency and cannot prove
that its declared phases occurred. Generated controls intentionally demonstrate
that distinction. All existing qualification gates remain open: complete source
and montage support, Siena clock/common-reference adjudication, protected target
custody, native isolation and actual full detector execution are still required.
No model result, direct/viewer understanding result or transfer improvement is
established. The canonical task, history and registered runtime remain unchanged.

Source scope: repository base `c620e64d39fda59e049c40b3bc7d6d328d1534f9`, current
task SHA-256 `7d8f9bdab6de4e8ae37fbb1628323a18e4887f65fb8e20e2095defe5d0b781e7`,
understanding contract SHA-256
`e5911c73a598779a2bc9613bec767bab07cb52596d7407caf13f364645866438`.
Exact executable dependencies are pinned in `score_detector.py`; no source
payload was downloaded for this component. The inherited event policy cites
[timescoring revision 426f8d2](https://github.com/esl-epfl/timescoring/tree/426f8d2b77974641dc9db71884e0812b249ba93b).
The scorer retains that implementation's integral-second input restriction,
fixed merge/split/tolerance policy and descriptive uncertainty limits.
