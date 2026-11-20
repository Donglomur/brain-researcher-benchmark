# Paired retinal reproduction and improvement interface

This component prepares a benchmark on the original retinal calcium-prediction endpoint: can an AI reproduce the author method, and can it improve the same endpoint? It is source-only. **This version always reports `UNQUALIFIED`.** It provides metadata and scoring interfaces, not a completed full-fit benchmark or an improvement result.

`paired_episode.validate_pair` validates `jaxley-paired-retinal-episode-v2` metadata and `jaxley-retinal-candidate-manifest-v2` descriptors. Descriptors are not array payloads or proof of actual delivery. `paired_assessment.py` exposes `assess_pair(operator, author, candidate, *, episode, trusted_operator_evidence=None, policy_precommit=None)` and reuses the unchanged `../retinal-heldout/score.py` comparison. `CONTRACT.v1.json` records the scientific scope; the executable input schema is described separately by `PAIRING_INTERFACE.v1.json`.

## Scientific scope

The target is dendritic calcium in cell `20161028_1` under checkerboard stimulation, using the supplied transient Off-alpha retinal ganglion-cell morphology. This is final published **Figure 3**, although the author repository uses `nex/fig4_rgc`.

There is **one biological cell**. Its 15 recording fields and 232 ROI constituents yield 147 branch/bin recording sites. Those sites are dependent measurements, not 147 independent biological replicates. Fields, repeated stimulus frames and fitting seeds do not create additional biological cells.

The fresh source-default partition has 12,185 training, 3,047 validation and 128 test rows out of 15,360 field-by-frame rows. The source repeats the same 1,024-frame stimulus sequence across fields and permutes rows using `RandomState(seed_membrane + seed_ruler)`, taking test rows first and then training/validation rows. This is a within-cell held-out-observation assay. It does not demonstrate unseen-stimulus, new-field, cross-cell or animal-population generalization. Exact ordered identities and masks must be bound; counts alone are insufficient.

Common preprocessing z-scores the whole cropped ROI recordings, applies the 7-Hz causal filter, selects delay from all ROI traces before holdout, and merges branch/bin sites. This is not train-only preprocessing. Both reference and candidate must use the same frozen realization, and this caveat must remain visible in any result.

## Participant conditions

| Material | A: paper + data | B: paper + data + code |
| --- | --- | --- |
| Paper, approved stimuli, morphology and identities | Same | Same |
| Approved training calcium | Same | Same |
| Explicitly approved validation targets | Same, if available and enforced | Same, if available and enforced |
| Structural masks and split/preprocessing information | Same | Same |
| Author code at `5e7a86282adb9d4603b5546ac5d8dad59aec7cc0` | Excluded | Included |
| Observed final test calcium or pre-freeze final test feedback | Excluded | Excluded |

Structural masks can be exposed or derived from field, row and site identities. Their secrecy is not claimed. The evaluator owns the authoritative scoring mask, and participants cannot select a favorable support subset. Observed test calcium remains private.

The new `paired_episode.candidate_view_v2` returns detached training and validation targets equally for A/B, while excluding test targets. Its `jaxley-retinal-candidate-input-v2` output includes row IDs, images, currents and structural masks for train/validation/test, with targets only for train/validation. Its v1 predecessor exposed training targets only. This v2 logical view still cannot authenticate approval or enforce filesystem, tool or later access. Both conditions need the same explicitly approved validation material through an enforcing transport with authentic event provenance. Missing bindings and self-reported readiness fields cannot qualify the episode. Visible validation labels also do not establish a 21-query limit: 21 is the author fit's epoch-end validation-check count, not an enforced participant feedback budget.

## Scores and scientific decisions

The retained scorer computes each site's Pearson correlation on the evaluator's valid mask and takes the arithmetic mean over all 147 sites. Its strict admission and undefined-site handling remain unchanged. Do not pool samples across sites, weight by support, omit undefined sites or substitute training loss or simulator equivalence.

The rounded published mean of **0.25** is context. Historical split, configuration, cache and selected-checkpoint correspondence is unresolved, so 0.25 is not a pass threshold for a fresh split. The meaningful fresh comparator is an executed author reference using the exact same split, sites, masks and preprocessing under the frozen matched compute policy. Its programme, validation selection, actual checkpoint and prediction provenance must be bound.

The frozen source author-reference loop has 21 epochs, 48 training batches per epoch and 1,008 updates, with 21 validation checks. These are reference defaults; candidate recipes are separately frozen under the matched policy and need not use those epoch or batch counts. The prepared reference route omits receptive-field plots, epoch-start/final diagnostic checkpoint streams, and train/test monitoring passes with test-scalar logging. Those diagnostics did not select parameters, but their omitted cost must be explicit in the matched-compute policy; this is not complete historical-run equivalence. Full-fit singleton integration and actual reference/candidate execution remain separate work. Numerical K2 qualification does not supply a retinal endpoint score.

The assessment retains the complete unchanged comparison, including descriptive scores and paired delta. It reports `qualification="UNQUALIFIED"` and `reproduced=None`, `improved=None`, `uncertainty=None` in this version. Optional `jaxley-retinal-policy-precommit-v1` metadata can pin a policy artifact, commitment receipt and event identifier. No scientific policy evaluator, authority verifier, chronology verifier or physical-transport verifier is bound here.

A future qualified decision needs a scientifically supported policy committed before candidate or test evaluation. It must define the estimand, scope, reproduction and improvement predicates, dependence treatment and meaningful-effect/uncertainty authority. No numeric tolerance, minimum effect, confidence level, block length or IID 147-site bootstrap is invented here. Missing authority produces an unqualified result rather than a post-hoc scientific rule.

## Remaining work and legacy boundaries

The remaining executable bindings are physical A/B transport with equal approved validation access, full-fit loop integration, actual paired reference/candidate provenance, and supported precommitted scientific policy with enforcing verification. A readiness boolean cannot supply these bindings.

The legacy reproduction, improvement and outcomes contracts retain their historical admission gates and unresolved pairing status. This fresh within-cell interface does not prove historical published-score reproduction, resolution of the fixed/untrained versus constrained-parameter source control, the separate seven-field Figure 3f finding, full-36 programme success or current SOTA.

## Active correction and historical contracts

The task-root `../../improvement.v1.json`, `../../reproduction.v2.json` and `../../outcomes.v1.json` remain immutable historical bindings. The separate versioned active correction lives under `../../policies/retinal-paired-correction-v1/`:

- `ADOPTION.v1.json` binds the exact task, paired component and corrected content.
- `improvement.v1.json`, `reproduction.v2.json` and `outcomes.v1.json` contain the active corrected contracts.

The maintained binder supports this task-specific projection through the explicit `--adopt-retinal-paired-correction` flag. It authenticates those bindings before adoption, and an ordinary subsequent pass preserves the adopted active projection. It does not replace the historical files, weaken preserved registry fields or provide a generic override.

This support makes the correction maintainable; it does not authorize a scientific decision policy, authenticate physical participant isolation or supply completed benchmark execution. The active scientific assessment remains **`UNQUALIFIED`** with the limitations above unchanged.

## Source controls and artifacts

Generated controls exercise interfaces and rejection paths only; they are not original-data execution or biological benchmark results. Run them only in the selected source-control environment. Output belongs in an explicitly supplied external `ARTIFACT_DIR`, separate from every source/input root, with finite read, write and time bounds. Public modules resolve dependencies through repository-relative paths; private evidence-tree paths are not runtime defaults. The owning controller delivers the focused campaign and exact invocation separately.
