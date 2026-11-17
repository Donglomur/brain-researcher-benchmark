# CBraMod: A Criss-Cross Brain Foundation Model for EEG Decoding

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-024`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Success:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule.

**Disposition:** source\_unresolved. The original CBraMod full twelve-dataset program has ordered decoding endpoints, but original cohort/split identities and a complete same-support baseline are unrecovered. The author explicitly disclaims exact split comparability for historical TUAB/TUEV comparisons and replaced their splitting code after publication. The current implementation's person-held-out 30%-label condition changes the original task and is only an extension. Recovering PhysioNet Table 3 alone cannot qualify this full-panel task.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition (calibration only)](historical/task.pre-improvement.v1.json)

Existing reproduction graders and pilot scores remain calibration evidence. They cannot establish paper improvement. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 18365 bytes; SHA-256 `140fcfa785133597faa18153c4c2ffaa19e2281ee47244ac8a41331fab24f6d8`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Implementation artifacts

- [Cbramod paired program](implementations/cbramod-paired-program) — Calibration only.
  Scope: Existing published source retained with its scientific scope. Source ownership does not establish equivalence to the complete task contract or current execution qualification. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.

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
