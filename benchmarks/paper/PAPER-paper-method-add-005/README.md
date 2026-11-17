# Generating realistic neurophysiological time series with denoising diffusion probabilistic models

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-add-005`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Success:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule.

**Disposition:** source\_unresolved. The original AJILE12 missing-channel experiment has ordered decoding and imputation endpoints, but exact Fig. 3E participant-by-dropout decoding results and paper-equivalent event/mask provenance are not recovered. The current local MSE/PSD/ridge scorer is a prospective reconstruction extension, not the published RF decoding comparison.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition (calibration only)](historical/task.pre-improvement.v1.json)

Existing reproduction graders and pilot scores remain calibration evidence. They cannot establish paper improvement. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 78971 bytes; SHA-256 `21f7f13671ea7bbc55a4be606ca2894db2ef7244fa9c776e1b6a2e4895ea6e9b`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Prospective 12-participant by 15-mask AJILE12 reconstruction preparation, train-only mean/ridge baselines, one-case export, bound submission collection and private target scoring. Actual fresh process/container/state isolation is required because combined masks expose held channels, and remains unqualified. Native data conversion, diffusion/reference execution, temporal guard bands and published downstream/spectral endpoints remain held; scientific qualification is unknown. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](http://www.neurotycho.org/anesthesia-task)
- [Code](https://crcns.org/data-sets/hc/hc-24)
- [Code](https://dandiarchive.org/dandiset/000055/0.220127.0436)
- [Code](https://github.com/mackelab/neural_timeseries_diffusion)
- [Code](https://github.com/mackelab/neural_timeseries_diffusion/blob/7e9c3314dc242c36a206d18f13158c049e84cd1d/conf/dataset/ajile.yaml)
- [Code](https://github.com/mackelab/neural_timeseries_diffusion/blob/7e9c3314dc242c36a206d18f13158c049e84cd1d/ntd/ajile_imputation_experiment.py)
- [Code](https://github.com/mackelab/neural_timeseries_diffusion/blob/7e9c3314dc242c36a206d18f13158c049e84cd1d/ntd/datasets.py)
- [Code](https://github.com/mackelab/neural_timeseries_diffusion/blob/7e9c3314dc242c36a206d18f13158c049e84cd1d/scripts/ajile_script.sh)
- [Code](https://pmc.ncbi.nlm.nih.gov/articles/PMC11573898)
- [Code](https://raw.githubusercontent.com/mackelab/neural_timeseries_diffusion/7e9c3314dc242c36a206d18f13158c049e84cd1d/LICENSE)
- [Code](https://raw.githubusercontent.com/mackelab/neural_timeseries_diffusion/7e9c3314dc242c36a206d18f13158c049e84cd1d/README.md)
- [Paper](https://doi.org/10.1016/j.patter.2024.101047)
- [Source](https://figshare.com/articles/dataset/16599782)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
