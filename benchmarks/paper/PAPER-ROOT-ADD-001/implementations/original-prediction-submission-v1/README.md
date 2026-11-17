# Original held-sentence prediction submissions

This operator adapter connects frozen **raw predictions** to the original
PAPER-ROOT-ADD-001 scoring procedure. It never imports or executes candidate
Python. It regenerates the source requests privately, authenticates each
submitted prediction against the exact request, computes the original pooled
Pearson correlations, retains the observation products, and compares the full
candidate panel with the provided-author reference.

The complete route preserves 14 sessions, eight people, all 4,209 jobs per
session (**58,926 jobs total**), and all 224 result files. The number of prediction
requests depends on the original qids within each job. It preserves supplied
30-PC embeddings, all original lag/layer and lexical/control conditions,
speaker masks, response smoothing, source sentinel behavior, and held-qid row
ordering through the unchanged original input/prediction implementation.

The older native interface accepts final correlation artifacts. Its separate
70-episode prediction interface uses purged folds and different aggregation.
Neither supplies this original prediction-scoring route. Those components are
retained with their existing scopes.

## Request and submission boundary

`request_identity` binds the source job identity, held qid, training and query
rows, exact training features/responses, query features and expected prediction
shape. It copies their identities into a canonical descriptor before any
participant access. No query responses enter this descriptor or packet.
`export_request` writes one fold's permitted arrays and `REQUEST.json` into an
operator-supplied fresh destination.

**A request packet is not an isolation boundary.** Other folds' training targets
can reveal this fold's held-out responses. A protected executor must expose
only the current packet to a fresh invocation of the globally frozen candidate,
with no other-fold state, reference results, operator data, targets or private
products. The existing 70-episode container profile does not implement this
source-native schedule. This adapter makes no protected-execution claim.

The scorer accepts a frozen submission directory containing only:

```text
SUBMISSION.json
REQUESTS.jsonl
predictions/000000000.npy
predictions/000000001.npy
...
```

`SUBMISSION.json` has exactly these fields:

```json
{
  "schema": "language-original-raw-prediction-submission/v1",
  "candidate_sha256": "<operator-frozen candidate SHA256>",
  "condition": "paper_data",
  "requests": {"bytes": 1234, "sha256": "<REQUESTS.jsonl SHA256>"},
  "request_count": 123
}
```

The integer examples above are illustrative. Every JSONL row has an ordinal,
the trusted request identity, and one bounded prediction file identity:

```json
{"ordinal":0,"request_sha256":"<original request SHA256>","prediction":{"path":"predictions/000000000.npy","bytes":1234,"sha256":"<prediction file SHA256>"}}
```

Requests must match the complete source traversal and ascending held-qid order.
Prediction files contain finite float32 or float64 matrices with every query
row and output column in source order. Their values are predictions, not
submitted correlations or masks. The scorer checks frozen manifest/index/file
hashes, primitive NPY geometry and extent, ordinary stable file identity,
symlinks/hardlinks, duplicate JSON keys, exact order, and complete file coverage.
Missing, reordered, changed or extra products fail; no subset is substituted.

The candidate hash and information condition must match the trusted caller's
freeze. This authenticates the declared submission identity. It does not prove
which program produced those numbers, or that its execution respected the
packet restrictions. An authenticated execution trace remains required before
an AI performance claim.

## Private scoring products

For every source job, the operator retains a compressed private product with
predictions, targets, original qids, time rows and correlations, plus its fold
metadata and exact file identity. These products support later independent
private rescoring; an ordered digest alone would not. They contain held-out
targets and must never be delivered to a participant.

The scorer writes all 224 source-format correlation arrays and `SCORE.json`.
The report contains the complete original Figure 3b–e reduction, the original
nine source contrasts and context curve, and continuous candidate/reference
discrepancies across the full panel. Same-task improvement diagnostics retain
the fixed layer-5, lag-17–19, equal-14-session mean and paired session deltas,
with eight participant clusters. Source 42-entry shuffle statistics do not
become independent-participant uncertainty or an improvement objective.

Undefined correlations remain undefined; original support is not silently
repaired. No binary reproduction margin, meaningful-gain threshold or
participant-level superiority policy is invented. Continuous discrepancies
can be reported without those binary criteria. All scientific qualification,
protected execution, independent AI reproduction and admitted improvement
flags remain false.

## Execution and resources

`python3 -I -B bridge.py --help` lists the complete operator CLI. It requires
the original three input archives, the original author analysis archive, the
frozen submission and candidate hashes, information condition, current
NumPy/SciPy versions, and explicit request/read/working/output allocations.
No candidate command is accepted. The parent scheduler must bound process
time and memory; these declarations are not OS memory enforcement.

Source preparation, reference reading, submitted artifacts and private outputs
have separate accounting. Private products can be large because the complete
original job lattice is retained. Their storage must be budgeted before a real
run; no size, training cost or authentic full-candidate execution is inferred
from generated controls. Partial failed outputs are preserved. There is no
automatic retry or reduced task fallback.

The implementation binds the unchanged original source at commits `7cddf182`
and `e5d5bc61`. The supplied author reference was measured separately in
[`original-reference-20261117`](../../docs/provenance/original-reference-20261117/README.md).
No source archive or authentic candidate prediction was read during this
adapter's construction. The original reported paper value 0.05 and the measured
provided-author mean 0.04512071156679768 remain distinct provenance fields.

Generated controls exercise the actual original held-qid/private-Pearson seam,
retained private observation products, request exposure and row identity,
frozen artifact integrity, malformed/nonfinite predictions, complete roster
admission, bounded files and resource refusal. They use generated arrays and no
model fitting. Run them with:

```sh
python3 -I -B test_bridge.py -v
```
