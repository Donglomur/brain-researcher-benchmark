# CBraMod: A Criss-Cross Brain Foundation Model for EEG Decoding

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-024`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Separate paper outcomes

The current definition supports two independent outcomes: recreate the original findings and exceed them on the same task. Each uses matched paper+data and paper+data+author-code conditions. Contract eligibility and declared protocol availability do not establish a delivered runtime or scientific result.

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

**Disposition:** source\_unresolved. The original CBraMod full twelve-dataset program has ordered decoding endpoints, but original cohort/split identities and a complete same-support baseline are unrecovered. The author explicitly disclaims exact split comparability for historical TUAB/TUEV comparisons and replaced their splitting code after publication. The current implementation's person-held-out 30%-label condition changes the original task and is only an extension. Recovering PhysioNet Table 3 alone cannot qualify this full-panel task.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 18041 bytes; SHA-256 `fa0148010d746e107b651519c94ac1be23d7c435eb22b09538c700975c7cc8cd`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Publisher acquisition findings (2026-11-22)](docs/publisher-acquisition-findings-20261122.md)

## Implementation artifacts

- [Cbramod paired program](implementations/cbramod-paired-program) — Calibration only.
  Scope: Existing published source retained with its scientific scope. Source ownership does not establish equivalence to the complete task contract or current execution qualification. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Original endpoints float64 v2](implementations/original-endpoints-float64-v2) — Arithmetic portability successor not scientific qualification.
  Scope: Promote only integer operands to float64 before regression arithmetic, retaining original floating reconstruction and frozen predecessor. This fixes older-sklearn portability; current 1.9.1 already promotes internally.
- [Original endpoints v1](implementations/original-endpoints-v1) — Reviewed source component.
  Scope: CBraMod original endpoint arithmetic. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://arxiv.org/abs/2412.07236)
- [Code](https://github.com/wjq-learning/CBraMod)
- [Code](https://github.com/wjq-learning/CBraMod/blob/b9e961003214326972c567eff390e75b0287e32a/preprocessing/preprocessing_physio.py)
- [Code](https://proceedings.iclr.cc/paper_files/paper/2025/hash/bbbd6d915cb90be21c1254a82d45cedd-Abstract-Conference.html)
- [Code](https://raw.githubusercontent.com/wjq-learning/CBraMod/b9e961003214326972c567eff390e75b0287e32a/LICENSE)
- [Code](https://raw.githubusercontent.com/wjq-learning/CBraMod/b9e961003214326972c567eff390e75b0287e32a/README.md)
- [Paper](https://proceedings.iclr.cc/paper_files/paper/2025/hash/bbbd6d915cb90be21c1254a82d45cedd-Abstract-Conference.html)
- [Source](https://physionet.org/content/eegmmidb/1.0.0/)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
