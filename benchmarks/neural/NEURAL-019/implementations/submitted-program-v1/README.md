# NEURAL-019 submitted-program route

This component connects the complete registered MC_Maze development panel to the unchanged movement scorer through an isolated submitted-program lifecycle. It replaces the missing published authoring entrypoint with an explicit-path operator route. **Source and generated controls do not qualify the current Docker host, scientific image, authentic execution, or participant performance.** No registration or existing implementation is changed.

The task remains one exposed Jenkins macaque/session: **1,340 labeled training trials from 28 maze groups, four training group folds, and all 126 assessment trials from eight other maze groups**. This is the existing grouped-holdout adaptation, not the official NLB leaderboard split/readout or the entire raw source corpus. Each trial retains 140 bins and all 137 neural units. The two public files total 59,349,239 bytes and retain their original fixed hashes. The assessment endpoint is signed x/y velocity in m/s on the source-lagged clock, −150 through 545 ms in 5 ms steps. Symmetric preprocessing and the 100 ms lag make this retrospective, not an online decoder.

The public packet contains all training counts/velocities and assessment counts. The programme instructions require training-only preprocessing, fitting and selection. A source freeze and successful score do not establish that arbitrary submitted code obeyed that rule: assessment counts are accessible during the whole batch. Accuracy does not establish a matched latent-representation comparison, biological mechanism, native LLM understanding, population generalization or SOTA. Prior NEURAL-017/018 exposure and the historical reference evaluation remain disclosed.

## Candidate interface and custody

Submit one UTF-8 Python file of at most 65,536 bytes. The worker calls:

```text
python -I -B /program/program.py --input /input --out /output
```

The candidate receives only the two pinned public files, its source, the task worker, the transport's public request metadata, the existing approved image and bounded writable scratch/output. It receives no repository, raw NWB, operator identity map, assessment targets, prior predictions, reference report or Docker socket. No pull, installation, network or host candidate fallback is available.

The candidate must write exactly `predictions.npz`, at most 1,048,576 bytes, containing the original six fields:

| Field | Complete required value |
| --- | --- |
| `velocity` | Finite signed float32/64 `[126,140,2]`, m/s |
| `trial_ids` | Every original anonymous assessment ID once; reordered rows allowed |
| `velocity_left_edges_ms` | Exact original 140-bin velocity clock |
| `velocity_axes` | Unicode `['x','y']` |
| `velocity_units` | Unicode scalar `m/s` |
| `panel_fingerprint` | Exact original public fingerprint |

The unchanged bounded NPZ parser also enforces its 1 MiB expanded inventory, supported headers/CRC, units, clock, complete identities and finite values. Extra candidate files, links and special files are refused. After the child exits, the worker adds transport-only `RESULT.json` and `OUTPUTS.json`; these are untrusted output declarations, not scientific or isolation evidence. The transport independently checks the complete inventory after removing the producer, so late writes cannot become unchecked outputs.

`stage` snapshots the candidate before preparing public bindings. It publishes a source commitment and an exact exposure-review request without reading public numerical payload bodies or granting approval. The independent operator supplies the existing transport's approved image inventory and exact source/command/mount boundary record. `run` verifies that approval and the pinned plan, consumes the stage once, invokes the concrete provider, and independently re-observes its receipt. Producer removal, complete owned-resource cleanup, original deadline and exact source/mount/output identities must all pass before grading.

The captured prediction pin remains binding during the original scorer's second read and private temporary copy. A valid replacement NPZ inserted after capture is rejected before any private operand is resolved. The unchanged scorer then validates all six fields, authenticates all four reference streams and their recorded lineage, and loads the complete targets once. Primary score remains equal-maze-group macro uniform-axis R², with pooled R² secondary and all four signed comparisons against `phase_only`, `raw137`, `pca10` and `random10`. Negative scores remain valid; constant group axes remain included with undefined primary/contrasts. There is no new success floor.

## Explicit execution profile

Candidate limits preserve the original **20 seconds from the producer start request, 1.75 CPU quota, 3 GiB RAM, two numerical threads, 64 KiB source and 1 MiB prediction**. The task worker sets `OPENBLAS_NUM_THREADS`, `OMP_NUM_THREADS`, `MKL_NUM_THREADS` and `NUMEXPR_NUM_THREADS` to `2` in the child environment before candidate imports. The unchanged transport retains its own one-thread environment. These settings are declared/enforced runtime conditions, not evidence of scientific fitting provenance.

The new transport profile differs from the historical one and inherits no historical runtime qualification:

| Item | Current explicit profile |
| --- | --- |
| Trusted output holder | 1 CPU, 128 MiB; historical holder was 0.25 CPU, 256 MiB |
| Candidate scratch/output | 64 MiB scratch; 8 MiB output volume; maximum three transport files and no subdirectories |
| Envelope/metadata | Worker-generated `RESULT.json`/`OUTPUTS.json` and read-only `/request.json` |
| Host requirement | Existing local Docker Unix socket, Linux procfs and independently reviewed immutable image |
| Provider phase | 30 s setup + 20 s producer + 15 s capture + 15 s cleanup = 80 s, inside the unchanged 90 s request deadline |
| Whole `run` command | 120 s wall maximum, including at most 30 remaining seconds for grading; historical whole attempt was 110 s |
| Trusted host CPU | At most 20 CPU seconds, respecting tighter inherited limits; candidate/holder CPU is separately bounded |
| Provider I/O | 256 MiB source/input/metadata reads, 8 MiB host writes, plus at most 256 KiB independent observer reads |
| Docker CLI | At most 128 calls and 8 MiB retained replies |

