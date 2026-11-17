# NEURAL-021 portable deferred protected numerical grade

This source-only component is self-contained and uses the Python standard library.
For generated CI, use Python 3.11.18 on Ubuntu 24.04 with no pip installation.
An independently reviewed manifest pin is required; use the exact bytes and
SHA-256 published with this release rather than computing a new trust pin from
an unreviewed checkout. From any working directory:

```text
python3.11 -I -S -B /ABS/COMPONENT/verify_source.py \
  --manifest-bytes REVIEWED_MANIFEST_BYTES \
  --manifest-sha256 REVIEWED_MANIFEST_SHA256 --check
```

This authenticates every package member, then executes a captured fresh-directory
copy of the generated controls. It requires exactly 11 methods (five original
author and six independent), zero failures/errors/skips/expected failures/unexpected successes, zero authentic input
reads, and zero native/model calls. Missing or changed source, a child nonzero
exit, timeout, malformed result, skipped/expected-failure method, unexpected success or wrong count fails CI with a
nonzero exit. It does not run any producer, dataset, candidate or scientific
experiment. Source check success is not native/runtime qualification.

The package contains all 13 original producer source members and their unchanged
manifest, the unchanged deferred grader, interface and scorer. The `science/private`
directory name denotes the scorer's operator-side role; it contains source code
only. There are no target arrays or case artifacts in this package. `producer/BINDINGS.json`
contains fixed provenance descriptors and file pins, not dataset bodies or private
source imports. `DERIVATION.json` identifies every copied source byte and the few
portable test-path changes. This is authored benchmark code, not a copy of the
primary research repository. The producer's executable bodies are included to
preserve its authenticated closure; generated checks never invoke their mains.

For a real deferred grade, first arrange the separately reviewed original producer
run, independent original observer/outer-exit evidence, protected input preparation,
and a newly qualified grading owner as described below. All retained original
receipt paths must still match the source root used by that producer. Relocating
this source package does not authorize rewriting historical receipt paths: supply
the original authenticated source at its recorded root, or conduct a separately
authorized future producer run from the new root. This package authorizes neither.
Copy `REQUEST.template.json` to a separate operator-controlled location, fill all
selected exact pins and absolute paths, and bind its hash externally. The template
is deliberately disabled and cannot qualify its own evidence.

This operator interface scores the complete immutable output of an already closed
`neural021/full92-program-v1` run. It reuses the original complete observer
admission, public validator and condition-specific trajectory R² scorer. It
launches no candidate, model, container, native phase, signal preparation or
reference. The existing ungraded controller and central registration stay intact.

The scope remains 272 training trials and all 92 queries: 52 active and 40
perturbation, 65 units, six history bins and every 30-by-2 trajectory. A file,
condition or new grading entrypoint is not another benchmark. Source construction
does not establish scientific or runtime qualification.

## Source inspection

Use an independently captured SHA-256 of `grade_completed.py` and explicit paths
to the original source directories. Inspection authenticates the fixed original
13-member source manifest and the unchanged public interface and scorer. It does
not open a selection, query roster, target, candidate or result artifact.

```text
/QUALIFIED/python -I -S -B /ABS/COMPONENT/grade_completed.py inspect \
  --source-sha256 REVIEWED_ADAPTER_SHA256 \
  --producer-root /ABS/COMPONENT/producer \
  --science-root /ABS/COMPONENT/science
```

`--science-root` contains `public/interface.py` and `private/scorer.py`; it need
not contain a dataset. Source filenames, byte extents and hashes are fixed in the
implementation. Inspection does not invoke the producer's bootstrap or main.

## Complete grade invocation

`REQUEST.template.json` is deliberately disabled and contains invalid operand
placeholders. The trusted operator creates a separate request and independently
selects its exact bytes/hash. It binds the source directories, original source
selection and 8,192-byte observer receipt, an independent outer-exit review,
separate grade-runtime review and grading authority, the exact original public
case roster, protected target generation, a fresh output and explicit limits.

```text
/QUALIFIED/python -I -S -B /ABS/COMPONENT/grade_completed.py grade \
  --source-sha256 REVIEWED_ADAPTER_SHA256 \
  --producer-root /ABS/COMPONENT/producer \
  --science-root /ABS/COMPONENT/science \
  --request /OPERATOR/REQUEST.json \
  --request-bytes REVIEWED_BYTES --request-sha256 REVIEWED_SHA256
```

All descriptors have exactly `path`, `bytes` and `sha256`. Paths are absolute,
ordinary, nonsymlink paths. Files must have one hard link and remain stable
through bounded capture. A fresh result cannot replace source, producer,
public-package or input files. Protected targets cannot alias an early metadata
operand or a candidate-visible tree. The original fixed binding determines the
target generation; a new arbitrary target pin is not a new supported dataset.

