# Frozen training-prevalence reference

This component implements the anatomical training-prevalence comparator proposed
in the existing [task contract](../../understanding.v1.json). It supplies a
deterministic five-fold prediction artifact accepted by the unchanged
[primary scorer](../clinical-ccep-artifact-grading/README.md). It adds no task,
scientific result, participant runner or authentic-data qualification.

For held patient h, let n[p,k] be the number of complete site × VTC-contact
blocks assigned anatomical class k in training patient p, and N[p] their total.
Every held block receives

    probability[k] = (1/4) × sum over p != h of n[p,k] / N[p].

Patient weighting is a prospective implementation choice, frozen here to match
the primary patient-macro objective. The registration did not specify prevalence
weighting. This is the empirical optimum for an unconstrained constant predictor
under the corresponding **unclipped training** cross-entropy; no optimality claim
is made for the scorer's clipped loss. It is not a pooled-block prior. Each
block is counted once; its pulse repetitions cannot reweight its patient.
There is no smoothing, fitted hyperparameter, model selection or held-out-class
repair. A class missing from all training patients receives probability zero;
the existing scorer applies its predeclared finite loss floor. The implementation
uses exact rational arithmetic before the final binary64 conversion and rejects
output that fails the existing normalization tolerance.

## Operator procedure

Use Python 3.11+ and its standard library. Keep this directory adjacent to
`clinical-ccep-artifact-grading`; the loader admits the existing scorer's exact
14,609 bytes and SHA-256
`2426ddc5585a113fb839e3b3dd78bf2c684d3f0d5fef2dac0b9af4ab1ebd6f32`
before executing it. No dependency installation or network access occurs.

1. Independently authenticate the complete five-patient owner policy, anatomical
   mapping and all blocks. The policy must pass the existing scorer and declare
   all cases ready. These inputs remain missing from this source delivery.
2. For each held patient, create a separate training-label JSON containing only
   every case from the other four patients. Authenticate and freeze its bytes
   before fitting. Do not pass a complete target document or held-patient rows.
3. Run `fit` once per held patient under the same frozen source/method, then freeze
   each fold JSON and its SHA-256. Fits and class-count diagnostics are evaluator
   artifacts. The predictor accepts no waveform or held-target argument.
4. Run `assemble` with all five frozen folds. Freeze the emitted primary
   prediction artifact before using the existing protected scorer.

Training-label fields are exactly:

```json
{
  "schema": "ccep-training-prevalence-labels-v1",
  "task_id": "clinical-ccep-stimulation-attribution",
  "policy_sha256": "<trusted exact policy digest>",
  "held_patient": "<opaque held patient in owner policy>",
  "class_order": ["hippocampus", "amygdala", "lateral_temporal_cortex", "other_mixed"],
  "rows": [{"case_id": "<training case>", "class_index": 0}]
}
```

The one-row illustration is not a complete usable input. The strict row set is
all declared training blocks, including every anatomical class. Held, foreign,
duplicate or missing rows fail admission. Classes are original stimulation-pair
anatomy, never fitted BPC categories. A label digest authenticates operator bytes;
it does not establish the scientific correctness of the anatomical mapping.

In a private operator directory with a restrictive umask and no-clobber outputs:

```sh
python3 -I -S -B /absolute/path/to/prevalence.py fit \
  --policy POLICY.json --policy-sha256 POLICY_SHA256 \
  --held-patient HELD_PATIENT --training-labels TRAIN_ONLY.json \
  --training-labels-sha256 TRAIN_ONLY_SHA256 > NEW_PRIVATE_FOLD.json

python3 -I -S -B /absolute/path/to/prevalence.py assemble \
  --policy POLICY.json --policy-sha256 POLICY_SHA256 \
  --folds FOLD1.json FOLD2.json FOLD3.json FOLD4.json FOLD5.json \
  --fold-sha256 SHA1 SHA2 SHA3 SHA4 SHA5 > NEW_PRIVATE_PREDICTIONS.json
```

Both commands emit complete JSON on stdout; failures return exit 2 with a generic
refusal. A successful exit establishes software admission only. Retain a private
execution receipt tying the five fold hashes and fixed source hash to assembled
prediction bytes. Assembly verifies declared counts and recomputes the fixed
prior, but cannot prove that a forged operator fit came from authentic labels.
Actual filesystem/process isolation remains the operator runner's responsibility.

The fit for one patient must run with only that fold's training-label artifact
mounted. Other patients legitimately serve as training in other folds, but
fold state must not carry across those invocations. This source is an owner
reference, not a participant access controller.

## Scope and verification

The generated tests distinguish the hand-calculated patient prior from pooled
block/pulse weighting, check held-label noninterference, absent classes, complete
five-fold assembly and the unchanged primary score. They also exercise leakage,
missing/foreign/duplicate rows, wrong hashes, wrong folds, tuned probabilities,
unresolved coverage before label access, and isolated CLI invocation. Run:

```sh
python3 -I -S -B /absolute/path/to/test_prevalence.py
```

Authenticated waveform/event/anatomy preparation, native unit verification,
source completeness, full participant delivery, waveform-dependent references,
and clinical or agent performance remain unestablished. This prevalence reference
cannot demonstrate understanding of a neural waveform. Since its predictions do
not use the response, whole-block response reassignment would leave them unchanged;
this source does not claim to have executed those controls on authentic packets.
No historical result, current task definition or existing source pin is changed.
Code and generated tests are original project-MIT software; external data rights
remain separate.
