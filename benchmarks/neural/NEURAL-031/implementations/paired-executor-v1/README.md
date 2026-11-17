# NEURAL-031 complete targets and isolated paired program execution

This component connects the accepted paired delivery and ratio scorer. It adds
the missing private-target format bridge and a Docker executor for one frozen
submitted Python program across all 40 mouse/view contexts. Neither accepted
projection nor scientific scoring equations are changed.

This task uses **processed baseline morphology and coactivity measurements**.
It measures what a submitted analysis program can predict. It is not direct
neural waveform perception, a native viewer task, or a reproduction of the
paper's pooled retrospective correlation statistic.

The complete population stays fixed: 27 source members, 20 mice, 1,143 original
rows, 774 baseline-defined requests in each condition, 731 observed ratios and
43 requested observations whose follow-up is unavailable. Every request needs a
prediction. Follow-up/baseline volume is dimensionless; ratio 1 is no change,
observed zero remains zero, and unavailable targets are not scored as zero.
The unchanged endpoint reports equal-mouse baseline MAE minus neural MAE, both
absolute arms, per-mouse results and strata, no-change and training-only
mouse-balanced median controls. Negative gain is valid. Overlapping training
sets do not make these 20 independent experiments.

## Exact private target bridge

`targets.py` authenticates the original private NPZ, complete row census and
public support against fixed independent source descriptors in
`TARGET_SOURCES.json`. There is no CLI override for these descriptors. It accepts
only the seven original float64/int64 vectors with all 1,143 rows, verifies the
source-member/mouse/compartment and eligibility joins, maps unavailable NaN to
JSON null, and calls the unchanged target validator. It preserves existing
ratios; these operands do not contain original volumes for fresh division.

```sh
python -I -B targets.py --targets-npz /operator/original/private/targets.npz \
  --row-census /operator/original/private/row_census.jsonl \
  --support /operator/paired/support.json --output /operator/fresh-private-targets
```

The fresh directory has mode 0700 and contains mode-0600 `targets.json` plus
`TARGETS_RECEIPT.json`, which records the new target digest. The complete
authentic conversion and its joins against all 40 existing input contexts ran
once on 2026-11-17 and passed independent saved-output review. The compact
[validation receipt](AUTHENTIC_VALIDATION.json) binds the exact source, protocol,
outputs and acceptance. Private targets remain outside Git, and the public
executor never receives their paths as participant mounts.

## One frozen program, 40 fresh contexts

`executor.py` starts the original **480-second whole-batch monotonic deadline**
before program capture. It copies the supplied program once and freezes its
hash and method declaration before opening any query context. It executes
`fold00/baseline`, `fold00/neural`, through `fold19/neural`, without resetting the
clock or imposing arbitrary per-context compute slices. Setup, exports,
execution, capture, removal and complete collection all count against the same
deadline. Protected scoring is a subsequent operation.

Each context reuses the accepted single-context exporter and mounts only three
readonly files: its own `data.npz`, its own `manifest.json`, and the frozen
`submission.py`. It never mounts the paired store, support file, repository,
another fold, private targets or earlier outputs. This matters because another
fold's training labels contain the current query mouse's answers. Baseline
archives physically lack neural-valued columns; common predictors and
missingness indicators remain identical across information conditions.

The production backend uses an existing immutable local Linux Docker image ID,
not a mutable tag, and never pulls an image. It rejects image-defined volumes
and unexpected inherited environment variables. It inspects the actual context
configuration and mount identities, including a readonly root filesystem,
network disabled, no added capabilities, non-root user, no-new-privileges,
3 GiB memory with no additional swap, and 1.75 CPU. It provides a bounded tmpfs
output and a temporary filesystem charged to the same 3 GiB memory limit.
There is no unrestricted host-process fallback.

The lifecycle deliberately keeps tmpfs alive until capture: start a minimal
keeper, execute the submitted program, require normal exit, pause and verify
the whole container, capture a bounded output tar, remove the container, and
successfully query its absence. Pausing freezes surviving descendants before
capture. The tar parser permits only the prediction file and optional output
root, with inert timestamp metadata; links, special files, path overrides,
duplicates, extra payloads and trailing nonzero bytes are refused. Only after
removal is the captured output committed and the next context started.

