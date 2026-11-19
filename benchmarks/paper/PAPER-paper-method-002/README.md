# Jaxley: differentiable simulation enables large-scale training of detailed biophysical models of neural dynamics

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-002`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Design ready
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Separate paper outcomes

The current definition supports two independent outcomes: recreate the original findings and exceed them on the same task. Each uses matched paper+data and paper+data+author-code conditions. Contract eligibility and declared protocol availability do not establish a delivered runtime or scientific result.

**Corrected primary scope; outcomes remain unqualified.** Both outcome contracts retain the same primary scientific task. Unresolved source criteria still limit receipt admission.

**Primary goal:** Recreate and improve held-out stimulus-to-calcium prediction for the supplied retinal ganglion cell under the original observation, fitting and evaluation protocol, preserving the registered matched-control comparison until its exact primary-source identity is resolved.

**Primary scientific scope:** Retain the source-defined cell, morphology, recording-site/ROI correspondence, stimuli, response transforms, masks, train/validation/test identities and complete original held-out prediction vector. The retained current contract specifies cell20161028\_1,15fields and147model sites; authenticate that historical realization and its raw-ROI mapping before qualification. Compare source-author and candidate predictions on identical evaluation observations using the original masked sitewise Pearson aggregate, with a separately reported recreated author baseline. Keep the original fixed/untrained or constrained-parameter control requirement unresolved until its actual membership, source status and split compatibility are established. Do not substitute a seven-field experiment, simulator agreement, other cells or network tasks.

**Remaining source limits:**

- No verified cached primary paper body or pinned local author notebooks were available to these reviewers or the source owner. Current numerical targets, population mapping and figure identities are retained earlier-audit assertions, not newly authenticated primary-body evidence.
- The historical fixed/untrained OR constrained-parameter control requirement is registration evidence. Exact original-paper membership, reported direction/magnitude and compatibility with the full retinal evaluation remain unbound. Do not invent a roster, require both alternatives, choose the easiest alternative or silently substitute the seven-field comparison.
- The derived implementation establishes that J17 simulates fitted-model responses, J18 analyzes measured/model receptive fields and J19 uses separate reduced data support. This is implementation evidence, not independent authentication of the original paper's conclusions or indispensable-control relationships.
- Absence of a software dependency does not prove absence of a required scientific control. If authentic primary evidence establishes one, source-bind it before qualification; current registration and metadata acceptance alone do not make J17/J18/J19 mandatory.
- Exact historical cache, raw-ROI-to-model-site correspondence, published train/validation/test indices, response transformations, checkpoint and reproduced author comparator remain unqualified. Default configurations are not proof of the published realization.
- Published rounded0.25 and the separately reported positive-site count/maximum are not actual replay results or self-justifying numerical tolerances. Primary acceptance criteria, meaningful gain and dependence-aware uncertainty remain unbound.
- One cell remains one biological unit. Sites, fields, stimuli and fitting seeds supply dependent or conditional information, not independent animal replication or cross-cell generalization.
- The 36-family source programme explicitly does not rewrite the canonical task roster. Preserve it without requiring or claiming whole-programme success from the retinal endpoint.
- All four outcome/access cells remain unknown. Central scope continuity does not admit model execution, historical source equivalence, candidate freeze, scientific reproduction or improvement.

**Retained source scope:** Preserve J17 fitted-model spatial calcium/voltage simulation, J18 measured/model receptive-field analysis, J19 reduced-data learning comparison and the wider source programme as separately named, source-unqualified result families. They neither replace nor automatically gate the primary prediction outcome. Retain authentic anatomy/observation lineage needed to define the prediction computation; do not infer every illustrative output as a separate success criterion. A prediction win alone does not establish mechanistic validity, true conductance recovery, all-paper reproduction or cross-cell generalization.

- [Reviewed primary scope correction](../../../docs/provenance/paper-outcome-scope-decisions.v1.json)
- [Original-finding reproduction contract](reproduction.v2.json)
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

**Disposition:** design\_ready. The original retinal response-prediction task has an ordered metric, recoverable author route and published mean correlation 0.25. Exact historical cache, published split/checkpoint, author replay and admission remain incomplete. This design is explicitly retinal-scoped; the expanded 36-family implementation remains preserved and cannot receive whole-programme success from this endpoint.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 35436 bytes; SHA-256 `0ca58963c4c07298bc258e3abb6a4a0dea1a2415204c681a78182dbad7978644`.
- [Preserved legacy runtime declaration](implementations/registered-runtime/manifest.json)
- [Legacy declaration package](implementations/registered-runtime)

This preserved declaration is lineage, not current execution qualification. Its historical paths may describe the source snapshot.

## Task documentation

- [Pre-scope reproduction source role](docs/provenance/reproduction.pre-scope.role.json)
- [Preserved pre-scope reproduction declaration](docs/provenance/reproduction.pre-scope.v1.json)
- [Current reference qualification and historical replay scope](docs/reference-qualification-scope.v1.md)
- [Original-data preprocessing diagnostic](docs/jaxley-original-data-diagnostic.v1.md)
- [Original-data preprocessing diagnostic evidence](docs/jaxley-original-data-diagnostic.v1.json)

## Implementation artifacts

- [Registered runtime](implementations/registered-runtime) — Calibration only.
  Scope: This is the source package currently selected by the published catalog; current does not assert executable/scientific qualification. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Allen selector](implementations/allen-selector) — Calibration only.
  Scope: Existing published source retained with its scientific scope. Source ownership does not establish equivalence to the complete task contract or current execution qualification. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Checkpoint correspondence v1](implementations/checkpoint-correspondence-v1) — Reviewed source component.
  Scope: Reviewed additive source component for the existing task. The package documentation and source contracts define its scope; source enrollment does not establish authentic-data execution or scientific qualification.
- [Heldout target binding v1](implementations/heldout-target-binding-v1) — Reviewed source component.
  Scope: Evaluator-side target-sidecar and metadata binding to the existing held-out operator schema, with eight generated controls and the retained producer/scorer. Public source contains no authentic target values or private phase manifests. Source enrollment does not establish a full fit, authenticated author/candidate prediction pair, scientific score, improvement, or benchmark readiness. Existing masked site-wise Pearson metric and scientific holds remain unchanged.
- [Original input programme v1](implementations/original-input-programme-v1) — Reviewed source component.
  Scope: Source-only original-input programme and generated-control entry points for Jaxley, with six unchanged prepared input modules, the unchanged numerical control module and bounded reporting transport. Preserves the existing 20 consumer and 15 numerical controls without transferring historical ARM admission to the prospective hosted CPU profile. Enrollment makes no new original-data decoding, model-fitting, scientific-readiness or hosted-runtime qualification claim.
- [Retinal heldout](implementations/retinal-heldout) — Reviewed source component.
  Scope: Full retinal held-out comparison. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/jaxleyverse/jaxley)
- [Code](https://github.com/mackelab/jaxley_experiments)
- [Code](https://github.com/mackelab/jaxley_experiments/blob/5e7a86282adb9d4603b5546ac5d8dad59aec7cc0/nex/fig4_rgc/01_setup.ipynb)
- [Code](https://github.com/mackelab/jaxley_experiments/blob/5e7a86282adb9d4603b5546ac5d8dad59aec7cc0/nex/fig4_rgc/data/20161028_1.swc)
- [Code](https://github.com/mackelab/jaxley_experiments/blob/5e7a86282adb9d4603b5546ac5d8dad59aec7cc0/nex/fig4_rgc/simulate.py)
- [Code](https://github.com/mackelab/jaxley_experiments/blob/5e7a86282adb9d4603b5546ac5d8dad59aec7cc0/nex/fig4_rgc/train.py)
- [Code](https://pmc.ncbi.nlm.nih.gov/articles/PMC12695658/)
- [Code](https://raw.githubusercontent.com/mackelab/jaxley_experiments/5e7a86282adb9d4603b5546ac5d8dad59aec7cc0/LICENSE)
- [Code](https://raw.githubusercontent.com/mackelab/jaxley_experiments/5e7a86282adb9d4603b5546ac5d8dad59aec7cc0/README.md)
- [Code](https://www.nature.com/articles/s41592-025-02895-w)
- [Code](https://zenodo.org/records/14166049)
- [Code](https://zenodo.org/records/3708064)
- [Paper](https://www.nature.com/articles/s41592-025-02895-w)
- [Source](https://zenodo.org/records/3708064)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
