# Actual operator and source API

`neural080.py` is the new CLI. Preparation, staging, execution and comparison are separate process invocations. The execution parent uses ordinary Python/stdlib only; it must not inherit BLAS/PyTorch worker threads before installing process limits. `--help` is inert. The scientific operations are future entry points, not commands authorized or run during source construction.

Each phase accepts an explicit absolute configuration file, exact byte count and SHA256, a fresh output directory, and explicit JSON logical limits with `read_bytes`, `write_bytes`, `retained_bytes`, and `attempts`. No default allowance or qualification flag exists. Configuration and input JSON use the accepted strict decoder and no-follow, exact-byte capture. The CLI grammar is:

```
python3 -B neural080.py PHASE --config ABS_CONFIG --bytes N --sha256 HEX --output FRESH_OUTPUT --logical-limits JSON
```

`PHASE` is `prepare`, `stage`, `execute`, or `compare`. Preparation additionally requires `--roots JSON`, with metadata, recordings, media, logs and checkpoint roots. The actual source validators define closed schemas; no example authority/provider document or invented study-input manifest is supplied.

## Preparation

`operator.prepare(config_root, config_descriptor, roots, output, owner)` captures the complete graph/map/evidence, independently joins donor namespace plus identity and identical-media components, binds the raw graph descriptor across roles, validates original derivative history and the fixed target basis, reads all actual presentation logs, and produces the complete unscaled private recording pool. It publishes the exact target units/reference/clock/preprocessing contract alongside the original pool manifest, without replacing the preserved predecessor's source or output.

Preparation selects `full_svd_materialized` or `streamed_dual_certified` explicitly. The first calls the complete feature producer and binds its actual manifest. The second captures a `STREAM_INPUT.json` selection and creates a dedicated four-body feature metadata tree preserving the original relative paths. It does not create the approximately 265 GB learned-feature collection. The ordinary source map's media/evidence identities remain the same in both branches. Original preparation metadata containing recording/join roles is never mounted wholesale into a candidate.

The source-map schema requires all 1,102 ordered identities, exact media descriptors and expansion capacities, explicit rational clip origin, actual container/stream roles, original experimental basename, full provenance namespace/identity, and the verified silence branch. Its identity and audio bodies must independently join every original row. The graph loader captures all selected provenance evidence; a descriptor is not evidence of the provider's authenticity or discovery completeness.

`recordings.prepare_unscaled` uses the unchanged accepted recording/native/take readers and native signal projections. It never fits a held-person EEG normalization. Original whole-record artifact/ICA provenance is admitted only under the explicitly disclosed derivative profile; unknown preprocessing is unavailable. `clocks.produce` calls the complete unchanged MAT reader, joins every retained EEG/eye coordinate and annotates software timing limits.

## Staging and programme identity

`campaign.stage` reads the exact prepared manifest and deterministic assignment. The materialized branch captures complete feature bodies; the streamed branch stages only the personal operands and actual stream selection. Small nonlearned shared blocks are regenerated inside the worker, while learned blocks remain streamed. Each view contains exactly its TRAIN+QUERY personal covariates and TRAIN EEG, with full ordered coordinates and original-unit typing. No query EEG is published. `CASE.json` and `CONTEXT.json` bind the source assignment, prepared/pool identity, selected backend and whole programme tree.

The supplied source tree must include the fixed CLI and regular package initializer and every selected source member. Streamed execution binds the exact canonical source-tree member digest and all actual imported producer origins. The private source bootstrap, readonly complete tree and immutable host provisioning are necessary: rereading origin files alone does not prove what a previously loaded code object executed or detect adversarial ABA mutation.

Execution re-admits the exact closed CASE-derived view roster. Extra files cannot enter `/view` through a forged staged manifest. Stream mounts contain exactly the 1,102 selected media files, the one selected checkpoint, and the four feature metadata bodies; extra private files are rejected. Other ordinary tool roles are explicitly selected and pinned before fitting. Tool metadata does not prove absence of memorized labels or previously fitted state; programme/tool exposure eligibility requires independent review.

## Reference, supplied decoder and candidate calls

`models.capture_case_features` scopes personal rows to the actual case, and `capture_training_targets` snapshots only TRAIN EEG. `reference.run_outer` performs every selected nested fit and final refit, records complete support/selection/cost observations, and publishes all seven original-unit predictions. `reference.output_names` derives the finite output contract, including streamed pass ledgers, before launch; capacity insufficiency refuses before an unbounded allowlist is allocated. The fullSVD and streamed dual branches share the same ridge/selection programme and risk definition.

