# Frozen submitted program for the complete Indy day-pair task

This companion connects the existing NEURAL-023 public delivery to the existing full-support artifact scorer through a concrete isolated program transport. It adds an executable operator route for a submitted analysis program. **This source release has generated software controls only. No authentic candidate run, Docker qualification, model result, native neural-understanding result, or registration promotion is claimed.**

The task is unchanged: all 22,091 assessment endpoints, IDs 3010 through 25100, from the exposed Indy 2016-10-05 → 2016-10-06 pair; 96 spike-count channels; signed x/y trailing-20-ms finger velocity in metres per second. Source-day labels and the 60-second next-day calibration are supplied. The whole assessment count batch is visible, including later counts. This is retrospective batch decoding, not a past-only, unseen-animal, direct-observation or viewer task. NEURAL-023 assessment counts expose NEURAL-024 future-neural targets, so the latter cannot be called hidden after this exposure.

`DEPENDENCIES.json` pins 14 existing files from accepted commit `31c05a9d2675c7d4235f7a8a0df88c88981b9395`: the unchanged eight-file NEURAL-007 concrete Docker transport closure and six NEURAL-023 asset/scoring files. No shared source is copied or edited. The four public operands total 17,695,879 bytes; their identities are fixed by the accepted scorer's `ASSETS.json`. They are provisioned separately and are not included here.

The candidate is one Python file, at most 65,536 bytes, accepting `--input /input --out /output` and producing `predictions.npz`. Its exact arrays remain `case_id[22091]` and finite `velocity_m_s[22091,2]`. Each endpoint must appear once; row reordering is accepted. The existing 1,000,000-byte compressed and 600,000-byte expanded submission limits still apply.

## Execution sequence

1. `stage` snapshots the submitted program and the container worker into fresh read-only files. It publishes `SOURCE.json` and `PROGRAM_COMMIT.json` before preparing public input bindings. The stage does not read public numerical payload bodies and does not inspect private operands. This is a freeze before execution exposure, not proof that the author never saw public data previously.
2. `EXPOSURE_REQUEST.json` supplies the exact six proposed mounts: four public files, candidate source and worker source. It is a review request, **not** an approved exposure record. An independent operator must supply the existing transport's exact approved image inventory and boundary record for this source, image, command and mount set. The program never approves its own exposure.
3. `run` checks the pinned plan, source, dependencies and exact exposure; claims the stage once using exclusive `ATTEMPT.json`; and invokes the existing concrete Docker `Provider`. There is no host candidate fallback, image pull, installation or network. The candidate sees no repository, scorer, targets, saved reference metrics, host socket or public directory containing extra files.
4. The transport validates a natural successful producer exit, removes the producer before capture, captures the complete manifest-bound output through its trusted holder, removes all owned resources, and publishes an immutable receipt. The adapter re-observes that receipt and checks its request/source/mount identity and complete closure before accepting the captured NPZ.
5. The original full-panel NPZ validator rejects malformed, missing, duplicate or nonfinite endpoints before either operator operand is inspected. The scorer's second submission snapshot must match the same captured transport pin, so a later path mutation fails before private reads. Then the unchanged artifact scorer loads its pinned references and targets and writes the original mean-axis R², per-axis scores, MSE/MAE, eight descriptive clock blocks, seven signed reference comparisons and arithmetic audit. A negative R² is valid. No improvement threshold is added.

The worker's `RESULT.json` is an untrusted container report; it is never evidence of isolation or scientific correctness. Only the external transport establishes its documented closure boundary. Its current host/daemon behavior still needs a separately authorized qualification. Public-source contamination, metadata priors and input dependence are not resolved by successful execution.

## Operator commands

Use an existing qualified environment with Python and NumPy, an already installed local immutable scientific image, an existing local Docker Unix socket, sufficient leased resources, and independent exact exposure approval. These are future execution instructions; the source review did not provision or qualify them.

```sh
python3 -I -B /absolute/checkout/benchmarks/neural/NEURAL-023/implementations/submitted-program-v1/run.py stage \
  --repository /absolute/checkout \
  --candidate /absolute/submitted.py \
  --public-root /absolute/provisioned-public \
  --output /absolute/fresh-stage \
  --image sha256:REPLACE_WITH_64_HEX_LOCAL_IMAGE_ID
```

