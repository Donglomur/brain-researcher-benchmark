# Spike Rate Inference from Mouse Spinal Cord Calcium Imaging Data

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-replacement-015`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Success:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule.

**Disposition:** source\_unresolved. The original spike-rate inference endpoint is recoverable, but the exact full retrained-CASCADE correlation baseline, source-era timing/configurations and per-condition panel are not yet bound. Approximate cortical-default performance or a later timing repair cannot serve as the improvement target.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition (calibration only)](historical/task.pre-improvement.v1.json)

Existing reproduction graders and pilot scores remain calibration evidence. They cannot establish paper improvement. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 61485 bytes; SHA-256 `dd213ec6a8f5524a970a05eb891626eb4eaa50b03156f158c1f9b782e853fb81`.
- [Preserved legacy runtime declaration](implementations/registered-runtime/manifest.json)
- [Legacy declaration package](implementations/registered-runtime)

This preserved declaration is lineage, not current execution qualification. Its historical paths may describe the source snapshot.

## Implementation artifacts

- [Registered runtime](implementations/registered-runtime) — Calibration only.
  Scope: This is the source package currently selected by the published catalog; current does not assert executable/scientific qualification. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.

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
