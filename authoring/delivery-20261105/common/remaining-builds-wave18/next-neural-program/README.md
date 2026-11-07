# NEURAL-083: complete fixed-calibration program source

This source composes the existing OpenBMI motor-imagery task across all 54
people, two sessions, four calibration settings and three information arms.
Each independent candidate/reference panel contains 1,296 results and 129,600
probabilities. The same 10,800 online trials occur across the conditions; they
are not additional tasks or independent observations.

The new interface separates fitting from inference. Fitting receives the exact
original globally opaque-sorted training matrix and permitted metadata. After
natural process closure, the operator seals the model and retires the training
mount. A fresh inference process receives that condition's 100-row query matrix
and the sealed model. Every condition uses a new context and model. A learner
may keep permitted labeled training examples inside its model. Query truth is
never available to fitting or inference.

The operator uses the original full prepared recordings to construct one view
at a time. Donor session fragments are not candidate-visible: a proposed
fragment interface was rejected because it revealed which donor trials shared
a session, information absent from the original EEG condition. The rejected
design and independent finding remain in this package.

Batch inference does **not** mechanically prove that arbitrary code avoids
query adaptation. The original rule remains mandatory. A future run requires
independent method/exposure review tied to the exact program, source, input
index, image, resource caps and execution configuration. There is no claim of
mechanically isolated pointwise inference or universal prevention of covert
fitting. The separate interactive-agent condition is outside this source.

The independently frozen reference retains the original prospective CSP,
sample logvariance, shrinkage-LDA and training-only Platt calibration recipe.
It uses the supplied target calibration alone when present and all donors for
zero-calibration transfer. Its serializable state preserves the prior fallback,
five training-only folds and final refit. This is a source successor, not
numerical MATLAB parity or measured reference competence. Only that reference's
own captured, sealed state may be unpickled by its trusted entry point.

The unchanged primary is target20/EEG balanced accuracy, averaged over sessions
within each person and then over all 54 people. Both complete 1,296-result
panels must pass admission before a single protected target callback. Existing
calibration/context/permutation contrasts remain unchanged; candidate minus
the independent reference is an additional named comparison.

The 108 prepared arrays contain 433,728,000 numeric bytes. The straightforward
full protocol constructs approximately 369.2 GB of training matrices and
3.47 GB of query matrices cumulatively across both panels. This is repeated
construction work, not resident dataset size. A 512 MiB model allowance permits
retaining all allowed training values, but its cumulative worst-case capture
allowance across all conditions is approximately 1.39 TB. Source-derived
metadata, native response, input/readback and retained-output bounds are also
included in prospective admission. None is an observed runtime cost or a claim
that the full 5,184-phase workload is feasible on this Mac.

`program/index.py` constructs an operator-only canonical index from already
authenticated records and an authorized in-memory key; it opens no key or
neural file. `program/store.py` copies selected float32 rows without numerical
transformation. `program/controller.py` implements the full composition;
`program/native.py`, `worker.py` and `observe.py` provide bounded source-captured
execution and independent closure. The public registration adapter remains
disabled. Future preparation, runtime selection and grading are distinct root
actions; templates are not qualifying evidence.

No authentic data, identity key, native process, numerical model fit or
scientific score was used to construct this source. Full input/support,
dependency/image, method, filesystem/resource and actual runtime qualifications
remain absent. Original persistent class cues and 100-trial-calibrated visual
feedback remain scientific limitations: this is retrospective protocol-class
decoding, not cue-independent intention decoding or a 20-trial closed-loop
performance claim.
