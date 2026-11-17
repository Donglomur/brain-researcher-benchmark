# Neural Encoding and Decoding at Scale

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-replacement-005`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 26106 bytes; SHA-256 `2b84b970780fb271fdfddaa2b459fc41f2db4580cccb923e81c6ded057fd0f3a`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Task implementation.
  Scope: Explicitly partitioned binned IBL trials to target-free task masks, a train-only prospective ridge reference, nine separate source-derived neural/behavior endpoints and paired comparisons retaining all 74 training and 10 heldout source session IDs. Exact ONE object membership/revisions, authenticated animal/probe joins, native eligibility/preprocessing/split and NEDS model parity, actual matched budgets, protected targets/tolerances, rights and scientific qualification remain held; complete generated coverage is not authentic population evidence.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/yzhang511/NEDS)
- [Code](https://proceedings.mlr.press/v267/zhang25bw.html)
- [Code](https://raw.githubusercontent.com/yzhang511/NEDS/61d2ef65556dbbc2b828d542f19bd4e7134c92f3/data/test_eids.txt)
- [Code](https://raw.githubusercontent.com/yzhang511/NEDS/61d2ef65556dbbc2b828d542f19bd4e7134c92f3/data/train_eids.txt)
- [Code](https://raw.githubusercontent.com/yzhang511/NEDS/61d2ef65556dbbc2b828d542f19bd4e7134c92f3/script/eval.sh)
- [Code](https://raw.githubusercontent.com/yzhang511/NEDS/61d2ef65556dbbc2b828d542f19bd4e7134c92f3/script/prepare_data.sh)
- [Code](https://raw.githubusercontent.com/yzhang511/NEDS/61d2ef65556dbbc2b828d542f19bd4e7134c92f3/script/train.sh)
- [Code](https://raw.githubusercontent.com/yzhang511/NEDS/61d2ef65556dbbc2b828d542f19bd4e7134c92f3/src/eval.py)
- [Code](https://raw.githubusercontent.com/yzhang511/NEDS/61d2ef65556dbbc2b828d542f19bd4e7134c92f3/src/prepare_data.py)
- [Code](https://raw.githubusercontent.com/yzhang511/NEDS/61d2ef65556dbbc2b828d542f19bd4e7134c92f3/src/train.py)
- [Code](https://raw.githubusercontent.com/yzhang511/NEDS/61d2ef65556dbbc2b828d542f19bd4e7134c92f3/src/utils/ibl_data_utils.py)
- [Paper](https://proceedings.mlr.press/v267/zhang25bw.html)
- [Source](https://openalyx.internationalbrainlab.org)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