`feature_stream.ActualFeatureStream.columns` accepts a concrete typed source selection, not a replacement feature callback. Every requested range regenerates all full producer values, checks complete row hashes against the first completed pass, retains all 1,102 identities and costs every repeated read/forward. `dual.fit` consumes every selected column, fits only the unique TRAIN videos, records explicit conditional numerical bounds and computes all prediction scores in that TRAIN basis. Compact scaler/second-center state is reconstructable only through metered exact-source replay and hash verification.

The supplied decoder closure contains actual fitted numeric states and TRAIN-fitted feature scores, never protected reference EEG predictions. The generic condition receives no supplied fitted decoder. The augmented condition receives only the exact permitted fold closure mounted separately under `/tools/decoder`, with a concrete captured-state prediction API. The entire reference output directory is not mounted. Decoder-only comparison rows point to the original FULL reference bank rather than triggering repeated baseline execution.

The complete future execution calls are 30 reference jobs plus 120 candidate jobs. Each candidate must publish one `PREDICTION.npy` in original EEG units on exactly the ordered case query coordinates. Both modes and both tool regimes use the same whole FULL-arm budget. Common preparation is allocated equally over the 30 outer cases with exact totals; augmented agents additionally pay the whole case-specific FULL decoder construction cost. Remaining process allowances are conservative after debit. Fixed scientific controls are separately accounted, and no five-arm allowance is transferred.

Before any reference fit or worker launch, `campaign.require_matched_resource_envelope` checks the actual typed `runner.Limits` objects. The reference FULL decoder and generic candidate must match `address_space_bytes`, `file_bytes`, `tmpfs_bytes`, `open_files`, `processes`, `threads`, `seed`, `poll_seconds` and `cleanup_seconds`. The complete typed field roster must be partitioned exactly: `cpu_seconds`, `wall_seconds`, `output_bytes`, `output_members`, `stdout_bytes`, `stderr_bytes`, `report_bytes`, `intake_bytes` and `intake_members` are the separately declared additive/capture allowances. The complete seven-arm reference may need larger totals in that latter group. No larger memory, concurrency or scratch envelope is accepted as a control-job allowance. This source invariant repairs N080-W02; actual native/aggregate enforcement and end-to-end accounting remain unqualified.

## Actual process boundary and limits

`runner.run_case` is Linux-only and requires an unprivileged dedicated single-threaded launcher, exact executable/runtime/source/tool manifests, and explicit limits. It uses the inspected bubblewrap API, checked descriptor mounts, isolated namespaces, cleared environment, readonly inputs, a sized `/tmp`, fresh output/log roots, process limits, bounded stdout/stderr, finite output admission, and independently attempted process/FD cleanup. It retains the raw first error and subsequent cleanup observations. Partial outputs are retained, not silently deleted.

All runtime limits are explicit: whole wall and cleanup reservations, polling, CPU, address space, file size, descriptor/process counts, stdout/stderr, output aggregate/member limits, intake limits, report size, threads, seed, and tmpfs size. These fields are ordinary selected capacities, not a certificate. A provisioned Python and loader-library tree must contain finite ordinary regular members; no installation or broad host runtime discovery is performed.

The source does not convert per-process rlimits into a tree quota, output polling into a disk quota, or direct bubblewrap-monitor wait4 into complete job CPU/RSS. The binary's reproducible-build relation to inspected source, actual kernel behavior, aggregate cgroup accounting, external wall supervisor and immutable host provisioning remain empirical gates. Observed in-process budget debits are developmental diagnostics until those end-to-end obligations are independently qualified.

## Protected capture and comparison

`artifacts.capture_panel` admits the complete fixed reference and four candidate panels before opening any private target binding. It captures 330 distinct predictions, 30 means and 30 sigmas, plus source-panel and fit-support metadata. `CapturedPanel` is only a locator. `scoring.compare` re-admits all bodies, checks the exact prebound private pool, and verifies each reference TRAIN target identity and scale against the actual original pool rows. Reordered training targets cannot establish a different fixed baseline while preserving only its moments.

Only after complete admission does the scorer open private EEG. It divides original-unit residuals by exact outer-TRAIN sigma once, uses all fixed coordinates, and produces complete video/family/person reductions, signed contrasts, four separate candidate improvements, fixed sensitivities and shared conditional resamples. There is no best-success subset, best-tool-cell substitution, inferred fresh case or registration output.

The original accepted diagnostic remains available through its unchanged `source/private/OPERATOR.md` and original source APIs. It is an exposed-development diagnostic with its own exact denominator, not a shortcut to the new complete programme.