The 256 MiB read cap is **provider-only**, not a whole-attempt I/O measurement. Its two streaming public-input identity passes account for 118,698,478 input bytes before metadata/archive overhead. The scorer separately hashes the 59,347,496-byte public packet, reads only its five assessment identity fields, validates/copies the prediction and reads the bounded private/reference operands. There is no separate redundant validate invocation. Those trusted scorer, interpreter/library and daemon/kernel reads are not included in the provider counter. Source staging, operator receipts and the worker's container I/O also have distinct scopes. No authentic I/O, elapsed time, peak RAM or compression result has been measured here; limits are not observations. Original cumulative historical charges are not reset or reused as permission for a new run.

## Operator commands

Provision the original assets separately. Use an existing compatible Python/NumPy/SciPy environment, an approved already-local image, independently reviewed exposure and a separate resource allocation. The following are future execution instructions, not work performed by this source revision:

```sh
python3 -I -B /absolute/checkout/benchmarks/neural/NEURAL-019/implementations/submitted-program-v1/run.py stage \
  --repository /absolute/checkout --candidate /absolute/submitted.py \
  --public-root /absolute/provisioned-public --output /absolute/fresh-stage \
  --image sha256:REPLACE_WITH_64_HEX_LOCAL_IMAGE_ID
```

Retain the printed plan pin independently. `EXPOSURE_REQUEST.json` is not approval. The existing `osl_transport_exposure_v1` approval must bind role `A`, the exact source, image, command and four requested mount identities, plus independently approved image inventory and boundary-audit pins. The provider additionally mounts `/request.json` and the output volume as part of its reviewed source-defined boundary.

Operator configuration has exactly these fields; use actual independent exposure bytes/hash and existing disjoint private control/quarantine roots:

```json
{
  "docker_binary": "/absolute/docker",
  "docker_socket": "/absolute/local-docker.sock",
  "control_root": "/absolute/private-control",
  "quarantine_root": "/absolute/private-quarantine",
  "exposure_path": "/absolute/approved-exposure.json",
  "exposure_pin": {"bytes": 1234, "sha256": "REPLACE_WITH_APPROVED_FILE_SHA256"}
}
```

```sh
python3 -I -B /absolute/checkout/benchmarks/neural/NEURAL-019/implementations/submitted-program-v1/run.py run \
  --repository /absolute/checkout --stage /absolute/fresh-stage \
  --plan-bytes EXACT_BYTES --plan-sha256 EXACT_SHA256 \
  --configuration /absolute/operator-configuration.json \
  --target /absolute/operator-only/private.npz \
  --reference-grade /absolute/operator-only/grade.json \
  --reference-commit /absolute/operator-only/prediction_commit.json \
  --output /absolute/fresh-result
```

Private paths remain operator-only and are not resolved by the scorer until the public prediction contract passes. Actual asset identities are fixed in the accepted scorer; no production override exists. Read `LIFECYCLE.json`, its transport receipt pin and `SCORE.json`. Invalid submission, scoring error, incomplete cleanup, deadline failure or a missing/partial receipt is not a completed scored run. The stage cannot be retried automatically. Forced controller loss requires independent closure evidence and the transport's existing parent-only owned-resource recovery under separately authorized remaining resources; this adapter never searches for or kills unrelated containers.

## Source and generated evidence

`DEPENDENCIES.json` pins twelve unchanged accepted files at commit `31c05a9d2675c7d4235f7a8a0df88c88981b9395`: eight concrete NEURAL-007 transport files and the NEURAL-019 portable scorer plus its three legacy source/asset dependencies. No shared source is modified. Orchestration was adapted into these task-local files from reviewed NEURAL-023 commit `c2149217a51c195c6189ffb5f607739283ad84ae` (`run.py` source SHA-256 `9e1b8847671c893ec7d429ee3bcac3acb8ed20d55fa607304c5b280c3d910266`). That is implementation lineage only: NEURAL-023 is not imported or required at runtime, and its qualification is not inherited.

Generated controls cover complete reordered 126-trial predictions with independent scalar group arithmetic and all four original comparisons; missing/duplicate/nonfinite/malformed predictions; wrong clocks; failed cleanup/deadlines; changed receipts and captures; replacement immediately before scoring; frozen-source and mount/exposure changes; retry refusal; two-thread child settings; and the one-file candidate/envelope boundary. Test input metadata and targets are invented. The compact public fixture is not a generated full neural tensor or an authentic preparation. A fake transport and mocked worker child are used only in controls; no candidate code runs on the host. The production CLI always selects the concrete pinned provider.

```sh
python3 -I -B /absolute/checkout/benchmarks/neural/NEURAL-019/implementations/submitted-program-v1/test_run.py
```

The test log records the actual interpreter patch and NumPy versions, exact generated payload-write counter scope and zero authentic/model/native execution. This is observed software-environment evidence, not a hermetic runtime or a benchmark performance result.
