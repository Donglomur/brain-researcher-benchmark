# Spike Rate Inference from Mouse Spinal Cord Calcium Imaging Data

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-replacement-015`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Separate paper outcomes

The current definition supports two independent outcomes: recreate the original findings and exceed them on the same task. Each uses matched paper+data and paper+data+author-code conditions. Contract eligibility and declared protocol availability do not establish a delivered runtime or scientific result.

**Corrected primary scope; outcomes remain unqualified.** Both outcome contracts retain the same primary scientific task. Unresolved source criteria still limit receipt admission.

**Primary goal:** Reproduce and assess improvements in the paper's continuous spike-rate inference comparison on paired spinal calcium/electrophysiology recordings, preserving both spinal populations, the source-defined held-neuron exclusions, original sampling/noise/target-smoothing conditions, cortical/default and cross-dataset CASCADE, raw fluorescence and OASIS comparators, and source-grounded correlation, bias and error outcomes. Retain complete per-neuron and condition panels and necessary alignment and temporal-precision controls. Report reproduction and source-qualified improvement separately. Acquisition experiments and the downstream in-vivo application remain outside this bounded task.

**Primary scientific scope:** The retained empirical paired-recording inference comparison: continuous smoothed rates against electrical ground truth, with original matched held-neuron evaluation, both spinal populations, original sampling/noise conditions, full method/control coverage and source-grounded correlation/bias/error outcomes. Preserve the source-qualified Figure 4 cortex comparison, sweeps and essential timing/precision controls already retained by the accepted component. The thirteen-group Figure 1-6 census was an owner's interpretation, not an explicit decision enrolling every result as primary. Figure 7 and acquisition experiments remain excluded.

**Remaining source limits:**

- Exact source-era condition/neuron/recording manifests, noise realizations, checkpoints, held-neuron exclusions, support masks, alignment and animal/session dependence remain unresolved.
- Keep original source timing separate from the later one-timepoint correction, current demo noise grid and prospective native-400ms condition; none proves original figure equivalence.
- Historical correlation, bias and error outcomes remain required. The component's single-pass normalized L1/signed-bias diagnostics are not qualified reproduction of original source or later-demo bias/error columns. Source metric definitions and timescale support must be authenticated.
- Preserve source discrepancies in neuron-count ordering, noise eligibility and Figure 6c model identity. Do not resolve them by a favorable cell subset, guessed comparator or convenient filename glob.
- Complete reference outputs, justified agreement/superiority criteria, uncertainty units and paired access/budget manifests remain unestablished. Correlation gain alone must not conceal rate-calibration failure.
- Held-neuron electrical targets cannot be exposed to inference candidates to support a newly enrolled descriptive task. Any added target-access regime or full thirteen-group primary project requires explicit scientific scope and observation-policy decisions.
- Neither metric software checks nor a source inventory establishes authentic reproduction, improvement, native parity or SOTA. Restore independent reproduction reporting without accepting a partial condition as the full task.

**Retained source scope:** Retain real paired-recording spike-pattern/kernel characterization, high-frequency-event reconstruction and separate relative-rate/segment analyses as specifically named source evidence. They are genuine empirical results, not automatically mandatory primary outcomes. The supplied-array metric kernel is partial support for the registered primary inference task; it is not a separate successful reproduction. The Figure 3d simulation illustration is distinct from these empirical results and cannot satisfy the primary task.

- [Reviewed primary scope correction](../../../docs/provenance/paper-outcome-scope-decisions.v1.json)
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

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** source\_unresolved. The original spike-rate inference endpoint is recoverable, but the exact full retrained-CASCADE correlation baseline, source-era timing/configurations and per-condition panel are not yet bound. Approximate cortical-default performance or a later timing repair cannot serve as the improvement target.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 67266 bytes; SHA-256 `5e8464df4214c83b470b58fb6098a1489cd2fc8a69a66750f214e7d3dd574ce0`.
- [Preserved legacy runtime declaration](implementations/registered-runtime/manifest.json)
- [Legacy declaration package](implementations/registered-runtime)

This preserved declaration is lineage, not current execution qualification. Its historical paths may describe the source snapshot.

## Implementation artifacts

- [Registered runtime](implementations/registered-runtime) — Calibration only.
  Scope: This is the source package currently selected by the published catalog; current does not assert executable/scientific qualification. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Original endpoint metrics v1](implementations/original-endpoint-metrics-v1) — Reviewed source component.
  Scope: Original spinal-calcium endpoint metrics. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.
- [Current condition evaluator v1](implementations/current-condition-evaluator-v1) — Reviewed source component.
  Scope: Bounded file evaluator for the explicitly adopted current\_source\_noise7\_eligible\_v1 condition: complete 132-record census, all 116 eligible recordings, all 44 neurons and 16 fixed input-noise exclusions, with shared support and separate 21/23-neuron cohort summaries. This is a current-source comparison, not recovered historical Figure 4 aggregation. Source-qualified references, held-neuron provenance, protected participant delivery and unresolved historical alignment, sweeps and cortical scope remain separate; no authentic scoring or candidate result is claimed.
- [Source condition primitives v1](implementations/source-condition-primitives-v1) — Reviewed source component.
  Scope: Complete 44-neuron/132-recording source admission and the root-adopted current-source bank have one authenticated preparation:116 recordings prepared and16 explicitly unavailable because native noise exceeds the requested level. No model or scientific scoring ran. The existing full132-record metric route still refuses this incomplete condition; historical alignment/noise scope, cortical scope, qualified comparisons and protected participant delivery remain separate.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://doi.org/10.1523/JNEUROSCI.1187-24.2025)
- [Code](https://github.com/HelmchenLabSoftware/Cascade)
- [Code](https://raw.githubusercontent.com/HelmchenLabSoftware/Cascade/1f9f98bf93b9b554ab68d6304aa365ab7c7ee34f/Demo%20scripts/Demo_benchmark_model.py)
- [Code](https://raw.githubusercontent.com/HelmchenLabSoftware/Cascade/1f9f98bf93b9b554ab68d6304aa365ab7c7ee34f/Demo%20scripts/Demo_benchmark_model_within_dataset.py)
- [Code](https://raw.githubusercontent.com/HelmchenLabSoftware/Cascade/1f9f98bf93b9b554ab68d6304aa365ab7c7ee34f/Demo%20scripts/Demo_discrete_spikes_with_ground_truth.py)
- [Code](https://raw.githubusercontent.com/HelmchenLabSoftware/Cascade/1f9f98bf93b9b554ab68d6304aa365ab7c7ee34f/Demo%20scripts/Demo_train.py)
- [Paper](https://doi.org/10.1523/JNEUROSCI.1187-24.2025)
- [Source](https://github.com/HelmchenLabSoftware/Cascade/tree/1f9f98bf93b9b554ab68d6304aa365ab7c7ee34f/Ground_truth)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
