# A doubly stochastic renewal framework for partitioning spiking variability

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-009`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** source\_unresolved. The registered Fig. 3 task admits an ordered estimation-agreement question, and the paper reports 23% average discrepancy between spike-only and voltage-derived irregularity. However, the exact percentage-error definition, empirical voltage reference pipeline, cohort/segment identities and conflicting 25/50 ms preprocessing are unresolved. The local prospective held-trial evaluator changes the historical evaluation and cannot certify a same-task paper win.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 28914 bytes; SHA-256 `14cb9dd87da798aa217873376bba6d2a3a4b0c2e19ea38e67450b70e29210f42`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Prospective intracellular bridge for Pala MATLAB fields, 20-kHz spike detection/interpolation, calibration-only voltage-rate splines at both 25 and 50 ms, operational-time CV², paired pinned DSRP spike estimates and segment summaries. Authentic eight-neuron/five-mouse identity and trial admission, spline and bin-policy reconciliation, the published twenty-segment mapping, native reference agreement, protected grading and empirical resources remain unqualified. Exact MIT upstream estimator bytes and notice are preserved. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Pala source adapter v2](implementations/pala-source-adapter-v2) — Reviewed source component.
  Scope: Pala voltage source adapter. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/engellab/DSRP)
- [Code](https://github.com/engellab/DSRP/blob/ba0490d064ea299c975e12bb94f3d922468f6b50/README.md)
- [Code](https://github.com/engellab/DSRP/blob/ba0490d064ea299c975e12bb94f3d922468f6b50/src/dsr_project/neuron_stat.py)
- [Code](https://github.com/engellab/DSRP/blob/ba0490d064ea299c975e12bb94f3d922468f6b50/src/dsr_project/time_rescaling.py)
- [Code](https://raw.githubusercontent.com/engellab/DSRP/ba0490d064ea299c975e12bb94f3d922468f6b50/README.md)
- [Code](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12484930/fullTextXML)
- [Paper](https://www.nature.com/articles/s41467-025-63821-4)
- [Source](https://zenodo.org/records/1304771)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
