# Overt-gaze steady-state visual target decoding

[Neural-data understanding](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `NEURAL-084`
- **Track:** Neural-data understanding
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current neural-understanding objective

One of four source labels ordered1up,2left,3right,4down; corresponding nominal reference frequencies60/\[5,7,9,11\]Hz.

**Source delivery:** partial\_delivery. The delivered source defines full54-person overt-gaze SSVEP inputs, CCA/constant/permuted references and a fit/infer programme producer. The task-owned package does not include the protected scorer/preparation body needed to substantiate the documented all 54-label grading path; authentic inputs and runtime are unqualified. It is a prospective400 sample representation, not native401 sample MATLAB parity.

- [Current target, controls and access conditions](understanding.v1.json)
- [Preserved historical task definition](historical/task.pre-understanding.v1.json)

| Condition | Source availability | Representation and boundary | Missing |
| --- | --- | --- | --- |
| Direct observation | not\_delivered | Potential ten-channel four-second numeric or fixed spectral observation for one query; no direct formatter/episode is delivered. Same signal/nominal frequency information only, no query labels, cue order, external source or numerical tools. | Bounded faithful representation and exact direct-response condition. |
| Typed viewer | not\_delivered | Potential typed time/frequency inspection of a fixed ten-channel epoch; no viewer is supplied. Display operations/transform definitions must be frozen and cannot expose target cues or raw arrays; visual versus numeric observations are distinct conditions. | Viewer and renderer, action budget, response collector and information-equivalence accounting. |
| Tool assisted | not\_delivered | A prospective per-query investigator could inspect EEG/spectra or request the fixed CCA decoder. Fresh query context, identical permitted epoch/frequency data and total compute; no held-person adaptation or evaluator feedback. | Adaptive-agent source/transport and separate decoder-alone comparison not delivered. |
| Frozen program | source\_available | One frozen programme with train-only fit and query-only infer over54 folds; three independent query-only CCA/control processes. Seal per-fold model, retire training/query views, reset state and retain all 400responses/fold; fit cannot see held-person query features. | Actual authentic preparation, protected scorer and native full-workload qualification. |

Source availability does not establish a qualified runtime. A programme score cannot be reported as direct or viewer interpretation, and unsupported conditions cannot be inferred from a nearby implementation.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 21339 bytes; SHA-256 `98e57e82954932a7962595611e3d142703021f347aed1d638ef8265a7a545356`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Implementation artifacts

- [Sequential programme](implementations/sequential-programme) — Task implementation.
  Scope: Keep mixed current/source-predecessor/context members together; this map does not select a new operative version or qualify execution.
- [Delivery source](implementations/delivery-source) — Task implementation.
  Scope: Keep mixed current/source-predecessor/context members together; this map does not select a new operative version or qualify execution.
- [Full cohort scoring v1](implementations/full-cohort-scoring-v1) — Reviewed source component.
  Scope: Full-cohort protected scoring component. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Source](https://academic.oup.com/gigascience/article-pdf/8/5/giz002/28563177/giz002.pdf)
- [Source](https://doi.org/10.1093/gigascience/giz002)
- [Source](https://gigadb.org/dataset/100542)
- [Source](https://github.com/PatternRecognition/OpenBMI)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
