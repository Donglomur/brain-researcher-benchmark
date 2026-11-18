# A data-driven approach to identifying and evaluating connectivity-based neural correlates of conscious visual perception

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-add-010`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Design ready
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Separate paper outcomes

The current definition supports two independent outcomes: recreate the original findings and exceed them on the same task. Each uses matched paper+data and paper+data+author-code conditions. Contract eligibility and declared protocol availability do not establish a delivered runtime or scientific result.

**Corrected primary scope; outcomes remain unqualified.** Both outcome contracts retain the same primary scientific task. Unresolved source criteria still limit receipt admission.

**Primary goal:** Reproduce the published Figure 3c(i–ii) CS↔PFC maximum-squared-DTW-barycenter face-versus-object result during task-irrelevant stimulus onset, including its paired participant feature distribution and corresponding Figure 3a classifier point/fold profile; assess improvement on that same named decoding task and evaluation support.

**Primary scientific scope:** Original condition-averaged empirical inputs, all 94 source participants, first 1000 ms stimulus ON, symmetric CS↔PFC feature semantics, paired face/object feature values and distributions, and the original participant-grouped ten-fold logistic classification. Retain granular feature derivation, probabilities, labels, fold identities/counts, threshold-0.5 accuracies, unweighted fold mean/population SD and separate source AUC companions. Preserve full-search winner-selection exposure across measures, relevance, timing and collapsed directions; the complete discovery matrix is provenance evidence, not automatically a mandatory rerun. Figure S4c trace/barycenter/peak diagnostics apply when claiming that source illustration, with source identity unresolved. This is a result-level classification task, not whole-paper reproduction, unknown-category single-trial decoding, consciousness detection or a causal interaction test.

**Remaining source limits:**

- Root explicitly selected this published panel on 2026-11-17. This is not historical restoration; current complete-family wording requires coordinated correction in both outcomes before final binding.
- The article authenticates 64.3% mean accuracy with 9.4 percentage-point fold SD as a printed reference. This is not a rerun, acceptance tolerance, candidate uncertainty interval or automatic success threshold.
- Exact SPI member/configuration, symmetric source-code mapping, post-QC domain and source feature derivation remain unresolved; do not choose a DTW algorithm variant or directional code row by convenience.
- The article links Zenodo v2 18294156; official v1-to-v2 succession is verified. Payload equivalence and compatibility of pinned code cab648bbe2eab7093f9ab7b9a5fcddabf28e60a0 with final publication/v2 remain unverified. Existing v1 artifacts are not retroactively authenticated.
- Full article HTML and official release landing pages were actually retrieved; correction-body details were indexed primary text only. Corrected supplement identity/content and its source-example mapping remain unresolved.
- Source participant aliases, observation ordering, realized folds, full-precision paired feature/reference outputs and indispensable controls require authentication; no archive or data payload was inspected in this review.
- Historical condition averaging and full-search winner selection must remain explicit. Future protected candidate evaluation requires a justified selection-aware improvement rule on identical task support; discovery-cohort reuse is not untouched external validation.
- Trusted granular execution, numerical agreement criteria, meaningful improvement, participant-aware uncertainty, final access/resource budgets and paired paper+data versus paper+data+code delivery remain unqualified. Current SOTA and successful reproduction/improvement are not claimed.

**Retained source scope:** source\_selection\_provenance: Preserve the full source measure/condition discovery matrix and winner selection as provenance and control evidence. Reproducing discovery or claiming superiority across the larger family would require its actual cells and controls; do not infer blind prespecification from selecting the published winner now. separate\_source\_results: Retain other Figure 3 points and curves, CS↔PAR, other regions/conditions, cross-relevance transfer, neural-mass theory results and broader robustness analyses as separately named evidence; no automatic all-figures obligation. conditional\_illustrative\_companion: Figure S4c source participant traces, barycenter trajectory and peak diagnostic accompany a claim to reproduce that illustration. Exact participant and corrected supplement mapping remain unresolved; illustrative values are not population targets. prospective\_extension: Preserve nested feature selection, new folds, participant-balanced accuracy and label-independent trial-level proposals separately. They cannot silently replace the historical selected-condition task or its mean-fold accuracy.

**Retained source roles:**

| Source field | Declared role |
| --- | --- |
| Item 1 / Role | Source selection provenance |
| Item 1 / Scope | Preserve the full source measure/condition discovery matrix and winner selection as provenance and control evidence. Reproducing discovery or claiming superiority across the larger family would require its actual cells and controls; do not infer blind prespecification from selecting the published winner now. |
| Item 2 / Role | Separate source results |
| Item 2 / Scope | Retain other Figure 3 points and curves, CS↔PAR, other regions/conditions, cross relevance transfer, neural mass theory results and broader robustness analyses as separately named evidence; no automatic all figures obligation. |
| Item 3 / Role | Conditional illustrative companion |
| Item 3 / Scope | Figure S4c source participant traces, barycenter trajectory and peak diagnostic accompany a claim to reproduce that illustration. Exact participant and corrected supplement mapping remain unresolved; illustrative values are not population targets. |
| Item 4 / Role | Prospective extension |
| Item 4 / Scope | Preserve nested feature selection, new folds, participant balanced accuracy and label independent trial level proposals separately. They cannot silently replace the historical selected condition task or its mean fold accuracy. |

- [Reviewed primary scope correction](../../../docs/provenance/paper-outcome-scope-decisions.v1.json)
### Current primary improvement policy

**Disposition:** design\_ready.

The reviewed current policy selects the primary scientific scope. Runtime routes are not declared by this policy metadata.

- [Selected current improvement contract](improvement.primary-scope.v1.json)
- [Authenticated policy revision](docs/provenance/improvement.primary-scope.revision.v1.json)
- [Reviewed primary scope decision](../../../docs/provenance/paper-outcome-scope-decisions.v1.json)

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

## Retained predecessor improvement policy

This original contract preserves the predecessor scientific instructions and source scope. The selected primary policy above governs current improvement.

**Disposition:** design\_ready. The source has ordered stimulus-decoding accuracies and a recoverable classifier recipe. Exact publication/data/supplement identity, original folds and the complete endpoint matrix remain unbound. The existing nested single-measure component changes selection, weighting and input assumptions; it cannot establish a same-task paper win.

- [Retained original improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 92570 bytes; SHA-256 `fe1f8de046c5a2ca6aa496ffe665959cba32282a39c349d4f0d20702ad4b953a`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Conditional nested connectivity evaluation](docs/nested-connectivity-v1.md)
- [Pre-scope reproduction source role](docs/provenance/reproduction.pre-scope.role.json)
- [Preserved pre-scope reproduction declaration](docs/provenance/reproduction.pre-scope.v1.json)
- [MEG generation provenance, observed discrepancies and remaining evidence](docs/generation-provenance-20261118/generation-provenance.v2.md)
- [MEG primary source and derived-evidence identities](docs/generation-provenance-20261118/source-map.v2.json)

## Implementation artifacts

- [Nested connectivity v1](implementations/nested-connectivity-v1) — Calibration only.
  Scope: Conditional 246-feature nested participant-held-out classifier with training-only standardization and complete supplied-protocol support. Canonical feature eligibility, source/cohort/correction joins, upstream functional-connectivity extraction, the matched nuisance comparison, competent references, protected execution and whole-task scientific qualification remain held. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Original feature producer v1](implementations/original-feature-producer-v1) — Reviewed source component.
  Scope: Complete original 94-person input producer has authenticated preparation of94 files,376 windows and1,504,000 finite values. The source four-ROI normalization, six-pair DBA route and ten-fold classifier connect the retained scorer; generated controls use an analytic DBA seam. No native DBA, feature extraction, classifier fit or scientific score ran. Historical release/order/folds and full-precision reference calibration remain unresolved. Two additional mandatory generated controls now exercise the pinned real tslearn 0.6.3 backend; their first hosted execution and locked-wheel runtime compatibility remain pending. The original 40 construction controls and authentic preparation evidence are preserved.
- [Delivery verifier v1](implementations/delivery-verifier-v1) — Reviewed source component.
  Scope: Reviewed delivery-verifier source for the existing MEG task. Source and delivery controls do not establish new scientific results or runtime selection.
- [Paired program v1](implementations/paired-program-v1) — Reviewed source component.
  Scope: Reviewed paired-program and participant-facing source for the existing MEG task, preserving the stated scientific and runtime limits.
- [Original fold score v1](implementations/original-fold-score-v1) — Reviewed source component.
  Scope: Original MEG stimulus-decoding accuracy. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://doi.org/10.1093/nc/niag029)
- [Code](https://doi.org/10.17617/1.WQA3-WK71)
- [Code](https://github.com/anniegbryant/MEG_functional_connectivity)
- [Code](https://raw.githubusercontent.com/anniegbryant/MEG_functional_connectivity/cab648bbe2eab7093f9ab7b9a5fcddabf28e60a0/README.md)
- [Code](https://zenodo.org/records/18294156)
- [Paper](https://academic.oup.com/nc/article/2026/1/niag071/8916853)
- [Paper](https://doi.org/10.1093/nc/niag029)
- [Source](https://zenodo.org/records/15315238)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
