# MindEye2: Shared-Subject Models Enable fMRI-To-Image With 1 Hour of Data

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-032`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Design ready
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Separate paper outcomes

The current definition supports two independent outcomes: recreate the original findings and exceed them on the same task. Each uses matched paper+data and paper+data+author-code conditions. Contract eligibility and declared protocol availability do not establish a delivered runtime or scientific result.

**Corrected primary scope; outcomes remain unqualified.** Both outcome contracts retain the same primary scientific task. Unresolved source criteria still limit receipt admission.

**Primary goal:** Reproduce the original one-hour MindEye2 retrieval and reconstruction result on subjects 1, 2, 5 and 7, and the source's one-hour subject-1 pretrained-versus-from-scratch reconstruction contrast. Preserve each result's original test support, reconstruction metrics, normalization references and exposure; report both corrected physical retrieval directions and the complete named reconstruction panel. Assess candidate improvement against a qualified author comparator on the same one-hour task under a justified joint decision, keeping the subject-1 transfer contrast separate. Retrieval-only success does not discharge reconstruction or the transfer comparison.

**Primary scientific scope:** Root-selected Option A: the original four-subject one-hour fMRI-to-image retrieval/reconstruction result in Tables 1/8 plus the one-hour point of the subject-1 pretrained-versus-from-scratch reconstruction contrast in Figure 5/Section 3.1.1. Preserve their separate test supports, complete named reconstruction metrics, normalization references, training and image-model exposure, original repeated presentations and source reductions. Apply the authoritative physical-direction correction unambiguously in the task and both access conditions while retaining original labels and correction provenance. Same target-subject data does not imply equal total pretraining data or compute.

**Remaining source limits:**

- Exact source data/checkpoint/input identities, shared1000 support, source-normalization/repeat lineage and native metric parity remain unresolved.
- The exact original one-hour subject-1 contrast ordinates, normalization references, model identities and source comparison outputs still require authentication; its support must not be pooled into the four-subject retrieval result.
- Pretraining exposure intentionally differs between the source pretrained and from-scratch arms and must be disclosed rather than equated.
- Complete reconstruction coverage, qualified same-one-hour author comparator, numerical agreement/superiority criteria and the joint decision remain unresolved. Retrieval-only gain or a forty-session control cannot satisfy the selected complete outcome.
- Thirty overlapping retrieval draws cannot establish participant-level uncertainty, independent sample size or superiority. No scientific criterion is inferred from corrected labels or printed precision.
- Paired paper+data and paper+data+author-code delivery/exposure/resource budgets, independent submitted-computation verification and final canonical bindings remain unqualified; all four scientific outcomes remain unknown.

**Retained source scope:** genuine\_selected\_primary\_component: Corrected one-hour brain-query/image-candidate retrieval, source mean 0.574, and reverse retrieval, source mean 0.790, remain separate real empirical method endpoints; neither alone discharges the reconstruction or subject-1 transfer comparison. Published values are source observations, not newly justified acceptance thresholds. separate\_empirical\_source\_results: Forty-session Table 6, additional training-duration points, human preference, captions, GNet, architecture, ceiling, COCO retrieval, UMAP/ROI/semantic and other source outputs remain separately named evidence where retained. They neither substitute for the selected one-hour contrast nor automatically become mandatory task outcomes. prospective\_extension: New splits, first-session-only normalization, altered cohorts or changed neural/image-model pretraining exposure remain explicitly labelled extensions rather than silent replacements of the original task.

**Retained source roles:**

| Source field | Declared role |
| --- | --- |
| Item 1 / Role | Genuine selected primary component |
| Item 1 / Scope | Corrected one hour brain query/image candidate retrieval, source mean 0.574, and reverse retrieval, source mean 0.790, remain separate real empirical method endpoints; neither alone discharges the reconstruction or subject 1 transfer comparison. Published values are source observations, not newly justified acceptance thresholds. |
| Item 2 / Role | Separate empirical source results |
| Item 2 / Scope | Forty session Table 6, additional training duration points, human preference, captions, GNet, architecture, ceiling, COCO retrieval, UMAP/ROI/semantic and other source outputs remain separately named evidence where retained. They neither substitute for the selected one hour contrast nor automatically become mandatory task outcomes. |
| Item 3 / Role | Prospective extension |
| Item 3 / Scope | New splits, first session only normalization, altered cohorts or changed neural/image model pretraining exposure remain explicitly labelled extensions rather than silent replacements of the original task. |

- [Reviewed primary scope correction](../../../docs/provenance/paper-outcome-scope-decisions.v1.json)
- [Original-finding reproduction contract](reproduction.v1.json)
- [Paired outcome protocols](outcomes.v1.json)
- [Preserved definition before dual outcomes](historical/task.pre-outcomes.v1.json)

| Outcome | Information condition | Endpoint eligibility | Protocol status | Declared availability | Scientific outcome |
| --- | --- | --- | --- | --- | --- |
| Reproduction | Paper data | source\_unresolved | unresolved | unresolved | Unknown |
| Reproduction | Paper data author code | source\_unresolved | unresolved | unresolved | Unknown |
| Improvement | Paper data | design\_ready | unresolved | unresolved | Unknown |
| Improvement | Paper data author code | design\_ready | unresolved | unresolved | Unknown |

Author-baseline replay and historical reconstruction attempts retain their original scopes. They are not promoted to qualified AI reproductions or improvements by these contracts.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** design\_ready. The original one-session retrieval/reconstruction task and corrected published retrieval score are recoverable. Native feature/reference parity, full reconstruction evaluation, exact historical preprocessing and sample manifests, a meaningful effect rule, and measured episode budgets remain unqualified; the feature-only component cannot admit an improvement win.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 192096 bytes; SHA-256 `50fe1753a1fcfdae05a9cdfbf0ff1366101c3ddfbd9bc05f52dbeca0a89aadfc`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)
- [Publisher acquisition identities and remaining qualification (2026-11-22)](docs/publisher-acquisition-identities.v1.json)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Scores identity-bound MindEye2 retrieval embeddings with corrected image/brain directions and 30 frozen 300-candidate pools, plus reconstruction feature kernels, post-model repeat averaging and exposure-ledger audits. Complete native adaptation/reconstruction, authentic four-subject/trial identities, paper/notebook orientation and historical RNG parity, checkpoint/image exposure, rights and protected scientific qualification remain unresolved. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Bounded retrieval v2](implementations/bounded-retrieval-v2) — Reviewed source component.
  Scope: Bounded MindEye2 retrieval scoring. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://arxiv.org/abs/2403.11207)
- [Code](https://github.com/MedARC-AI/MindEyeV2)
- [Code](https://github.com/MedARC-AI/MindEyeV2/blob/76a2609243ba1bacb450e47e3dc78de1f78a9c00/src/Train.ipynb)
- [Code](https://github.com/MedARC-AI/MindEyeV2/blob/76a2609243ba1bacb450e47e3dc78de1f78a9c00/src/final_evaluations.ipynb)
- [Code](https://github.com/MedARC-AI/MindEyeV2/blob/76a2609243ba1bacb450e47e3dc78de1f78a9c00/src/recon_inference.ipynb)
- [Code](https://github.com/MedARC-AI/MindEyeV2/blob/76a2609243ba1bacb450e47e3dc78de1f78a9c00/src/setup.sh)
- [Code](https://huggingface.co/datasets/pscotti/mindeyev2)
- [Code](https://proceedings.mlr.press/v235/scotti24a.html)
- [Code](https://raw.githubusercontent.com/MedARC-AI/MindEyeV2/76a2609243ba1bacb450e47e3dc78de1f78a9c00/LICENSE)
- [Code](https://raw.githubusercontent.com/MedARC-AI/MindEyeV2/76a2609243ba1bacb450e47e3dc78de1f78a9c00/README.md)
- [Paper](https://proceedings.mlr.press/v235/scotti24a.html)
- [Source](https://huggingface.co/api/datasets/pscotti/mindeyev2)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
