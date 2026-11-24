# Complete full32 image reference

This component adds a single-reference execution and evaluation path for the unchanged [four-demo image method](../four-demo-image-reference-v1/README.md). It produces no direct/model arm and no paired receipt. It closes a source-path gap; it does **not** establish authentic classification performance, a competent scientific baseline, model performance, or a new completed benchmark.

The scope is the existing `erp-core-remaining-persons-released-marker-v1` condition: all 6,400 events from the predefined 32-person complement to six feature-training and two development people. Each person contributes 200 events. This is distinct from the original 400-case/two-person development condition and from the whole 40-person source collection. The 32-case exploratory pilot and an unselected 640-case proposal cannot substitute for it.

The fixed algorithm is `four-demo-image-reference-v1/reference.py`, 14,509 bytes, SHA256 `08286eaab4be66d2dc66f646f475a851ab861ac0337279a5696faefbd9c8bfd6`. Its missingness, clipping and classification behavior remain unchanged. The original programme and pilot results are untouched.

## What the runner does

1. **Freeze:** authenticate the source closure, original public manifest/roster, runtime and four externally pinned old demonstration PNGs. Extract features from those four images through the unchanged method, fit exactly once and save an immutable model before opening any query image. The ordered demonstration labels remain 0, 1, 0, 1; the six-person feature bank and natural class prior are unavailable. A failed fit retains failure evidence and grants no retry.
2. **Check demonstration correspondence:** after the model freezes, open the authenticated full32 public packet and render its fixed four demonstrations. Require exact PNG equality with the fitting inputs before processing a query. This closes the gap between a caller-supplied image descriptor and the packet's fixed demonstrations. The original demonstration JSON identity is pinned independently.
3. **Run all cases:** use the original raster and lossless codec at the initial state: Cz/Pz, gain 20, samples −256 through 767, no display filter or actions. Retain every query PNG. Refuse compressed images above 64 KiB; do not alter or resample them. Each query gets a fresh owned child running the unchanged `predict` CLI through a framing wrapper. Only the exact algorithm, frozen model and current PNG are added to the existing sandbox's literal read permissions.
4. **Admit every case before targets:** independently regenerate all 6,400 original fixed views, match the retained images and display/codec records, and validate first stdout, complete bounded stderr, context/model/source binding and owned cleanup. A missing, duplicate, failed, changed, invalid or generated-only response refuses the full arm. Only after all admissions pass does the evaluator call the original protected private-join loader and metric kernel.

The collector preserves the full32 failure rule: an incomplete arm has no complete score. It does not import the exploratory pilot's errors-as-wrong endpoint. There is no count override, automatic retry, case replacement, class balancing, per-query fitting, cross-query adaptation or fabricated second arm. Create-only outputs prevent accidentally overwriting the same attempt. The trusted operator must retain failures and must not relaunch into a new directory as an undeclared retry.

The retained `INITIAL.json`, per-case `START.json`, captures and completion records provide partial evidence if a run fails. `ARM.json` exists only after all 6,400 successes. Interruption is unwound through the existing owned-child cleanup. If a hard OS interruption or exhausted closure budget prevents final failure-writing, the durable earlier records remain; missing finalization never implies success.

## Metrics and interpretation

The unchanged original metrics are equal-person balanced accuracy at `p >= 0.5` and equal-person natural-log loss with metric-only clipping at `1e-15`. All 32 person rows are retained and each protected join must contain 40 targets and 160 standards. The analytic constant-0.5 comparator has balanced accuracy 0.5 and log loss `ln(2)`. No competence threshold or uncertainty interval is invented; the existing paired bootstrap cannot be reused for one arm.

The target is experimental target-versus-standard event identity, not physiological P3 presence. Prior exposure remains explicit: the 32-case pilot covered every person, the image method followed aggregate results/clipping failures, and the numerical reference has already been graded on the full cohort. A future run can withhold current-run targets until predictions freeze. It cannot make this cohort untouched or establish independent generalization. Numerical-waveform reference results have different input information and are not same-image comparisons.

## Use after separate execution selection

