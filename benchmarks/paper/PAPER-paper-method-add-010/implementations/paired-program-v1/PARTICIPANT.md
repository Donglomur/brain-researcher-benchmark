# MEG selected-condition programme interface

Predict whether each queried regional MEG window represents a face or an object.
The observations are **known-category epoch averages** from all 94 original
participants, task-irrelevant stimulus ON, 0–999 ms. They are not single trials,
consciousness labels, or an independent new cohort.

Your `submission.py` receives `--input /input --output /output/RESULT.json`.
Read `/input/CONTEXT.json` and `/input/WINDOWS.npy`.

- The float64 NPY bank has shape **[376, 4, 1000]**, with no pickle objects.
  Rows align exactly with the context's `windows` list. The four regional rows
  are Category Selective, IPS, Prefrontal Cortex, and V1/V2; time advances by 1 ms.
- Every window has an opaque `id`, an opaque participant `group_id`, and a SHA256
  commitment to its 4×1000 little-endian float64 C-order bytes. IDs and bank order
  do not encode the source category. Four windows per participant preserve the
  source's complete four-category block; the other two categories remain
  anonymous in this input.
- `training` lists the labeled face/object windows belonging to other
  participants, in the declared original source-row order. `queries` lists all
  face/object windows of the current held participant group, in opaque order.
  The entire held batch is available together. No held labels are supplied.
- The paper is available at `/paper/PAPER.bin`. Its actual media type is declared
  by the study operator outside this interface. `/contract/PARTICIPANT.md` contains
  these instructions. Only the code-assisted condition receives `/author`, a
  code-only capsule from the fixed official repository revision.

Write one strict JSON object with exactly these keys:

```json
{
  "schema": "meg-paired-program-response/v1",
  "context_sha256": "the exact context commitment",
  "probabilities": {"every query ID exactly once": 0.5},
  "source_feature_values": null
}
```

Probabilities mean **P(object)** and must be finite numbers in [0,1]. Exactly
0.5 predicts face. Missing, extra, duplicate, nonfinite or cross-context output
invalidates the attempt. Do not write other files into `/output`; use `/work`
for bounded temporary work. The trusted wrapper creates the transport envelope
after your process exits successfully.

An **improvement** campaign permits `source_feature_values: null`. A
**reproduction** campaign requires a map covering every one of the 376 opaque
window IDs with the claimed original CS↔PFC maximum-squared-DTW-barycenter scalar,
or null for an explicit source solver failure. Claimed global features must be
identical across all ten fold executions. Consistency alone is not agreement
with an authentic source reference; the evaluator reports that distinction.

The declared outcome is fixed by the study before execution; the programme
author must know it before submitting code. Both assistance programmes freeze
before any of the ten labeled outer-fold views are exposed. Each fold runs in a
fresh isolated phase with the same frozen programme. No other fold's writable
state, outputs or scoring feedback is available. Data are public-source material,
so these restrictions do not claim freedom from external memorization.

The original method used sample-SD ROI standardization then linear detrending,
all six source-ordered DBA pairs, and the maximum of the squared CS↔PFC
barycenter. It screened/imputed the complete four-category feature block before
face/object selection and cross-validation. Its mixed-sigmoid transform used
training location/scale but recomputed final extrema over each transform batch,
including the held batch. These transductive conventions remain disclosed and
possible under this interface. A method change must not be described as a
literal reproduction of those operations.

The primary endpoint remains the unweighted mean of ten held-fold accuracies,
with population fold SD reported separately. Supplied folds are matched across
both assistance conditions, but their historical paper identity is unresolved.
An accuracy above the paper's rounded printed value alone does not establish a
reproduction, meaningful improvement, or SOTA result.
