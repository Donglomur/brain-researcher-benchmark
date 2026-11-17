# DREDge: robust motion correction for high-density extracellular recordings across species

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-add-003`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** source\_unresolved. The source reports ordered human motion-trace agreement, but the registered Pt01-Pt03 task is currently scored by a new consistency/fidelity panel rather than an exactly recovered paper endpoint. Published per-patient correlations are recoverable; their exact temporal alignment, preprocessing, corresponding author output and an admissible full-cohort comparison remain unresolved. Human agreement must not be relabelled absolute motion accuracy.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 30852 bytes; SHA-256 `8e02798f85f2f20a6185e7a06397d7ebd081085830282c6685bbffea7626e102`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Content-pinned raw human LFP segment loading, an independent rigid registration control, shared interpolation and prospective paired consistency/fidelity comparison of supplied default-DREDge/alternate shifts against fixed/no correction, with Pt01–Pt03 cohort summaries. Authentic geometry/preprocessing and current data access, native default/alternate DREDge execution, full-population qualification, figure targets, external motion truth, protected evaluation, rights and scientific qualification remain held. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://dandiarchive.org/dandiset/000957/)
- [Code](https://datadryad.org/dataset/doi:10.5061/dryad.d2547d840)
- [Code](https://doi.org/10.6084/m9.figshare.14024495.v1)
- [Code](https://github.com/Center-For-Neurotechnology/HumanNeuropixelsPipeline/)
- [Code](https://github.com/evarol/dredge)
- [Code](https://github.com/evarol/dredge/blob/ed236113a0b6c29b376065440174da6341a1d875/notebook/ap_registration.ipynb)
- [Code](https://github.com/evarol/dredge/blob/ed236113a0b6c29b376065440174da6341a1d875/notebook/lfp_registration_and_interpolation_demo.ipynb)
- [Code](https://github.com/evarol/dredge/blob/ed236113a0b6c29b376065440174da6341a1d875/src/dredge/dredge_lfp.py)
- [Code](https://raw.githubusercontent.com/evarol/dredge/ed236113a0b6c29b376065440174da6341a1d875/LICENSE)
- [Code](https://raw.githubusercontent.com/evarol/dredge/ed236113a0b6c29b376065440174da6341a1d875/README.md)
- [Paper](https://www.nature.com/articles/s41592-025-02614-5)
- [Source](https://datadryad.org/api/v2/versions/224794/files)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
