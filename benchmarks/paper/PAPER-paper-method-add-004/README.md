# iSTTC: A robust method for accurate estimation of intrinsic neural timescales from single-unit recordings

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-add-004`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 30897 bytes; SHA-256 `ae45457700ada5d9a9f578ad4e1eb9bf5825e94850f52753d9b2f9f0d07b0a54`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Empirical sensitivity and Figure 7C mixed models](docs/sensitivity-glm-v1.md)

## Implementation artifacts

- [Isttc registration](implementations/isttc-registration) — Task implementation.
  Scope: Keep mixed current/source-predecessor/context members together; this map does not select a new operative version or qualify execution.
- [Isttc programme](implementations/isttc-programme) — Task implementation.
  Scope: Keep mixed current/source-predecessor/context members together; this map does not select a new operative version or qualify execution.
- [Empirical diagnostics](implementations/empirical-diagnostics) — Empirical diagnostics.
  Scope: Existing published source retained with its scientific scope. Source ownership does not establish equivalence to the complete task contract or current execution qualification.
- [Sensitivity glm v1](implementations/sensitivity-glm-v1) — Task implementation.
  Scope: Complete empirical sensitivity-grid production and conditional dual-reference reports, with source-formula Figure 7C balanced Gaussian REML fixed effects and variances plus separately labeled prospective mouse uncertainty. Authentic cohort/covariate identity, historical QC and window policies, native R/lme4 parity, protected references and scientific qualification remain held; source profile intervals, other figure endpoints and whole-paper reproduction are outside this component.
- [Empirical estimation](implementations/empirical-estimation) — Empirical fit producer.
  Scope: Complete selected 5775-unit/four-estimator fit-production capability through exact external official helper bytes; all 23100 fit coordinates and scientific failures retained. Does not implement Figure 7C GLMs or whole-paper reproduction. Authentic cohort/QC admission, historical numerical parity and scientific qualification remain unverified.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://allensdk.readthedocs.io/en/latest/visual_coding_neuropixels.html)
- [Code](https://gin.g-node.org/iinnpp/isttc)
- [Code](https://github.com/iinnpp/isttc)
- [Code](https://github.com/iinnpp/isttc/blob/e78cfd2b2ea79b7a7e707db7b79e218212497e43/notebooks/mice/calculate_and_plot_tau_per_unit_4methods.ipynb)
- [Code](https://github.com/iinnpp/isttc/blob/e78cfd2b2ea79b7a7e707db7b79e218212497e43/notebooks/mice/load_dataset.ipynb)
- [Code](https://github.com/iinnpp/isttc/blob/e78cfd2b2ea79b7a7e707db7b79e218212497e43/src/isttc/scripts/calculate_acf.py)
- [Code](https://github.com/iinnpp/isttc/blob/e78cfd2b2ea79b7a7e707db7b79e218212497e43/src/isttc/scripts/calculate_tau.py)
- [Code](https://github.com/iinnpp/isttc/blob/e78cfd2b2ea79b7a7e707db7b79e218212497e43/src/isttc/scripts/run_allen_mice_data.py)
- [Code](https://raw.githubusercontent.com/iinnpp/isttc/e78cfd2b2ea79b7a7e707db7b79e218212497e43/LICENSE)
- [Code](https://raw.githubusercontent.com/iinnpp/isttc/e78cfd2b2ea79b7a7e707db7b79e218212497e43/README.md)
- [Source](https://portal.brain-map.org/explore/circuits/visual-coding-neuropixels)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