The original submitted invocation remains:

```text
/usr/local/bin/python -I -B /program/submission.py --input /input/data.npz --manifest /input/manifest.json --output /output/predictions.json
```

The keeper, PID ceiling of 256, 1 MiB output tmpfs and failure recovery policy
are prospective implementation details requiring actual runtime qualification.
They are not inferred historical measurements or new scientific success rules.
On failure, only a resource carrying the exact owned batch label can be removed.
A bounded 10-second emergency cleanup attempt may extend past an exhausted
batch clock; that is recorded as failure and receives no successful-batch
credit. Unknown cleanup, an unresponsive daemon or a surviving producer prevents
the next context and protected scoring. No automatic retry occurs.

## Operator interface and scoring barrier

The method JSON uses schema `neural031_frozen_program_method_v1` and contains
`program` (`bytes`, `sha256`), a nonempty `method` description,
`same_method_across_views: true`, `training_only_selection: true`, and the exact
`image_inventory_review_sha256` and `method_review_sha256`. Those are frozen
operator declarations. Identical source and declarations do not independently
prove a matched scientific procedure: code can branch on the view or degrade a
baseline deliberately. Image inventory and matched-method review remain external
requirements for scientific qualification.

```sh
python -I -B executor.py --store-root /operator/existing-paired-store \
  --program /operator/submission.py --method-json /operator/method.json \
  --image-id sha256:EXACT_REVIEWED_LOCAL_IMAGE_ID \
  --output-root /operator/fresh-attempt
```

This command executes a candidate and requires a separately admitted runtime;
it was not run during construction. Add `--targets` and `--targets-sha256` only
for an admitted protected scoring operation. The code first collects and
validates all 40 outputs, confirms producer absence, and only then calls the
unchanged scorer. It never stats, hashes or opens a target path before that
complete public-output barrier. The scorer independently repeats public output
validation before its first private target read.

Outputs are operator-only: frozen program/method, exact exported inputs,
captured predictions, complete `collection/submission.json` and support, and
`BATCH.json`. Failed runs retain `FAILURE.json` and never become accepted
collections for protected scoring. A receipt written just before a late deadline
failure is renamed `UNACCEPTED_BATCH.json`. This component does not register a
runtime or automatically promote benchmark readiness.

## Construction evidence and remaining work

There are 34 distinct passing construction controls: 16 target tests and 18
executor tests. The target duplicate-ZIP control was corrected and rerun once,
giving 35 passing executions. `TESTING.json` records the exact runs and their
limits. Run the complete generated suites from this directory with:

```sh
python -I -B tests/test_targets.py -v
python -I -B tests/test_executor.py -v
```

These commands need Python and NumPy, and do not require Docker. Both suites
reclaim their generated disk fixtures; observed cumulative writes and removals
totaled 1,266,833 bytes. They are construction checks, not candidate benchmarks.

Generated target controls cover the full panel, source/census joins, null/zero
semantics, bounded archives, counterfeit source rejection and unchanged scorer
interoperability. Executor controls use explicitly simulated Docker command
transport and generated observations, including malformed final outputs,
cross-context mounting attempts, frozen-source changes, deadline and removal
failures. Simulated transport cannot establish actual container isolation,
daemon behavior, candidate feasibility or runtime resource enforcement.

The later authentic target/input validation retained all 1,143 rows, 774
requests, 731 observed ratios and 43 unavailable requested targets. Every one
of the 40 existing contexts matched the new private JSON: 29,412 training-label
joins and 1,548 query identities. It reused the original projection and wrote
139,739 bytes of private targets and receipts. This cohort has no observed-zero
ratio, so zero preservation remains supported by generated controls.

`TESTING.json`, its recorded source pins, and `SOURCE_POLICY.json` construction
boundaries preserve the original construction checkpoint. The additive
`AUTHENTIC_VALIDATION.json` records the subsequent authentic check. No candidate,
Docker execution, model fit or scientific score was performed. Remaining steps
are an exact image/runtime inventory, actual full lifecycle and isolation
qualification, and an admitted complete matched-method study. Target/input
compatibility does not establish those results or whole-benchmark readiness.
