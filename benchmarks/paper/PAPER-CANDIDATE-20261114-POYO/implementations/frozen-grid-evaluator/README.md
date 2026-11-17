# POYO complete frozen-grid output evaluator

This is an experimental output consumer for the existing task
`PAPER-CANDIDATE-20261114-POYO`. It implements a prospective, explicitly versioned
evaluation policy. It does not recover the historical 2023 training experiment,
authenticate the currently missing original corpus/grid, train a model, or qualify
a new benchmark. The registry, registered scientific contract and draft are unchanged.

The complete corpus descriptor must contain 158 distinct sessions, seven animal
identities and all four registered source families. This is the corpus membership,
not a requirement that all 158 sessions be held out at every adaptation budget.
Each externally frozen budget supplies its complete held-session list and positive
adaptation trial count. Every listed session requires all four methods: pretrained,
matched architecture from scratch, ridge and recurrent. Every budget/session cell
supplies its full ordered output-occurrence grid. No default roster, adaptation grid,
sample mask, reference output or scientific success threshold is invented here.

## Selected scientific policy

The current pinned official POYO callback uses the continuous-output R2Score metric
after pooling repeated absolute timestamps, then averages session scores equally.
The pinned current readout has two velocity dimensions. This component follows the
mathematical semantics of that explicitly selected contemporary policy:

1. Use only the externally frozen evaluation occurrences; no prediction-dependent
   masks. Pool both predicted and target vectors at identical absolute session
   timestamps by their arithmetic mean. Distinct integer timestamps remain exact,
   including integers above 2^53. Timestamp units and common clock are obligations
   of the external support authority, not facts established by these values.
2. For each dimension, compute residual sum of squares (RSS) and centered total sum
   of squares (TSS). Following the selected TorchMetrics 1.9 convention, RSS at or
   below the represented `1e-4` threshold gives 1; otherwise TSS at or below the
   threshold gives 0; otherwise use `1 - RSS/TSS`. Average the two dimension scores
   uniformly, not by target variance. Negative scores are retained.
3. Average held-session scores equally within each budget/method. Return every
   session and dimension result, per-source and per-animal descriptive session
   averages, and all session-matched pretrained-minus-comparator differences.
   Animal groups are descriptive; they do not replace the primary session macro.

Normalization is material: the near-zero threshold is scale dependent. Inputs and
targets must already be in the same selected, training-only normalized units. Each
session therefore declares its exact two-dimensional mean, positive scale and
provenance identity. This consumer records/validates that declaration; it does not
apply the transform or prove how values were produced. Method execution, matching
architecture, equal compute and no-pretraining contamination also need independent
producer evidence. A matching field or hash alone establishes none of them.

Arithmetic uses exact rational operations on admitted JSON integers and represented
finite binary floats, then converts report scalars to binary64. This avoids overflow
or cancellation in the mathematical reductions, but does not reproduce GPU dtype,
floating accumulation, window timestamp quantization or distributed native behavior.
An unrepresentable output metric is refused rather than clipped. This policy must
not be advertised as bitwise TorchMetrics parity or original-paper reproduction.
The near-constant branch is a library convention, not evidence of useful decoding.

## Input contract and callable boundary

The complete field-level ABI is enforced by `admit_design`, `admit_predictions` and
`admit_targets` in `evaluator.py`. Extra fields, duplicate JSON keys, nonfinite or
boolean numbers, missing/duplicate/unordered output identities and incomplete
method/case support are refused. `test_evaluator.fixture()` is an explicitly invented
complete-shape example; its provenance hashes are not production scientific authority.

`evaluate(design_body, design_pin, prediction_body, target_loader)` authenticates the
exact owner-selected design bytes and admits the entire prediction grid before
calling the trusted target loader once. The design's authority, original session,
support and normalization pins are externally provisioned evidence identities, not
recursively read or independently authenticated by this component. Their scientifically
valid joins remain prerequisites. All targets are then admitted against the identical
complete grid before numerical results are returned. Reports remain evaluator-private.

The CLI authenticates the target bytes against a separately owner-supplied extent and
SHA256 only after public admission. Inputs use nonblocking, no-follow regular-file
opens with a 64 MiB per-operand ceiling; parent directories are trusted operator paths.
The output uses exclusive creation. This is a trusted-host consumer, not a sandbox or
a complete process/memory controller. It makes no authoring-history or no-feedback
isolation claim. All artifact paths and target identities must be selected by the
trusted owner, never taken from candidate-controlled metadata.

Future inert invocation (placeholders must first be supplied from authentic evidence):

```sh
python3 -I -S -B evaluator.py \
  --design OWNER_COMPLETE_GRID.json --design-bytes OWNER_GRID_BYTES \
  --design-sha256 OWNER_GRID_SHA256 --predictions SUBMITTED.json \
  --targets OWNER_TARGETS.json --targets-bytes OWNER_TARGET_BYTES \
  --targets-sha256 OWNER_TARGET_SHA256 --output NEW_PRIVATE_SCORES.json
```

## Evidence, controls and remaining work

`PROVENANCE.json` identifies the official primary views and their limits. The
registered contract still requires the original 158-session mapping, Flint rights,
immutable source reconciliation, complete historical transfer grid/configuration
and competent matched references. This prospective consumer does not resolve those
holds or establish that 158 contemporary converted sessions are the historical 158.

Nine generated methods passed once, including the actual CLI, duplicate timestamps,
unequal dimension/session weighting, negative contrasts, near-zero metric branches,
full-grid target-last refusals and integer clock identity. Three additional checks
covered the subsequently added regular-file boundary without replaying the numerical
suite. No authentic neural values, model, GPU, Docker or private answer was accessed.

Exact rational arithmetic can be expensive for real grids; the 64 MiB input ceiling
is not a host-memory/CPU guarantee or proof that a full authentic programme fits.
Resource adequacy, a closed producer, cohort/split/clock provenance, native parity,
scientific competence and any improvement claim remain unqualified. Publication supplies this experimental source API only; every readiness flag stays
false and the benchmark count does not change. Read `SCOPE_CLARIFICATION.md` before
interpreting submitted-method contrasts or using this component in a paired study.

## Portable source distribution

Run the inert CLI example from this component directory on Unix with Python 3.11.
All local dependencies are included; no package installation or network is needed.
`SOURCE.json` lists every distributed member other than itself. Authenticate its
expected hash from the reviewed release before trusting its member hashes.
`test_delivery.py` checks relocation and an actual generated CLI call; the original
control modules remain available and CI runs them. Local delivery validation does not
repeat the already accepted numerical suites. No authentic inputs are distributed.
