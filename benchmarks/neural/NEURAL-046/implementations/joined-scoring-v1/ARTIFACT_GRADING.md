# Paired scoring from committed artifacts

`grade_artifacts.py` supplies an operator file interface to the existing
`score_joined` implementation. It retains the current AUC-response endpoint,
equal-animal weighting, signed contrasts and mandatory independently tuned MEN
sensitivity. It never fits models or substitutes the historical mean-response
targets. Existing source pins and arithmetic remain unchanged.

The complete bundle, manifest, state directory and report are custodian-only.
They must not be mounted into a participant environment: the bundle contains
targets and identity mappings, and the report retains per-trial/animal losses.
This source component supplies neither a participant interface nor a production
sandbox. It is not connected to the canonical dispatcher and does not establish
authentic-data execution, direct neural understanding or benchmark readiness.

## Input and invocation

Prepare one directory containing `manifest.json` and exactly these six named
inputs: `public.json`, `submission.json`, `sensitivity.json`, `binding.json`,
`closure.json`, and `private.json`. Other members are never discovered or read.
The five public-side objects use the existing paired scorer contract. The private
object is the complete prepared target-row list. No authentic roster is supplied
or synthesized by this component.

The manifest has exactly `schema="neural046-joined-artifacts-v1"`, `inputs`, and
`limits`. `inputs` maps the six names without `.json` to objects with exactly
`path`, `bytes`, and lowercase `sha256`; each path must be that name plus `.json`.
`limits` contains positive integer `max_file_bytes`, `max_total_bytes`, and
`max_report_bytes`. Their implementation ceilings are 64 MiB per input/report
and 256 MiB total input. The manifest itself is limited to 64 KiB. These are
rejection bounds, not an empirical resource qualification for a complete task.

With an already-created custodian state directory and absent report path:

```sh
python3 -I -B grade_artifacts.py --bundle /custodian/bundle \
  --state-directory /custodian/grading-state --report /custodian/result.json
```

Source is authenticated against the pinned paired scorer, which checks its
existing shared dependency closure. File reads reject symbolic links, irregular
files, size/hash mismatches, malformed UTF-8/JSON, duplicate members, nonfinite
numbers, escaped invalid Unicode and nonzero floating literals rounded to zero.
Ordinary finite binary64 rounding remains permitted. Input declarations and
total size are checked before any input payload; the five non-target artifacts
are then authenticated and parsed.

## Target access and failed attempts

The paired scorer validates complete primary/sensitivity predictions, operator
identity mapping and closure digests before invoking the target loader. At that
point the adapter exclusively creates and fsyncs a consumption marker, then
opens and authenticates `private.json`. The marker is named by the canonical
manifest digest; JSON whitespace and member-order changes do not create a fresh
attempt. The receipt separately records the exact manifest file hash.

The custodian must retain the same state directory for this precommitted
manifest. A new directory or materially changed manifest is a distinct operator
action, not blocked by filesystem isolation here. A hash and three claimed
closure booleans do not prove process termination, source provenance, permitted
training or absence of prior target exposure; those remain external obligations.

Any failure after consumption retains that marker, including invalid private
metadata, target hash failure, numerical scoring failure, report-size rejection
or output-write failure. There is no selective retry or partial-result output
under the same manifest/state pair. Earlier validation failures do not open
targets or create consumption state. The final report is exclusively created
only after complete paired scoring; pre-existing reports are never overwritten.
An interrupted report write may leave a partial file, which must be retained as
a failed artifact rather than interpreted as a successful report.

Both marker and report explicitly leave scientific qualification false. The
report retains all existing paired scientific arithmetic and custody limits;
no favorable sign or statistical significance is rewarded by the adapter.

## Verification and integration

`test_grade_artifacts.py` uses the existing tiny invented fixture in
`test_score.py`. It exercises the real paired scorer, correct animal weighting,
shuffled private order, incomplete sensitivity, unclosed producers, malformed
JSON, resource and path rejection, target-last access, persistent consumption,
report failures and preservation of existing output. These are engineering
controls, not source observations or agent trials.

The new test should be enrolled as an additional command alongside the current
joined-scoring component. The old scorer tests need no replay for these new
files. Canonical task, shared workflow, registry and readiness changes are not
part of this package.