The operator requires Python 3.10+ for the maintained full32 interfaces. The standard-library prediction child was tested with the existing macOS system Python. Production requires the pinned `/usr/bin/sandbox-exec` boundary; there is no unsandboxed fallback. One query child runs at a time, in addition to its coordinator and bounded stderr-reader thread. RAM/CPU hard quotas, escaped-descendant containment and full authentic execution remain unqualified.

`SOURCE_BINDINGS.json` freezes the adapter/client and all selected public dependencies. Stage source/runtimes must match those pins. `freeze` accepts an explicit JSON specification; the resulting `CONTRACT.json` freezes model, input, runtime, source and budget identities. There are no implicit default data locations.

```sh
python adapter.py freeze --input FREEZE_SPEC.json --input-bytes BYTES \
  --input-sha256 SHA256 --output /absolute/fresh-freeze
python adapter.py run --input /absolute/fresh-freeze/CONTRACT.json \
  --input-bytes BYTES --input-sha256 SHA256 --output /absolute/fresh-run
python adapter.py evaluate --input /absolute/fresh-freeze/CONTRACT.json \
  --input-bytes BYTES --input-sha256 SHA256 --arm /absolute/fresh-run \
  --arm-bytes ARM_BYTES --arm-sha256 ARM_SHA256 \
  --private-material /absolute/trusted-private-descriptor.json \
  --output /absolute/fresh-evaluation
```

The private descriptor file is read lazily inside `evaluate`, after complete public admission; it is not parsed by the CLI at startup. The operator must keep the packet/private material and outputs outside runtime-readable roots. Runtime and per-file content pins do not independently certify the surrounding OS or prove unknown prior/pretraining exposure.

The freeze specification fields are `schema` (`erp-full32-image-reference-freeze-spec-v1`), `repository_root`, `source_bindings`, `public_root`, `public_manifest`, `demos`, `demo_export_provenance`, `interpreter`, `sandbox`, and `limits`. Each demo has absolute `path`, `file` (`bytes`, `sha256`), ordered `record` (`demo1`–`demo4`) and `label`. `demo_export_provenance` is the accepted export receipt's content descriptor; it is an operator declaration, with actual pixel-to-packet correspondence independently verified before queries and again before scoring. Executables have absolute `path`, `bytes`, `sha256`. The public manifest is the exact pinned full32 packet; a different packet is refused.

`limits` contains `freeze`, `run`, `evaluate` allocations, each with `read_bytes`, `write_bytes`, `work_seconds`, `closure_seconds`, `episode_work_seconds`, `episode_cleanup_seconds`. Their cumulative ceilings are 1 GiB artifacts, 16 GiB charged reads, 3,600 work seconds and 600 closure seconds. These are prospective upper bounds, not measured authentic costs or grants to execute. Read accounting includes a conservative 32 MiB source/import allowance per stage, 1 MiB plus repeated source/model/image reads per child, actual packet/capture reads, and 16 MiB reserved for protected joining; it is not syscall-complete I/O telemetry.

A complete future operation needs four accepted demo image pins, pinned executable identities, fresh disjoint output paths, a separately selected cumulative resource admission, and a trusted private descriptor. Complete image regeneration and the second rendering pass during admission are required. No authentic fit, prediction or protected score has been run for this component.

## Generated controls

```sh
python -B test_adapter.py --repository-root /absolute/repository
```

The controls cover the full 6,400-row generated inventory and original 32-person metrics, missing/duplicate/invalid/reordered responses, target-last refusal, duplicate private joins, exact generated query/demo equality with the original viewer, fixed image-cap refusal, demo-source mismatch, narrow sandbox permissions, immutable file pins, unchanged CLI execution under the real macOS sandbox, invalid-model-before-query ordering, extra stdout and generated-capture exclusion. They use no authentic packet, image, prediction or target.

The first operator test used Python 3.9 and failed on the maintained strict-zip requirement. The adapter now rejects that operator version early. The existing Python 3.11 environment passed the generated suite, including the macOS sandbox control. Generated controls establish those engineering behaviors only; they are not a small authentic trial or evidence of classifier competence.
