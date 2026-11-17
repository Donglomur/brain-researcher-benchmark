# Purkinje morphology: current local handoff

2 November 2026. Use the **submitted-program route** below for the complete released-tree numerical task. The adjacent README is an immutable historical description of the older artifact verifier, pinned in `authoring/delivery-integration-native-v1/FREEZE.json`. Its statement that candidate code is not executed does not describe this separately qualified program route.

The candidate starts with the [public TASK](../../../authoring/purkinje-morphology/program-completion-v1/public/TASK.md) and [SCHEMA](../../../authoring/purkinje-morphology/program-completion-v1/public/SCHEMA.json). The [public allowlist](../../../authoring/purkinje-morphology/program-completion-v1/registration/program_assets.json) identifies exactly 15 files: ten SWCs, cell metadata, exposed author totals, the declared source-semantics excerpt, TASK and SCHEMA. Supply only those files in the candidate workspace. This page, results, private references and the operator repository are not additional candidate inputs. A public-only folder is not an access sandbox.

One Python program runs as `python -I /program/program.py --input /input --out /output`. It writes five required files: `cells.csv`, `branches.csv`, `author_sections.csv`, `components.csv`, and `summary.json`. An optional `interpretation.json` is retained but unscored. Do not use the legacy artifact route's extra `reproduce.py` requirement. The program limit is 131,072 bytes, candidate time 60 seconds, memory 3 GiB, and aggregate output 8 MB; exact per-file caps are in TASK.

From the repository root, an operator can inspect the registered command without dispatch:

```sh
python3 tools/neurobench.py run PAPER-FIND-REP-013 \
  --program /absolute/path/to/program.py \
  --output artifacts-build/fresh-purkinje-attempt \
  --review /absolute/repository/path/to/current-review.json \
  --other-reserve-bytes 102000000 --dry-run
```

All paths must exist where required, and output must be fresh. Removing `--dry-run` invokes the verified program wrapper only after a new operator allocation and current review are in place. The review is a repository file binding the exact program, source freeze, qualification, output, latest cost and current capacity. The shown other-reserve value is the minimum example, not a current allocation. The whole attempt is 150 seconds with 24 MB durable reserve. Historical reviews and their counters are not reusable grants.

Read `<output>/score.json` together with `<output>/outer_receipt.json`; captured candidate files are under `<output>/unit/`. The score retains all 31 numeric fields and 58 summary diagnostics, full topology and missingness coverage, and both caliber conventions. Equal-cell branch-length RMSE alone is insufficient: a wrong-caliber control has zero branch-length error. There is no ordinary accuracy floor or scientific-insight reward.

An [independently authored program](../../../authoring/purkinje-morphology/independent-program-runtime-policy-v1/RESULTS.md) completed all ten trees and 13 components with exact identities and only numerical-roundoff discrepancies. That is implementation-independence evidence, not a blinded LLM trial. The same-source ordinary/common-command qualification is preserved separately in [registration results](../../../authoring/purkinje-morphology/program-completion-v1/registration/RESULTS.md).

This bounded task audits released tree geometry and source discrepancies. It does not resolve H13 raw/export disagreement, historical caliber-state ambiguity or mouse-donor mapping, nor complete the original species/Sholl/spine/regional/allometric investigation, access-effect study or improvement phase. Those commitments remain under the same PAPER-FIND-REP-013 ID. See the [four-task guide](../../../docs/neuroscience-benchmarks/BOUNDED_LOCAL_TASKS.md) for the distinction between local usability and full-contract admission.
