# Conditional predictive information in worm neural history

[Neural-data understanding](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `NEURAL-048`
- **Track:** Neural-data understanding
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current neural-understanding objective

The independently recomputed equal-worm difference between behavior-only and behavior-plus-neural held-out Bernoulli log losses; null or negative increments are valid answers. Labels are dorsal=1 and ventral=0.

**Source delivery:** partial\_delivery. A causal-history helper and independent matched-probability scorer exist. They do not execute native conversion or model fitting, and scorer receipts cannot establish that supplied predictions used causal features or isolated whole-worm training.

- [Current target, controls and access conditions](understanding.v1.json)
- [Preserved historical task definition](historical/task.pre-understanding.v1.json)

| Condition | Source availability | Representation and boundary | Missing |
| --- | --- | --- | --- |
| Direct observation | not\_suitable | The scored target is an across-worm predictive-information contrast requiring matched trained predictions. A no-tools reading of a trace cannot estimate this held-out incremental loss; reading a precomputed loss table would be a different arithmetic task. | A separate direction-decoding direct task would need an explicitly separate condition and endpoint. |
| Typed viewer | not\_delivered | A future trace viewer may support investigation of history/controls; it does not itself deliver the full predictive contrast. Typed actions must preserve the causal cutoff and hide query targets; all numeric claims still require independent scoring. | No task-specific viewer, matched rendering protocol or participant transport. |
| Tool assisted | not\_delivered | Causal history and loss/interval routines can support numerical investigation of matched predictions. Operator reference is private; participant model fitting, feature lineage and all case-local tools must be independently bound and audited. | No supplied native fitting/investigator runner or isolation evidence.; Operator analysis/comparator source does not supply a participant episode or candidate programme execution route. |
| Frozen program | not\_delivered | Intended precommitted decoder/training recipe producing the three complete matched arms. Freeze recipe and budgets before query access; only training-worm labels may fit transforms or select hyperparameters. | Current CLI grades prediction artifacts; it does not execute a candidate or attest its fitting. |

Source availability does not establish a qualified runtime. A programme score cannot be reported as direct or viewer interpretation, and unsupported conditions cannot be inferred from a nearby implementation.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 15880 bytes; SHA-256 `4b6c95dc1566a712f30087e67eeaccb0e58484ff57fdc6e2a77ad1170e7dc15b`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Task implementation.
  Scope: Builds causal predictor histories and scores matched behavior, neural-history and shifted-neural probabilities using equal-worm log-loss contrasts and paired worm uncertainty. Native H5/MAT conversion, complete animal/episode identities, actual causal preprocessing and fitting, rights, authentic references and final target/window/protocol qualification remain open; scorer receipts do not attest those operations.
- [Halfcycle support v1](implementations/halfcycle-support-v1) — Reviewed source component.
  Scope: Reviewed additive source component for the existing task. The package documentation and source contracts define its scope; source enrollment does not establish authentic-data execution or scientific qualification.
- [Frozen comparator v1](implementations/frozen-comparator-v1) — Reviewed source component.
  Scope: Frozen behavior comparator for NEURAL-048. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Source](https://datadryad.org/dataset/doi:10.5061/dryad.8sf7m0cz2)
- [Source](https://datadryad.org/terms)
- [Source](https://github.com/flavell-lab/SAAV_Decoding)
- [Source](https://raw.githubusercontent.com/flavell-lab/SAAV_Decoding/c7e7e18a84cde5dc02df9d63492293b38402eb2c/DecodingMain.ipynb)
- [Source](https://raw.githubusercontent.com/flavell-lab/SAAV_Decoding/c7e7e18a84cde5dc02df9d63492293b38402eb2c/kfold.py)
- [Source](https://raw.githubusercontent.com/flavell-lab/SAAV_Decoding/c7e7e18a84cde5dc02df9d63492293b38402eb2c/load_data.py)
- [Source](https://www.nature.com/articles/s41593-026-02257-5)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