Retain the printed plan byte count and SHA-256 outside the stage. Review the generated exposure request against the exact image inventory and source. Supply an operator configuration containing only these fields (example paths are placeholders):

```json
{
  "docker_binary": "/absolute/docker",
  "docker_socket": "/absolute/local-docker.sock",
  "control_root": "/absolute/preprovisioned-private-control",
  "quarantine_root": "/absolute/preprovisioned-private-quarantine",
  "exposure_path": "/absolute/independently-approved-exposure.json",
  "exposure_pin": {"bytes": 1234, "sha256": "REPLACE_WITH_EXACT_APPROVED_FILE_SHA256"}
}
```

The control and quarantine roots must be existing, disjoint, operator-private directories. The transport's existing `osl_transport_exposure_v1` record requires exact role `A`, source pin, immutable image ID, command, mount identities, approved image-inventory hash, boundary-audit pin and verified role boundary. No CLI switch bypasses these checks.

```sh
python3 -I -B /absolute/checkout/benchmarks/neural/NEURAL-023/implementations/submitted-program-v1/run.py run \
  --repository /absolute/checkout \
  --stage /absolute/fresh-stage \
  --plan-bytes PRINTED_BYTE_COUNT --plan-sha256 PRINTED_SHA256 \
  --configuration /absolute/operator-configuration.json \
  --target /absolute/operator-only/assessment-targets.npz \
  --reference /absolute/operator-only/reference-metrics.json \
  --output /absolute/fresh-lifecycle-output
```

Private target/reference path strings are passed only to the trusted operator process; they never enter the candidate plan or mounts. The scorer's original expected identities cannot be overridden through this interface.

## Bounds and failure handling

This is a newly declared execution profile, not inherited historical timing qualification. Candidate compute remains 20 seconds, 1.75 CPUs and 3 GiB RAM. The captured transport enforces one numerical thread, 64 PIDs, 64 MiB private scratch and an 8 MiB output volume. Its separate holder has a 128 MiB memory limit and one CPU; this differs from the historical 0.25-CPU holder. Only `predictions.npz`, `RESULT.json` and `OUTPUTS.json` may be exported; the old allowance for extra diagnostic files is not retained.

The phase reserves 30 seconds for setup, 20 for producer work, 15 for capture and 15 for cleanup within an unchanged 90-second clock. It allows at most 128 bounded Docker CLI calls, 8 MiB CLI replies, 96 MiB transport reads and 8 MiB transport host writes, plus at most 256 KiB observer reads. The dedicated operator command has a 120-second wall timer and at most 20 CPU seconds, respecting a tighter inherited limit. The scorer gets at most 30 remaining wall seconds. The transport retains actual byte counters and explicitly does not infer producer logical I/O or exact peak RSS. Limits are ceilings, not measured authentic costs.

Read `LIFECYCLE.json`, the pinned transport receipt and, when present, `grade/receipt.json`. A missing receipt, `operator_error`, failed closure, timeout, invalid submission or partial directory is not a completed scored run. The stage is consumed once even after a failure; there is no automatic retry. The transport durably records exact owned resources for its existing parent-only `recover` method. Recovery requires the original ownership/request pins, remaining original allowance and independently established controller closure; this wrapper does not discover arbitrary containers, kill unrelated jobs or extend a failed deadline. If a controller was forcibly lost or cleanup remains uncertain, stop and obtain a separately authorized recovery allocation before further work.

Sixteen generated controls check full reordered support with the original metric code, valid negative scores, incomplete/duplicate/nonfinite/malformed submissions before private reads, unclosed producers, receipt changes, extra outputs, mutations before capture admission and between validation and scoring, source mutation, injected mounts, wrong exposure approval, stage-only behavior and refusal to retry. The transport is a fake only in these controls; the production CLI selects the concrete pinned provider. The controls do not qualify Docker or establish AI performance. Run them locally with:

```sh
python3 -I -B /absolute/checkout/benchmarks/neural/NEURAL-023/implementations/submitted-program-v1/test_run.py
```
