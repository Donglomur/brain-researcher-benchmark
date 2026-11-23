# Prospective training-condition mean reference

This implements a simple, fixed reference for the current NEURAL-037 complete
condition-mean prediction task. Its purpose is to make the declared
training-condition-mean control executable. Predictive competence and authentic
runtime qualification remain untested. This is a frozen programme reference;
it supplies no direct-interpretation or typed-viewer model result.

For each query acquisition and ROI, the reference takes the arithmetic mean of
the **observed native frames in that acquisition's visible opposite order**.
Every observed frame has equal weight regardless of its finite-trial count.
The resulting scalar is repeated over every required query frame. It ignores
the other five acquisitions and never aligns their ROI indices with query cells.

An entirely unobserved training ROI receives a constant zero prediction. This
is an explicitly prospective, uninformed fallback convention, not measured zero
physiology. The output records observed training-frame counts for every ROI.
The query target-availability mask is never consulted; complete finite outputs
are required even where the later private evaluator may find no observations.
The signed mean sums exact binary64 ratios and rounds the final mean to float64,
avoiding intermediate overflow and loss of tiny signed-cancellation residuals.
There is no fitting, interpolation, physical-time conversion, onset window or
source-unit reinterpretation.

## Operator route

`reference.py` pins the existing viewer source bootstrap and uses its unchanged
authenticated single-context loader. All 32 files and eleven permitted training
conditions are authenticated; only the same-acquisition opposite order enters
the predictions. Loader integrity does not establish external isolation.

Run a fresh process with only the selected context mounted, preserving the
existing reciprocal-context boundary. The reference code and rule must be
frozen before query exposure. A target in one context is training in another;
never provide the union of contexts or evaluator feedback to a participant.

```sh
python -I -B reference.py predict \
  --view /operator/one-original-view --context acquisition_1_ABC \
  --output /operator/results/acquisition_1_ABC.json
```

After all twelve independent processes have closed, capture their exact output
bytes in an operator-owned JSON list of
`{context_id,path,bytes,sha256}` descriptors, then assemble them:

```sh
python -I -B reference.py collect --captures /operator/all-twelve-reference-captures.json \
  --output /operator/reference-submission.json
```

The collector requires all twelve original identities, the same packet, source
binding and fixed rule, then calls the unchanged public-only complete prediction
validator. It emits the original submission schema for separate private scoring
through `../condition-endpoint-v1/score.py`. It never opens targets, computes a
metric, invents viewer action counters or claims how a participant produced an
output. Capture hashes and reported diagnostics are integrity checks under
operator custody, not independent evidence of execution.

Use the task's existing NumPy environment and separately selected authentic-data
resource protocol. Context outputs are capped at 4,500,000 bytes and the assembled
submission at the original 64,000,000 bytes. These are serialization limits, not
measured process memory, runtime, storage or provider budgets. No source arrays,
outputs or target data are distributed with this package.

## Generated source controls

```sh
python -I -B test_reference.py
```

Controls exercise the equal-frame rule, missingness convention, acquisition-local
identity, signed extreme means, all twelve original geometries, complete capture
assembly and source/rule mismatches using generated arrays. The existing scorer
and loader are reused rather than revised. No authentic neural data, model,
private scoring or scientific result is established by these controls.
