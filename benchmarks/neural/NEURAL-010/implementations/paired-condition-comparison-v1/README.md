# NEURAL-010 paired access-condition comparison

This operator source compares a complete zero-training visual-viewer campaign
with a complete zero-training frozen-program campaign on the same 686 CHB-MIT
recordings and 23 biological people. It adds joint admission and paired outcomes
to the existing event campaign; it does not create another benchmark task.

Both participant campaigns must already have finished. The comparison runs no
participant, model, renderer, signal reader, fitting procedure or detector. It
opens no neural recording. External campaign declarations and generated control
transcripts do not establish real execution, isolation, renderer fidelity,
clinical validity, native neural understanding or scientific superiority.

## What is compared

The selected conditions are `typed_viewer` and `frozen_program`, with `training`
equal to `none` in both. Both retain their own method and tool-policy identities.
Learning, tuning, selected resource limits and bounded observation opportunities
must match. A program trained on the other 22 people is refused by this route.

The source requires the same preparation selection, complete observation-support
bytes, original panel and assessment, event policy, three independently selected
reference streams and their run/closure identities. Both evaluation selections
and their candidate-specific provenance are retained. They are not required to
have identical whole documents: method and tool policy naturally differ.
All 46 participant contexts and their exchange namespaces must be disjoint.

The pixel viewer and numerical program also differ in representation. Their
signed outcome difference is therefore a **descriptive comparison of access
conditions**, not an isolated causal effect of tools. Fixed display gain,
saturation, pixel resolution, allowed observations, checkpoint exposure and actual
resource enforcement remain relevant limitations. This source supplies no new
static no-tools display condition or case-adaptive tool-assisted participant.

## Joint protected-target barrier

The preserved nine-file `vendor/event-campaign-v1` runtime and its original source
manifest are byte-identical to the existing implementation. Its detector
interface, scientific scorer and event matching/canonicalization kernels are
unchanged. The new entry admits this fixed closure; it accepts no arbitrary
runtime module, participant callback, alternate evaluator or target-loader plugin.

For each side, the unchanged campaign scorer replays the selected campaign
request, preparation, all 23 launch/state-freeze/closure records, all 686 submitted
recordings, complete frozen candidate and independent reference provenance. A
source-controlled I/O adapter intercepts the scorer's sole assessment-capture
call. Reaching exactly that boundary admits the side; returning early, reaching
a different boundary, or failing any prior check does not. The adapter does not
open the assessment during either admission.

Only after both admissions and the cross-condition checks succeed does the
comparison physically capture the common protected assessment once. The two
original score operations then replay against their immutable captured metadata
and that same assessment body. Capture, journal, directory-name and stat-only
operations must occur in exactly the recorded order with identical arguments;
there is no filesystem fallback for an uncaptured operand. Request and authority
containers are snapshotted before I/O, and returned name lists cannot mutate the
retained snapshot. The original kernels may still reopen their fixed,
hash-checked source files; this is explicitly distinct from operand replay.

Physical process/namespace isolation remains an external requirement. A trusted
operator must keep the comparison, preparation, assessment and prior campaign
evidence outside participant access. A hash or a source-replayed custody receipt
does not prove that a declared service actually enforced its claims.

## Results and missing support

The output preserves both original complete results, including their absolute
candidate/reference values, false-alarm locations and all montage strata. For
each metric it adds every paired person's left value, right value and signed
left-minus-right difference:

- Event F1: higher is better.
- Event sensitivity: higher is better.
- False alarms per 24 observed hours: lower is better; interfile gaps are excluded.

The complete originals remain in `left/RESULT.json` and `right/RESULT.json`,
bound by exact `original_result_pins` in the comparison. Its small
`original_result_summaries` are labeled summaries, not replacements for those
files. The comparison does not duplicate both potentially large original bodies
inside the original writer's single 16-MiB output envelope.

The complete-support mean gives equal weight to people and is available only
when every expected pair is defined. Undefined values retain their person slot
and an explicit reason. No failed or undefined person is silently dropped, no
zero is imputed, and no pooled score or ranking is created. Montage comparisons
retain their own complete person support and flag single-person strata. Paired
people and montage rows are not new independent replications, and overlapping
training or source exposure cannot be resolved by this arithmetic.

## Operator invocation

Use the isolated standard-library entry with independently selected source,
request and authority byte counts and SHA-256 identities:

```text
python3 -I -S -B entry.py
  --source-bytes N --source-sha256 SHA
  --request /operator/pair-request.json --request-bytes N --request-sha256 SHA
  --authority /operator/pair-authority.json --authority-bytes N --authority-sha256 SHA
  --read-root /operator/preparation --read-root /operator/completed-campaigns
  --read-root /operator/selected-references
  --output /operator/fresh-comparison
  --reservation-root /operator/existing-invocation-ledger
```

Line breaks illustrate one command. Each selected side supplies the original
event-score request and authority descriptors, not a participant-authored summary
table. `paired_conditions._selection` defines the exact paired schema. Its
`source` is the new package manifest; the two original score requests still bind
the preserved event-campaign manifest. The separate paired authority binds both
sides, the common protected assessment and the descriptive interpretation.

The invocation ledger and output directory are create-only. A repeated request
cannot silently reset its entry reservation. The output contains the selected
request/authority, whole-operation reservation, `left/RESULT.json`,
`right/RESULT.json` and final `COMPARISON.json`. An interrupted or failed operation
may retain a prefix and a best-effort `FAILURE.json`; it is not a completed
comparison and is never converted into empty detections or a score.

One whole-comparison budget and original start time cover both admissions,
replays and writes. Per-arm read/write allowances also persist across both
passes. All failed attempts remain charged. Captured metadata has a separate
bounded retention allowance; unused transient reservation is released to its
actual retained extent, never refunded as performed I/O or work. Logical byte
counters are not OS memory/disk quotas, measured physical I/O or runtime
qualification. Source-kernel reopen costs retain the upstream conservative
reservations. A caller must provide adequate storage, runtime and independent
custody; none is manufactured by this package.

The `compare` Python API is a trusted source composition interface. Invoke it
through the admitted entry/module loader to establish the complete new source
identity. It constructs the fixed upstream filesystem I/O itself and exposes no
backend injection parameter.

## Generated engineering controls

The tests construct complete artificial preparation metadata and campaign
evidence. Any participants, custody responses, intervals, source descriptors or
reference outcomes in those controls are explicitly generated doubles. The
public `CHBMIT_RECORDS.txt` fixture is only the published filename roster, not
EEG, annotations or patient outcomes. No scientific dependency, neural-data
loader, model service or authentic signal is needed by these controls.

The controls exercise the unchanged source campaign/scorer plus the actual new
joint route, including complete support, signed differences, single target
capture, failure before target access, condition mismatches and immutable replay.
They establish software behavior only. Test results and resource observations
must be reported from an actual selected run; authored tests or a source manifest
are not evidence that those tests passed.