The original selection is validated by unchanged `policy.selection`, including
complete scope and the historical public-format-only numerical flag. Its
independently selected method/runtime reviews are re-admitted by unchanged
`policy.reviews`. A separate grade request never retroactively changes those
original permissions or claims.

The original observer receipt must bind the exact source, selection, attempt,
worker invocation, source files and original deadlines. It must show natural
integer-zero worker exit, reaping, process-group absence, complete streams, no
timeout/forced kill/timer error, and no outstanding native recovery. An additional
independent outer-exit review binds the exact receipt and observer/worker source,
natural final observer exit and elapsed time within its original success bound.
The worker receipt alone cannot establish its parent's final exit.

The unchanged `observe.admit` then revalidates the complete original graph: all
three phase-specific views and retirements, global program/method commitment,
fit-state seal, whole prediction seal, all three producer/holder/volume closure
sets, strict native exit/CLI metadata, every complete retained artifact and the
separate original grade handoff. An unresolved holder or changed final prediction
denies grading. Opaque state is authenticated but never unpickled or executed.

The captured immutable prediction is validated against all 92 query IDs and every
30-by-2 finite nonboolean value before any protected callback. Only then does the
unchanged scorer invoke the owner-only target loader, exactly once. The loader
authenticates and parses the selected target bytes. The scorer independently
rechecks roster/generation, target shape and numeric domain. Target failures
remain failed grades, with no partial or favorable-case result.

## External review records

The precise, closed schemas are the `expected_review`, `expected_outer` and
`expected_authority` dictionaries in `evaluate`. They bind source, selections,
artifact identities, complete scope, target generation, output and resource
limits. No future result hash appears in an earlier request. The outer-exit record
is created after the original producer actually closes; the grading authority is
selected after that independent record exists. Neither must be invented from a
candidate's claim.

Hashes establish content identity, not reviewer identity or truth. These review
paths are supplied through the trusted operator's independently captured request;
they are not candidate inputs or a permission mechanism for an untrusted caller.
The deployment must exclude candidates and model authors from the operator tree
and protected targets. This module does not itself create that operating-system
boundary or establish historical exposure. The explicit disclosure field does
not undo prior public target exposure.

The grade-runtime record requires separately qualified operator-only target
access, original input/method/runtime admission, complete grading dependencies,
an external CPU/RSS enclosure and full stdout/stderr/failure-cost capture.
`ROOT_COMMAND.json` is an inactive invocation recipe, not an enabling selection.
The external owner must start its clock before interpreter launch and retain
natural final exit through signal-handler restoration and stream durability.

## Result and resource limits

Successful output contains the unchanged scorer's condition-specific
variance-weighted R², per-axis R², squared Euclidean loss and equal-condition
mean. Negative R² remains valid. A constant-target or numeric-range-undefined R²
remains null with its original disposition; loss is retained. No clipping,
baseline-beating threshold or success/failure substitution is introduced.

The immutable result remains provisional until independent natural grader exit
zero. It reports `runtime_qualified:false`, `scientific_qualified:false` and
`submission_ready:false`. A crash after result publication does not make a
successful completed operation. Failures emit a compact stderr record with the
error, consumed read reservations, protected capture count, elapsed wall/CPU
time and explicit absence of physical-I/O/RSS measurement. Original external
captures, including failure prefixes, must be retained by the owner.

Interface ceilings are 64 MiB managed reads, 64 KiB result, 600 wall seconds,
120 CPU seconds and an externally qualified 128 MiB host envelope. The template
selects 300 wall seconds. Bootstrap source loading conservatively reserves its
entire original 1,000,000-byte allowance before capture, including partial-source
failure. Runtime reads use original bounded stable capture. The CLI uses its
original clock, a wall alarm and CPU checks; these are not an aggregate OS memory
or descendant quota. No descendants are launched by this module. External
enclosure and measured feasibility remain separate requirements.

## Generated evidence and scientific interpretation

`test_grade_completed.py` builds complete 92-query filesystem fixtures. It runs
the unchanged observer admission, public interface and scorer; only source-bound
case/target metadata and receipts are replaced by explicitly invented fixtures.
The production CLI has no fixture-binding override. Tests cover perfect,
negative and undefined scores, malformed last queries, missing support, stale
prediction bytes, holder/native closure failures, boolean exit aliases, late
outer completion, source substitution and wrong private generation. The source
inspection and code-substitution refusal also run through the isolated CLI.
No authentic cases, arrays, targets or native observations are read by these
tests. The generated full-path API check is not an authentic CLI grade or a
measurement of native isolation.

The endpoint remains retrospective batch decoding from one macaque/session.
Source onset detection uses future acceleration; it is not an online causal
forecast. Fixed condition/time-template and other comparisons remain necessary
for neural-information interpretation. Query labels were historically public.
This grade alone establishes no competent baseline, contamination resistance,
unseen-subject generalization, scientific reasoning, clinical result or SOTA.
