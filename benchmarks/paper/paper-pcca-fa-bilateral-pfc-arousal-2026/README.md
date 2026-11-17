# Reproduce bilateral prefrontal covariance decomposition and pupil-linked arousal, then test protected neural-to-pupil prediction

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `paper-pcca-fa-bilateral-pfc-arousal-2026`
- **Track:** Paper research
- **Registration:** Expansion draft
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** source\_unresolved. The original paper contains an ordered estimator-validation route: Fig. 3e/f recovery of known across/within shared variance and dimensionality on simulated data, with pCCA comparison, plus Supplementary Fig. 4 method comparisons on neural recordings. The authorized overhaul can select this original source task. Exact original simulation draws/trial-count grid, baseline arrays, loss aggregation and matched evaluation protocol remain unrecovered; in-sample pupil R² is retained only as descriptive calibration.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 31881 bytes; SHA-256 `9303357e420fcce5ec110bdb3e10dd47153792769a92f6245cec83b54ec0883c`.
- [Registration and provenance](../../../docs/provenance/registrations/expansion-20261114/registry.json)

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Implementation artifacts

- [Descriptive outputs](implementations/descriptive-outputs) — Calibration only.
  Scope: Existing published source retained with its scientific scope. Source ownership does not establish equivalence to the complete task contract or current execution qualification. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/SmithLabNeuro/pcca_fa)
- [Code](https://github.com/meganmcd13/cca)
- [Code](https://github.com/meganmcd13/fa)
- [Code](https://github.com/meganmcd13/figures-dual-pfc)
- [Data](https://api.figshare.com/v2/articles/31431415)
- [Data](https://ndownloader.figshare.com/files/62236864)
- [Data](https://ndownloader.figshare.com/files/62236867)
- [Data](https://ndownloader.figshare.com/files/62236870)
- [Data](https://ndownloader.figshare.com/files/62236873)
- [Data](https://ndownloader.figshare.com/files/62236876)
- [Data](https://ndownloader.figshare.com/files/62236879)
- [Data](https://ndownloader.figshare.com/files/62236882)
- [Data](https://ndownloader.figshare.com/files/62236885)
- [Data](https://ndownloader.figshare.com/files/62236888)
- [Data](https://ndownloader.figshare.com/files/62236891)
- [Data](https://ndownloader.figshare.com/files/62236894)
- [Data](https://ndownloader.figshare.com/files/62236897)
- [Data](https://ndownloader.figshare.com/files/62236900)
- [Data](https://ndownloader.figshare.com/files/62236906)
- [Data](https://ndownloader.figshare.com/files/62236909)
- [Data](https://ndownloader.figshare.com/files/62236912)
- [Data](https://ndownloader.figshare.com/files/62236915)
- [Data](https://ndownloader.figshare.com/files/62236918)
- [Data](https://ndownloader.figshare.com/files/62236921)
- [Data](https://ndownloader.figshare.com/files/62236924)
- [Data](https://ndownloader.figshare.com/files/62236927)
- [Data](https://ndownloader.figshare.com/files/62236930)
- [Data](https://ndownloader.figshare.com/files/62236933)
- [Data](https://ndownloader.figshare.com/files/62236936)
- [Data](https://ndownloader.figshare.com/files/62236939)
- [Data](https://ndownloader.figshare.com/files/62236942)
- [Data](https://ndownloader.figshare.com/files/62236945)
- [Data](https://ndownloader.figshare.com/files/62236948)
- [Data](https://ndownloader.figshare.com/files/62236951)
- [Data](https://ndownloader.figshare.com/files/62236954)
- [Data](https://ndownloader.figshare.com/files/62236957)
- [Data](https://ndownloader.figshare.com/files/62236960)
- [Data](https://ndownloader.figshare.com/files/62236963)
- [Data](https://ndownloader.figshare.com/files/62236969)
- [Data](https://ndownloader.figshare.com/files/62236972)
- [Data](https://ndownloader.figshare.com/files/62236978)
- [Data](https://ndownloader.figshare.com/files/62236981)
- [Data](https://ndownloader.figshare.com/files/62236984)
- [Data](https://ndownloader.figshare.com/files/62236987)
- [Data](https://ndownloader.figshare.com/files/62236990)
- [Data](https://ndownloader.figshare.com/files/62236993)
- [Data](https://ndownloader.figshare.com/files/62237002)
- [Data](https://ndownloader.figshare.com/files/62237011)
- [Data](https://ndownloader.figshare.com/files/62237014)
- [Data](https://ndownloader.figshare.com/files/62237020)
- [Data](https://ndownloader.figshare.com/files/62237029)
- [Data](https://ndownloader.figshare.com/files/62237038)
- [Data](https://ndownloader.figshare.com/files/62237053)
- [Data](https://ndownloader.figshare.com/files/62237068)
- [Paper](https://doi.org/10.1038/s41467-026-71725-0)
- [Paper](https://www.nature.com/articles/s41467-026-71725-0)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
