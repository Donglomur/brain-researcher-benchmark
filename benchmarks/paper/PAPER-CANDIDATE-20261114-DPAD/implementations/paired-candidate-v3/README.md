# DPAD paired scorer with stable channel correlations

This successor fixes a numerical defect in the paired candidate scorer. Scaling
raw values before subtracting their mean can distort a channel's representable
variation when it has a large common offset. For example,
`x = [3*2**52, 3*2**52+2, 3*2**52+4]` and `y = [-1, 0, 1]` have exact Pearson
correlation 1. The predecessor's arithmetic returns `3/sqrt(10)`, approximately
0.948683. This affects both author references and candidate scores.

The new calculation subtracts an observed finite anchor before scaling. If a
finite opposite-sign subtraction overflows, it halves both operands first.
Centered unit-vector dot products then compute each channel's Pearson CC. A
constant channel still produces `null`, and full scoring still refuses an
undefined channel. Nonfinite values, missing rows, identity changes and incomplete
prediction grids retain their existing rejection behavior. Arithmetic means of
channel correlations remain the endpoints; correlations are not pooled across
channels or flattened samples.

`paired.py` loads the pinned initial evaluator into a private module and replaces
only its `channel_cc` function. The original evaluator's full author-grid path
and the candidate comparison therefore call the same corrected function. The
on-disk initial evaluator and `paired-candidate-v2` remain unchanged. Both
predecessor source identities are checked when this component loads.

Author references, candidate plans and paired results use v3 schemas and carry
`dpad-shifted-channel-pearson-float64-v1`. References made with the old arithmetic
are rejected by the new comparison, even if supplied with a matching content
hash. Owners must freeze a new author reference and candidate plan before using
this scorer. Its commands preserve the earlier argument structure:

```sh
python3 paired.py freeze-author --training AUTHOR_TRAINING --targets TARGETS --predictions AUTHOR_PREDICTIONS --output REFERENCE
python3 paired.py select-candidate --training CANDIDATE_TRAINING --output PLAN
python3 paired.py compare --targets TARGETS --reference REFERENCE --plan PLAN --predictions CANDIDATE_PREDICTIONS --reference-sha256 OWNER_REFERENCE_DIGEST --plan-sha256 OWNER_PLAN_DIGEST --output RESULTS
```

The original seven-session, five-fold, eight-dimension and seven-author-method
comparison is retained: 1,960 author grid cases, 280 candidate grid cases, 35
training-selected candidate cases and 245 paired fold contrasts. Author model
selection, candidate dimension selection, channel order/units, target identity,
paired aggregation and the declared frontier diagnostic are unchanged.

The four new test methods use exact-rational mathematical oracles, finite
extremes, subnormals, strict input refusals and one generated complete-grid
comparison that traverses both scoring paths. They write no generated fixtures
to disk. Run `python3 -B -m unittest -v test_stable_pearson` through the maintained
source-test pool. No existing successful test suite needs to be replayed to
qualify this numerical change.

This remains a prediction-scoring component. It provides no model fitting,
authentic recording result, source-paper reproduction, improvement, new task or
SOTA claim. The session/electrode crosswalk, original preprocessing/sanitization,
authentic author predictions, reference protection, paired participant delivery
and scientific inference gaps documented in the predecessor remain unresolved.
The numerical policy evaluates float64 Pearson arithmetic; it does not claim
bitwise agreement with the original scientific runtime.

## Check a candidate before protected scoring

`preflight` validates a complete submission using only the candidate plan and
predictions. It needs no held-out target arrays or author-reference artifact:

```sh
python3 paired.py preflight --plan PLAN --predictions CANDIDATE_PREDICTIONS --plan-sha256 OWNER_PLAN_DIGEST --output CHECK
```

It shares candidate validation with `compare`: all 35 session-folds, all eight
dimensions (280 prediction cases), selected-dimension recomputation, code and
configuration identities, channel identities/units, exact sample order, finite
arrays and full shapes. The supplied digest should come from the owner's freeze
record; matching a user-supplied digest alone does not authenticate that record.

The output reports structural acceptance and input digests, without correlation
scores or scientific success. Constant predictions may pass preflight and still
produce undefined correlations at protected scoring. Preflight does not establish
training chronology, permitted observations, preparation fidelity or a qualified
author baseline. It does not release or inspect protected targets and does not
change the existing source-panel restrictions or metrics.

Run `python3 -B -m unittest -v test_candidate_preflight test_stable_pearson` for the
new generated input-boundary controls and the existing numerical/full-grid
regressions. These controls are software checks rather than scientific results.

`provenance.json` retains the earlier numerical-revision record. The current
source binding also identifies the added preflight interface and its controls.

## Authenticated evaluator loading

The paired scorer compiles the exact evaluator bytes whose SHA256 it checked.
It does not execute a timestamp-valid bytecode cache or reopen the evaluator path
after authentication. The unchanged predecessor pin and numerical policy still
govern the calculation. `python3 -B -m unittest -v test_authenticated_dependency`
checks valid loading, source refusal, an unrelated cache and a file replacement
using generated source fixtures only.

## Preserve inputs and earlier outputs

All four current CLI commands require a **new output pathname**. Immediately
after argument parsing, before reading any operator input payload or starting
selection/scoring, the CLI refuses an existing destination or a missing output
parent. Refusal covers direct and normalized input aliases, hard links, symlinks,
dangling symlinks, directories and earlier result files. Reviewed dependency
source loading still occurs when the module starts; it does not read operator
training, prediction, target, plan or reference payloads.

The complete result and its unchanged canonical digest are computed before
publication. The CLI writes and flushes the serialized result to an owned pending
file in the destination directory, then creates the final pathname through an
exclusive hard link. A destination created after the early check is preserved;
no existing input or output is truncated or removed. The success digest is
printed only after complete publication. Filesystems without the required
same-directory hard-link operation fail without an overwrite fallback.

Failed serialization, writing, flushing or publication produces no new complete
final result. Cleanup touches only the owned pending file and never the final
destination. A cleanup failure may leave a private `.dpad-result-*.pending` file;
it does not hide an earlier publication failure or turn an already complete
publication into failure. A pending file is not a result. These are safeguards
for trusted operator paths, not isolation against hostile concurrent filesystem
changes or an operating-system resource supervisor.

Result schemas, scientific functions, selection rules, Pearson equations,
canonical result digests, full 35-fold/280-candidate/245-author comparison and all
scientific limitations are unchanged. The initial evaluator and v2 predecessor
remain byte-preserved. Historical provenance records are retained.

Run `python3 -B -m unittest -v test_output_preservation` for generated alias,
exclusive-publication, failure/race and complete-comparison controls. The existing
preflight CLI test now observes the exclusive publisher instead of mocking the
removed unrestricted write. `DPAD_CONTROL_ROOT` optionally retains generated
fixtures; absent that setting, temporary fixture directories are cleaned up.
No authentic recordings, model fits or scientific results are created.
