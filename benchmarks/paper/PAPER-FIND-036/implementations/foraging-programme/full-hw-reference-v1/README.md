# Complete head-withdrawal reference component

This separate operator component supplies the missing full Figure 6B reference
path: 200 real-label and 200 training-shuffle fits across all 40 original
sessions, complete out-of-fold probabilities, and sufficient trained BernoulliNB
state for all 400 fitted models. It preserves the existing 200-fit component and
its evidence. No authentic reference performance or paper result has been
established by adding this source.

The original question is retrospective avoidance versus escape, using every
released feature across the original two-second window. Both branches retain
source-order seed-622 stratified fivefold membership. Each session's pooled
out-of-fold probabilities use the original `>= 0.5` escape rule. The primary
metric remains the equally weighted mean of all 40 session balanced accuracies.
Shuffled performance is a compulsory control, never an improvement objective.

## What runs

`reference.py` authenticates the original 8,776-byte author script and extracts
nine unchanged shuffle, fit and prediction statements. Added callbacks count
attempted and completed fits; the returned real and shuffled estimators are
audited against their permitted training rows. The real predictions are checked
against the existing real-only source component in generated controls.

Other classification branches, permutation feature importance, the separate
predictive-window experiment and the author's top-level script are excluded.
This is the complete selected **HW reference component**, not a replay of every
calculation in the paper. The SVC exploration's leave-one-out evaluation is a
different comparison and is not substituted here.

## Prospective shuffle provenance

The historical source used an unseeded `default_rng()` and did not retain its
realization. This component requires the operator to freeze a new integer seed
before execution. It uses NumPy `default_rng(seed)` and refuses a bit generator
other than **PCG64**. One stream covers the HW folds in sorted source-member
order. Each fold records the actual before/after state and the corresponding
training permutation. A cloned generator audits that permutation without
advancing the production stream.

This preserves the source's training-label shuffle operation. It does **not**
reproduce the historical realization or the RNG consumption of the whole script:
the excluded HE and PFI branches also consumed random draws. Neither the printed
shuffled score of 0.5162 nor 100 deterministic engineering nulls is an oracle for
this fresh control. Large seed/state integers remain exact Python JSON integers;
do not round-trip them through JavaScript `Number`.

## Fitted-state audit

Every fold's operator-private JSON contains both fitted models' class counts,
feature counts, feature log probabilities, class log priors, parameters and
feature dimensions, together with fold membership and RNG provenance. There is
no pickle, executable serialization or participant model import. Counts are
checked against the actual training rows, and predictions reconstructed from
the numeric state must agree with the source estimator to absolute tolerance
`1e-12`. That tolerance concerns numerical state auditing only; it supplies no
scientific reproduction tolerance or improvement criterion.

The JSON representation is sufficient for this source BernoulliNB's inference,
not a complete copy of an arbitrary estimator object. `predict_state` operates
on already admitted in-memory state. Its caller must authenticate and bound any
external file before materialization; it is not a general untrusted-file loader.

## Operator invocation

Install this five-file directory beside `program` and `source-api-cli-v1`:

```sh
python -B full-hw-reference-v1/cli.py \
  --source-root program \
  --authority /operator/full-hw-authority.json \
  --authority-sha256 FROZEN_AUTHORITY_SHA256
```

The exact authority fields are:

- `schema`: `foraging_full_hw_authority_v1`; `task_id`: `PAPER-FIND-036`.
- `limits`: existing `common.Budget` fields `read_bytes`, `write_bytes`,
  `retained_bytes`, `other_future_bytes`, `free_floor_bytes`, `wall_seconds`.
- `prepared` and `author_source`: ordinary path/byte/SHA-256 descriptors. The
  prepared manifest must cover all original 40 sessions and source folds.
- `output_root`: a fresh private directory. Existing outputs are refused.
- `output_numeric_capacity_bytes`: at least `16 * H`, where `H` is the total
  original HW row count, for both complete float64 probability panels.
- `metadata_cap_bytes` and `fold_audit_cap_bytes`: positive per-document byte
  limits, each at most 16 MiB. Refusal never truncates a document.
- `audit_total_capacity_bytes`: complete cumulative fold-audit JSON payload
  capacity, additional to probability and other metadata output capacities.
- `rng`: exactly `schema`, `seed`, `bit_generator`, `stream`, with values
  `foraging_prospective_hw_rng_v1`, an integer in `[0, 2**128)`, `PCG64`, and
  `source-member-sorted-HW-only` respectively.
- `component_scope_acknowledged`: exactly `true`.

The trusted CLI authenticates the unchanged bootstrap, five existing runtime
modules and new reference source before loading them. The production runtime
continues to require the adopted NumPy 2.2.6, SciPy 1.15.3 and scikit-learn 1.6.1.
These construction versions are not authenticated historical package versions.
Imports or matching version strings alone do not qualify native execution.

On complete success the private output directory has 200 paired fold-audit JSON
files, 80 raw little-endian float64 probability vectors, `REFERENCE.json` and
`COMPONENT_RESULT.json`. Persisted fold audits are reauthenticated before the
completion receipt. The reference report preserves per-session class recalls,
confusions, balanced accuracies and both equal-session means. No paper outcome
or readiness flag is awarded.

Partial artifacts can remain after a failure; they are never success and are
not automatically resumed or overwritten. Failures report attempted/completed
fit counts when known. An interrupted computation with unknown progress stays
unknown. The outer operator must retain failure evidence, bound and drain
stdout/stderr, enforce deadlines, close owned processes, and admit complete
CPU/RAM/disk costs. The component provides cooperative time and explicit I/O
accounting, not process containment, a hard memory limit or complete physical I/O
measurement. Model/audit workspace and filesystem overhead must be reserved in
addition to the `16 * H` numerical payload.

## Remaining scientific gates

The authentic archive, exhaustive session roster and biological rat/session
mapping remain unadmitted. No data acquisition is supplied by this module.
Source-compatible native replay, independent reference qualification, comparison
with the printed real score, meaningful effect criteria, rat-dependent paired
uncertainty, exposure accounting and protected participant execution remain
separate work. Preserve the equal-session point estimate even when uncertainty
accounts for repeated sessions from five rats.

Paper-plus-data and paper-plus-data-plus-author-code conditions, reproduction and
improvement, remain distinct. A paper-relative improvement is not current SOTA;
a reference component is not a participant attempt or native neural understanding.

## Generated controls

```sh
python -B full-hw-reference-v1/test_reference.py -v
```

The eleven controls use generated 40-session arrays, a fixed generated splitter and
an equation-based estimator double. They exercise the actual source slice,
all 400 fits, real-only parity, frozen PCG64 replay, training/query separation,
fitted-state roundtrips, meaningful input/state failures, tie behavior and the
production CLI's full persistence path. The latter only substitutes the runtime
factory; typed array loading and output reauthentication remain real code paths.
These controls do not execute scikit-learn on authentic data or qualify its
runtime. `FORAGING_EXISTING_SOURCE_ROOT` is a test-only locator for the unchanged
`program` directory during isolated construction.
