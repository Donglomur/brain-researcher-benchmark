# Identifying interactions across brain areas while accounting for individual-neuron dynamics with a Transformer-based variational autoencoder

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-018`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Separate paper outcomes

The current definition supports two independent outcomes: recreate the original findings and exceed them on the same task. Each uses matched paper+data and paper+data+author-code conditions. Contract eligibility and declared protocol availability do not establish a delivered runtime or scientific result.

**Corrected primary scope; outcomes remain unqualified.** Both outcome contracts retain the same primary scientific task. Unresolved source criteria still limit receipt admission.

**Primary goal:** Reproduce the ten-session Allen empirical neural-modeling results, including the matched source component-ablation comparisons and the supported coupling/dynamics outputs within the retained scope. Report the full-model Table S1 negative log-likelihood as a named empirical performance component. Assess any improvement on the same source-qualified observation conditions and metric; lower full-model NLL alone does not reproduce or establish improved coupling interpretation. Preserve target-conditioned inference. Keep the prospective equal-session interaction-gain comparison separate, and retain the original exclusions for unsupported anatomical/condition-specific subpanels.

**Primary scientific scope:** Ten-session Allen empirical held-out neural modeling and matched original component comparisons, with supported coupling/dynamics outputs; the Table S1 full-model NLL is a named within-family performance component. No whole-paper, every-Figure-5-panel or simulation-column requirement.

**Remaining source limits:**

- Original ten-session/trial membership, source eligibility, source preprocessing and final split interpretation are not fully reconciled.
- Published total NLL must be reconciled with released loss reduction, Poisson constants, KL handling, model flags, posterior access and uncertainty aggregation.
- A no-coupling ablation retains trial-wise dynamics and post-spike history; the historical history-only phrase does not authorize relabeling it or imposing a different pure-history comparison.
- Anatomical/condition-specific subpanels excluded in the retained task remain excluded until their required source artifacts are reconstructed and validated; exact supported coupling/dynamics outputs remain unbound.
- Target-conditioned latent inference must remain explicit; blind forecasting and unseen-neuron generalization would change the task.
- The saved notebook repacking/split issue is attributed to the earlier source-recovery handoff; neither independent scope reviewer nor peer reviewer performed a new raw-notebook audit.
- Transcribing Table S1 means and standard errors is not independent reproduction. Lower full-model NLL alone does not establish complete-family success, stronger coupling interpretation or causal influence.
- Exact outcome scope and all required comparisons must be represented faithfully before admission; same\_primary\_unqualified does not admit a full-family reproduction/one-scalar improvement bundle.
- No numerical tolerance, superiority margin, scientific outcome or runtime qualification is established.

**Retained source scope:** within\_primary\_empirical\_performance\_component: Retain full-model Table S1 Allen test NLL as a genuine performance component of the original empirical family. Its improvement does not establish completion or improvement of the complete ablation/coupling/dynamics family. prospective\_extension: The equal-session interaction-gain implementation and proposed neuron-subsampling/shared-input robustness comparisons remain separate prospective extensions, not recovered Table S1 arithmetic or an authenticated pure-history comparator. simulation\_context: The original Table S1 GLM and EIF simulation columns remain distinct source context; they are not replacements for the Allen empirical column or compulsory additions to this retained primary scope.

**Retained source roles:**

| Source field | Declared role |
| --- | --- |
| Item 1 / Role | Within primary empirical performance component |
| Item 1 / Scope | Retain full model Table S1 Allen test NLL as a genuine performance component of the original empirical family. Its improvement does not establish completion or improvement of the complete ablation/coupling/dynamics family. |
| Item 2 / Role | Prospective extension |
| Item 2 / Scope | The equal session interaction gain implementation and proposed neuron subsampling/shared input robustness comparisons remain separate prospective extensions, not recovered Table S1 arithmetic or an authenticated pure history comparator. |
| Item 3 / Role | Simulation context |
| Item 3 / Scope | The original Table S1 GLM and EIF simulation columns remain distinct source context; they are not replacements for the Allen empirical column or compulsory additions to this retained primary scope. |

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

**Disposition:** source\_unresolved. The paper reports an ordered Allen test-NLL result, but the split, metric normalization and model flags needed to reproduce that number disagree with the available code path. The local equal-session interaction-gain endpoint is prospective and cannot substitute for exceeding the published full-model task.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 45187 bytes; SHA-256 `ad6cfd1138438c0c0267ef222de20d90ee82d49ca1573415a8b07eabe9b080c4`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)
- [ablation source recovery v1](docs/ablation-source-recovery-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Prepared-artifact evaluator for the complete ten-session history-versus-interaction comparison, with source neural and latent loss components, matched identities/batches and prospective session-level gains. Target-conditioned latent reconstruction is not blind forecasting. Native Allen preprocessing and eligibility, author interface/layout discrepancies, missing anatomical/condition subpanels, authentic figure references, code/data rights, grouped improvement and protected qualification remain unresolved. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Likelihood components v1](implementations/likelihood-components-v1) — Reviewed source component.
  Scope: Original ten-session, five-variant Allen Poisson likelihood component collection from declared native batches, with separate expected-count, factorial and combined sums. This does not select historical total-NLL, KL, penalty, stage, split or repetition conventions. Paper score and scientific qualification remain unset; no authentic inference or model execution is established.
- [Ablation source audit v1](implementations/ablation-source-audit-v1) — Reviewed source component.
  Scope: Recover the ablation notebook's actual score provenance. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://arxiv.org/abs/2506.02263)
- [Code](https://github.com/Qi-Xin/GLM-Transformer)
- [Code](https://github.com/Qi-Xin/GLM-Transformer/blob/421b5eef321cac3d1c1279759e0f6b638068b021/DataLoader.py)
- [Code](https://github.com/Qi-Xin/GLM-Transformer/blob/421b5eef321cac3d1c1279759e0f6b638068b021/Reproduce_figures/Fig5.ipynb)
- [Code](https://github.com/Qi-Xin/GLM-Transformer/blob/421b5eef321cac3d1c1279759e0f6b638068b021/allen_env_full.yml)
- [Code](https://proceedings.neurips.cc/paper_files/paper/2025/file/ac643478c07baa8432690555e4702b65-Paper-Conference.pdf)
- [Code](https://raw.githubusercontent.com/Qi-Xin/GLM-Transformer/421b5eef321cac3d1c1279759e0f6b638068b021/README.md)
- [Paper](https://proceedings.neurips.cc/paper_files/paper/2025/file/ac643478c07baa8432690555e4702b65-Paper-Conference.pdf)
- [Source](https://portal.brain-map.org/explore/circuits/visual-coding-neuropixels)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
