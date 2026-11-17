# DREDge: robust motion correction for high-density extracellular recordings across species

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-add-003`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Separate paper outcomes

The current definition supports two independent outcomes: recreate the original findings and exceed them on the same task. Each uses matched paper+data and paper+data+author-code conditions. Contract eligibility and declared protocol availability do not establish a delivered runtime or scientific result.

**Corrected primary scope; outcomes remain unqualified.** Both outcome contracts retain the same primary scientific task. Unresolved source criteria still limit receipt admission.

**Primary goal:** Reproduce the original Pt01–Pt03 human DREDge result: source-native LFP motion estimates and manual-trace agreement, with the source-linked before/after neural alignment and fidelity evidence. Assess improvement of manual-trace agreement on the same original complete patient panel only after its comparison and fidelity criteria are justified. Report the local held-channel consistency and alternate-settings panel separately as a prospective diagnostic extension.

**Primary scientific scope:** Legitimate empirical methods result on authentic human neural recordings: source-native LFP motion estimates and per-patient manual-trace agreement over the complete Pt01–Pt03 panel, with original temporal alignment and source-linked before/after neural fidelity. Preserve all relevant source intervals and required trace/spectral companions. Pt03 video or additional human spike/LFP validation is required only when included in the exact source result claimed; no every-figure or other-species expansion is implied.

**Remaining source limits:**

- The authenticated publisher extraction contains abstract, captions and availability information, not complete Results/Methods text.
- Exact manual-reference identities, temporal support, preprocessing, source execution and complete-cohort decision rules remain unresolved.
- Numerical correlation values quoted in later curation were not independently reauthenticated from the publisher extraction; exact numeric reference mapping remains open.
- Required fidelity outputs, patient/interval correspondence and reproduction/superiority criteria must be recovered before complete qualification.
- Pearson agreement is invariant to offset and positive scale; it is not independently observed absolute displacement accuracy. No scalar average, selected patient or prospective consistency score substitutes for the original panel.
- The source-unresolved paired proposal and partial scalar coverage do not establish runnable parity, scientific reproduction, improvement or SOTA.

**Retained source scope:** prospective\_diagnostic\_extension: Local held-channel adjacent-time voltage consistency, energy-ratio and default/fixed/no-correction/alternate-settings comparisons. This proposed evaluator is not an authenticated original-paper co-primary and uses a distinct rigid comparator and interpolation workflow. partial\_primary\_coverage: Three per-patient correlation scalars are a subpanel of the legitimate real-human primary, not complete reproduction or qualification. Their retention does not discharge before/after fidelity and source-companion obligations. prospective\_or\_simulation\_extension: Any newly introduced held-channel/time split or synthetic-motion result remains separately labelled; it cannot establish superiority on the original human endpoint.

**Retained source roles:**

| Source field | Declared role |
| --- | --- |
| Item 1 / Role | Prospective diagnostic extension |
| Item 1 / Scope | Local held channel adjacent time voltage consistency, energy ratio and default/fixed/no correction/alternate settings comparisons. This proposed evaluator is not an authenticated original paper co primary and uses a distinct rigid comparator and interpolation workflow. |
| Item 2 / Role | Partial primary coverage |
| Item 2 / Scope | Three per patient correlation scalars are a subpanel of the legitimate real human primary, not complete reproduction or qualification. Their retention does not discharge before/after fidelity and source companion obligations. |
| Item 3 / Role | Prospective or simulation extension |
| Item 3 / Scope | Any newly introduced held channel/time split or synthetic motion result remains separately labelled; it cannot establish superiority on the original human endpoint. |

- [Reviewed primary scope correction](../../../docs/provenance/paper-outcome-scope-decisions.v1.json)
- [Original-finding reproduction contract](reproduction.v1.json)
- [Paired outcome protocols](outcomes.v1.json)
- [Preserved definition before dual outcomes](historical/task.pre-outcomes.v1.json)

| Outcome | Information condition | Endpoint eligibility | Protocol status | Declared availability | Scientific outcome |
| --- | --- | --- | --- | --- | --- |
| Reproduction | Paper data | source\_unresolved | unresolved | unresolved | Unknown |
| Reproduction | Paper data author code | source\_unresolved | unresolved | unresolved | Unknown |
| Improvement | Paper data | source\_unresolved | unresolved | unresolved | Unknown |
| Improvement | Paper data author code | source\_unresolved | unresolved | unresolved | Unknown |

Author-baseline replay and historical reconstruction attempts retain their original scopes. They are not promoted to qualified AI reproductions or improvements by these contracts.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** source\_unresolved. The source reports ordered human motion-trace agreement, but the registered Pt01-Pt03 task is currently scored by a new consistency/fidelity panel rather than an exactly recovered paper endpoint. Published per-patient correlations are recoverable; their exact temporal alignment, preprocessing, corresponding author output and an admissible full-cohort comparison remain unresolved. Human agreement must not be relabelled absolute motion accuracy.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 36157 bytes; SHA-256 `08cc3c888441f27e1a8f2d2d7f000e3882f53e79a536ce5039ca098e12bc1071`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Content-pinned raw human LFP segment loading, an independent rigid registration control, shared interpolation and prospective paired consistency/fidelity comparison of supplied default-DREDge/alternate shifts against fixed/no correction, with Pt01–Pt03 cohort summaries. Authentic geometry/preprocessing and current data access, native default/alternate DREDge execution, full-population qualification, figure targets, external motion truth, protected evaluation, rights and scientific qualification remain held. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Manual trace agreement v1](implementations/manual-trace-agreement-v1) — Reviewed source component.
  Scope: Human manual-trace agreement. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

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
