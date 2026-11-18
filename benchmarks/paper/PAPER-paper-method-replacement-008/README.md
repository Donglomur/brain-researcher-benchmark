# BaRISTA: Brain Scale Informed Spatiotemporal Representation of Human Intracranial Neural Activity

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-replacement-008`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Separate paper outcomes

The current definition supports two independent outcomes: recreate the original findings and exceed them on the same task. Each uses matched paper+data and paper+data+author-code conditions. Contract eligibility and declared protocol availability do not establish a delivered runtime or scientific result.

**Corrected primary scope; outcomes remain unqualified.** Both outcome contracts retain the same primary scientific task. Unresolved source criteria still limit receipt admission.

**Primary goal:** Reproduce the original spatial-encoding comparison with channel masking held fixed: pretrained channel/channel, parcel/channel and lobe/channel models and their three matching random-initialized encoding controls on both sentence-onset and speech/non-speech decoding, including chronological sensitivity. Preserve all seven original test sessions, five fine-tuning seeds, original random nonoverlapping partitions and all five chronological folds. Assess candidate improvement on these same named endpoints and observation support against a fixed qualified competent author comparator, with exposure and search budgets disclosed.

**Primary scientific scope:** Explicitly selected now by ROOT\_BARISTA\_SELECTION.md: the channel-masking column of source Table 2 and corresponding two language-task results in Table 17. Preserve authentic session/person identities, semantic-positive ROC-AUC, source summaries and every per-session/fold/seed result, with the source validation-selected pretraining-checkpoint regime. This is the complete encoding-scale comparison at fixed channel masking; it does not establish encoding-versus-masking importance, the full factorial ANOVA or a whole-paper result. Source configurations define comparator/reproduction conditions, not automatic candidate architecture restrictions.

**Remaining source limits:**

- The exact named contrast is selected by the new root decision; it was not historically frozen. This scope selection establishes no source equivalence, scientific execution or numerical qualification.
- Authenticate original recordings, channel/annotation/session/person/movie identities, source partitions and chronological folds. Reconcile the person-6 paper/code session mapping rather than assuming equivalence.
- Authenticate checkpoints, pretraining people/movie exposure and validation-selection provenance; keep the selected regime distinct from three-pretraining-seed averaging. Matched exposure and search budgets remain required for comparisons.
- Recover authentic per-query probabilities, competent author replay, source summaries/SEM and dependency-aware reductions. Five fine-tuning seeds and repeated folds are not additional independent people.
- Meaningful gain, paired uncertainty and defensible reproduction/superiority criteria remain unresolved. No universal margin, new aggregate win scalar or requirement to improve random-null controls is introduced; do not average tasks to hide a regression.
- Candidates may use another method within the eventual declared information boundary. Source-model configurations are comparator definitions and reproduction obligations, not a restriction that candidates must share their architecture.
- No encoding-versus-masking ANOVA, all-masking-scale robustness, volume/optical-flow, whole pretraining, scaling or held-person-out claim is selected. Broader claims require explicitly enrolled controls; no current SOTA or new causal mechanism is inferred.
- All scientific outcomes and difficulty/source/native qualification remain unresolved. Preserve predecessor definitions and wider useful source work; align current goal, outcomes, catalog/CLI and admission without adding task IDs or claiming whole-paper completion.

**Retained source scope:** same\_result\_robustness\_companion: Figure 3/Table 10's three-pretraining-seed spatial sensitivity is retained separately from the selected tables' validation-selected checkpoint regime. It remains useful source evidence; the present selection does not silently enroll or recreate all pretraining. additional\_empirical\_comparison: Other encoding/masking factorial cells and PopT/Brant comparisons remain separately named evidence. Claims about relative encoding/masking contributions, robustness across masks or superiority over those models require their corresponding complete controls. separate\_source\_result: Volume/optical-flow classification, masked-channel reconstruction, held-person-out pretraining, data scaling, interpretation, spectral reconstruction and architectural ablations remain valid distinct results. Their existence does not make them mandatory primary obligations for this selected contrast.

**Retained source roles:**

| Source field | Declared role |
| --- | --- |
| Item 1 / Role | Same result robustness companion |
| Item 1 / Scope | Figure 3/Table 10's three pretraining seed spatial sensitivity is retained separately from the selected tables' validation selected checkpoint regime. It remains useful source evidence; the present selection does not silently enroll or recreate all pretraining. |
| Item 2 / Role | Additional empirical comparison |
| Item 2 / Scope | Other encoding/masking factorial cells and PopT/Brant comparisons remain separately named evidence. Claims about relative encoding/masking contributions, robustness across masks or superiority over those models require their corresponding complete controls. |
| Item 3 / Role | Separate source result |
| Item 3 / Scope | Volume/optical flow classification, masked channel reconstruction, held person out pretraining, data scaling, interpretation, spectral reconstruction and architectural ablations remain valid distinct results. Their existence does not make them mandatory primary obligations for this selected contrast. |

- [Reviewed primary scope correction](../../../docs/provenance/paper-outcome-scope-decisions.v1.json)
### Current primary improvement policy

**Disposition:** source\_unresolved.

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
| Improvement | Paper data | source\_unresolved | unresolved | unresolved | Unknown |
| Improvement | Paper data author code | source\_unresolved | unresolved | unresolved | Unknown |

Author-baseline replay and historical reconstruction attempts retain their original scopes. They are not promoted to qualified AI reproductions or improvements by these contracts.

## Retained predecessor improvement policy

This original contract preserves the predecessor scientific instructions and source scope. The selected primary policy above governs current improvement.

**Disposition:** source\_unresolved. Source classification targets and numeric results are recoverable, but the complete registered paper program includes original reconstruction and spatial-scale/pretraining analyses whose H/checkpoints, exact reconstruction evaluation and authentic split/source-clock bindings remain unresolved. A paper–code session-label discrepancy also needs resolution. The local chronological AUC aggregate or source-amended reconstruction MSE cannot by itself establish surpassing BaRISTA on its original full task.

- [Retained original improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 67527 bytes; SHA-256 `462ae59c8692847714ff4b54cc8eec73fc39715f9d00fbc2cebc88190140158e`.
- [Preserved legacy runtime declaration](implementations/registered-runtime/manifest.json)
- [Legacy declaration package](implementations/registered-runtime)

This preserved declaration is lineage, not current execution qualification. Its historical paths may describe the source snapshot.

## Task documentation

- [Pre-scope reproduction source role](docs/provenance/reproduction.pre-scope.role.json)
- [Preserved pre-scope reproduction declaration](docs/provenance/reproduction.pre-scope.v1.json)

## Implementation artifacts

- [Registered runtime](implementations/registered-runtime) — Calibration only.
  Scope: This is the source package currently selected by the published catalog; current does not assert executable/scientific qualification. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Classification endpoints v2](implementations/classification-endpoints-v2) — Reviewed source component.
  Scope: BaRISTA six-endpoint classification scorer. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/ShanechiLab/BaRISTA)
- [Code](https://raw.githubusercontent.com/ShanechiLab/BaRISTA/83b27375eba60e9eba9da4e7dd8fb283baace376/barista/config/braintreebank.yaml)
- [Code](https://raw.githubusercontent.com/ShanechiLab/BaRISTA/83b27375eba60e9eba9da4e7dd8fb283baace376/barista/config/model.yaml)
- [Code](https://raw.githubusercontent.com/ShanechiLab/BaRISTA/83b27375eba60e9eba9da4e7dd8fb283baace376/barista/config/train.yaml)
- [Code](https://raw.githubusercontent.com/ShanechiLab/BaRISTA/83b27375eba60e9eba9da4e7dd8fb283baace376/barista/prepare_segments.py)
- [Code](https://raw.githubusercontent.com/ShanechiLab/BaRISTA/83b27375eba60e9eba9da4e7dd8fb283baace376/barista/train.py)
- [Code](https://raw.githubusercontent.com/ShanechiLab/BaRISTA/83b27375eba60e9eba9da4e7dd8fb283baace376/barista/utility_scripts/aggregate_runs.py)
- [Code](https://raw.githubusercontent.com/ShanechiLab/BaRISTA/83b27375eba60e9eba9da4e7dd8fb283baace376/barista/utility_scripts/run_finetune_folds.sh)
- [Code](https://raw.githubusercontent.com/ShanechiLab/BaRISTA/83b27375eba60e9eba9da4e7dd8fb283baace376/barista/utility_scripts/run_finetune_random_splits.sh)
- [Data](https://braintreebank.dev/)
- [Paper](https://openreview.net/forum%3Fid=LDjBDk3Czb)
- [Source](https://raw.githubusercontent.com/czlwang/PopulationTransformer/d237755bbdea123c60bface0cecbb48bab6f42de/electrode_selections/clean_laplacian.json)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
