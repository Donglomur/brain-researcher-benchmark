# Standalone NEURAL014 reference source

`reference_program.py` preserves the original compact day-agnostic GRU/CTC
baseline from `neural014/public/reference.py`. This is an original benchmark
reference, not author weights, the paper's decoder, or a demonstrated competent
comparator. No Torch import, model execution, fitting, scientific inference,
scientific scoring, authentic input access, download or installation occurred
in this source build. Reference performance and runtime remain unqualified.

The program eagerly imports only standard-library modules and NumPy. Torch is
loaded only inside the unchanged `libraries()` helper when a future authorized
neural mode runs. The declared runtime is Python 3.12, NumPy 2.2.6 and Torch
2.6.0, with one Torch thread and deterministic algorithms; no environment/image
availability is asserted. Only the CPU execution condition is exposed. The
local pure controls use already-installed NumPy and do not qualify that runtime.

## Process ABI

Each command runs in its own operator-restricted process:

```
python reference_program.py fit --input /input/INPUT.json --model-output /output/model.bin
python reference_program.py adapt --input /input/INPUT.json --model /model/model.bin --model-output /output/model.bin
python reference_program.py infer --input /input/INPUT.json --model /model/model.bin --output /output/prediction.json
python reference_program.py prior --input /input/INPUT.json --output /output/prediction.json
```

`--device cpu` is optional and has no other allowed value. The program refuses
extra mode-inappropriate artifacts and requires the exact listed mount paths.
The parent authenticates all input/source/model identities, supplies finite
resource limits, seals completed outputs, and captures execution costs. The
program does not emit evaluator receipts or self-certified costs.

Input has exactly `schema`, `mode`, `generation`, and `rows`; schema is
`neural014-program-input-v1`. Generation is the original 64-hex operator
fingerprint. There is no arm/treatment flag. Rows for neural modes contain
exactly `id`, `session`, `role`, `steps`, `features`, plus `tokens` only when
labeled. IDs are opaque 64-hex strings; `features` contains the original
`arrays/<id>.npy` path, byte count and SHA256. Files retain their complete
primitive time-by-512 float32/float64 arrays. Same-open capture, exact NPY
geometry/payload, finiteness, duplicate JSON fields, 18-character integer
lexemes and depth48 are checked by the original captured helpers.

- Fit receives all training/development rows and requires nonempty support in
  all 27 training and nine disjoint development sessions. Targets must remain
  complete and nonempty. Infeasible training CTC alignment refuses the complete
  reference before fitting; development labels are used only for selection.
- Adapt receives one held session's complete usable calibration prefix, one to
  20 labeled observations. Input arrays are already transformed by the operator
  for the full or feature-loss treatment. The reference performs no additional
  feature-loss/shuffle/zero transform.
- Infer receives exactly one complete query with no tokens. It returns exactly
  `{"id": "<opaque id>", "tokens": [...]}`. Empty decoded sequences are valid;
  invalid tokens or exceeding the complete output bound refuse, never truncate.
- Prior receives only `role` and `tokens`, with both base-training and that
  session's calibration support. No IDs, session aliases, durations, arrays or
  query fields are admitted. It returns exactly `{"tokens": [...]}`; the parent
  attaches the same sequence to all session queries.

The local admission layer checks complete role cardinality and forbidden fields.
It cannot reconstruct private sentence exclusion or authenticate selected source
sessions. The parent binds the complete source roster and all remaining suffix
queries before any producer receives data. No cases are selected to fit a budget.

## Preserved mathematics and lineage

The original feature reader, anchored population moments, constant-column scale
one, baseline clipping to +-10, token/CTC helpers, framework setup, network,
input conversion, CTC update and prediction helpers are unchanged. The network
is 512->128 affine+tanh, two unidirectional 128-unit GRU layers, 41 output classes,
no dropout or external language model; per-trial recurrent state resets.

Fit normalization traverses training observations in sorted opaque-ID order.
Seed14014, Adam0.001, gradient norm cap1, ten epochs and the original
`default_rng(SEED+epoch)` trial permutation are retained. The selected checkpoint
has the lowest development session-macro PER, with the earliest epoch winning
exact ties. Development row order is preserved for the original summation rule.
There is no development refit. The fixed means/scales remain unchanged later.

Adapt loads a base-kind artifact, freezes all parameters except the input affine
layer, creates a fresh Adam0.001 optimizer, and performs exactly100 cyclic
updates over calibration observations sorted by opaque ID. Both full and loss
adaptations must independently mount the same original base. The program
refuses an adapted artifact as an adaptation origin. Full/shuffle/zero inference
must mount the same sealed full-adapted artifact; that cross-process identity is
owned by the parent. Query inference changes no fitted parameters or statistics.

The prior remains the most frequent complete training/calibration phoneme
sequence, with lexical tuple tie breaking. Source token order and normalization
are unchanged. The CTC feasibility rule includes adjacent-repeat blank spacing;
`zero_infinity=False`, finite loss checking and gradient nonfinite refusal remain.

## One primitive model artifact

The prior directory (`weights.npz` plus `BASE.json`) is replaced only in transport
by one deterministic ZIP_STORED NPZ `model.bin`. Its 17 arrays are:

- 12 float32 network-state arrays with exactly269097 scalar parameters.
- Float64 training center and scale, each length512.
- Primitive metadata: generation ASCII bytes as64 uint8 values, selected epoch
  as one int64, and artifact kind as one uint8 (`0` base, `1` adapted).

All member names are sorted. Timestamps, permissions and uncompressed ZIP method
are fixed; NPY headers are primitive and written without pickle. Reading does
not use `np.load`, object deserialization, or extraction to the filesystem. The
reader admits only the exact member roster, shapes, dtypes, finite values and
complete payloads under the original64MB ceiling. Normalization scale must be
positive. Adaptation copies the base's selected epoch and normalization values.
No optimizer state, hidden recurrent state, external weights or language model
enters the artifact. Metadata is part of the sealed bytes, not proof of external
execution provenance; the parent verifies and isolates actual producer lineage.

## Controls and handoff

`test_reference_controls.py` exercises only small invented arithmetic, metadata,
RAM NPY transport, arbitrary tiny primitive ZIP arrays, and source structure.
The arbitrary ZIP arrays are not network weights or a checkpoint. Exact AST
comparisons cover the unchanged mathematical and lexical helpers. Tests verify
role barriers, complete fit support, early invalid-CTC refusal, constant-column
normalization, original CTC repeats/blanks, prior ties and deterministic
serialization/refusal paths. They neither import Torch nor execute fit/adapt/infer.

`ORIGINAL_SOURCE_PINS.json` records exact captured helpers; `SOURCE_MANIFEST.json`
pins this source subtree. Parent combines this component with its reviewed
transport/controller, arranges independent review, and performs the isolated
commit. This child makes no Git/index/HEAD changes. Scientific design blockers
remain those in the parent `SCIENTIFIC_DESIGN.json`, including unresolved actual
trial support, missing authentic inputs, unverified source preprocessing and
feature anatomy, unavailable qualified runtime and unmeasured baseline competence.
