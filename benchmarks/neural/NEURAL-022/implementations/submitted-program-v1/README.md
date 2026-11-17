# Complete active-to-passive submitted programme

This component restores delivery and execution for the original **NEURAL-022** endpoint. A programme receives all 141 labeled active training trials and all 92 unlabeled queries: 40 passive primary trials and 52 active secondary trials. Every trial has six 20 ms spike-count bins for each of 65 units, flattened to 390 features. The output is all 92 ordered velocity predictions. The unchanged scorer retains all seven signed reference comparisons, the two mode-specific losses and 16 mode-direction strata. There is no scientific pass threshold.

This is a source-tested component awaiting explicit operator adoption and authentic runtime qualification. It adds no benchmark ID, AI run, score, new biological result, provider qualification or native-understanding condition.

## Delivery and execution

1. `run.py prepare` runs the unchanged `original/project.py` in isolation. It authenticates the previously closed receipt and exactly four saved arrays, runs the original 34 generated controls, and reuses the saved 62-fit reference results. It never decodes the original NWB, refits a model or recomputes reference predictions. The output keeps all original cases while removing training `source_rows` and withholding passive training, query velocities and reference predictions.
2. After producer removal and complete capture, preparation creates six immutable, individually readable files beneath a private directory. Only `training.npz`, `queries.npz`, `cases.json` and `TASK.md` enter candidate mounts. A pinned `PACKET.json` binds the files to the source and projection closure. The private bundle remains outside candidate mounts.
3. `run.py run` commits one Python source file, at most 200,000 bytes, before public input release. The isolated programme receives `--input /input --out /output` and must write only `predictions.json`, at most 65,536 bytes. The full unlabeled query batch is visible, but the original `TASK.md` policy requires fitting and normalization to use active training only. Query-dependent or transductive fitting remains outside that policy; output validation cannot certify compliance.
4. The provider observes the actual successful candidate exit, removes the producer, captures the complete output and closes the holder and volume. Candidate-written `RESULT.json` cannot replace that observed exit status. The operator republishes the captured predictions and commits them before grading.
5. The unchanged, captured pure-stdlib validator checks every public row before any private grading file stat, hash, open or mount construction. Invalid predictions retain the original `invalid_submission` and null-score disposition with no private grader dispatch. Malformed trusted case metadata remains an operator failure.
6. A separate trusted container runs the unchanged `original/grade.py` and accepted numerical modules. It repeats public validation, checks the exact saved reference losses, computes the original score and emits its bounded JSON. Natural exit, stopped state and independently observed removal are required before accepting a score. Candidate code is never a grader mount.

The original worker's validation/read counters describe that worker, not aggregate controller I/O. A valid submission is public-validated on the host and again by the original grader. Private transport authentication occurs after host validation and before the worker's own private-read counter. No target or reference numerical scoring runs on the host.

## Original clocks and resource profiles

| Stage | Whole / work / cleanup | Worker and resources |
|---|---|---|
| Packet preparation | 150 / 120 / 30 seconds | Original projector: 90 s enclosing producer interval; original 85 s cooperative compute plus finalization. This implementation selects a 1.5 CPU, 3 GiB projection worker and a 0.25 CPU, 128 MiB holder within the original 2 CPU / 4 GiB aggregate. The individual projection resource choice is new. |
| Programme | 210 / 180 / 30 seconds | Candidate lifecycle 70 s, including 20 s execution; 1.5 CPU / 3 GiB candidate and 0.25 CPU / 128 MiB holder. |
| Trusted grader | Included 80 s phase | One container, no holder: 1.75 CPU / 3 GiB, CPU rlimit 20/22 s, nofile 1024, 40 s wait and 20 s cleanup. This leaves 0.25 CPU for the controller. |

The copied concrete transport differs from its accepted predecessor in the holder CPU constant, consistently requested/admitted/reported as 250,000,000 nanocpus, the six numerical thread environment controls, each set to two, and publication of explicitly readable immutable files. Both publication helpers finalize an explicitly requested `0444` mode on the owned file descriptor after writing, so restrictive umasks cannot hide individual mounted files from container UID/GID 65534. Private `0400`/`0600` defaults, private `0700` parents and the native readability guard remain unchanged. The other five transport module bodies are byte-identical. Python source tests use one thread under the shared test pool, independent of the future original two-thread native profile.

The trusted projector's diagnostic nonzero exit is wrapped as a successful transport exit solely to preserve stopped partial files in quarantine. The controller requires both a zero projector diagnostic and all six original files before making a usable packet. Candidate nonzero exits propagate through the actual container exit status. Failed or timed-out candidate output is not admitted; failed capture may leave no usable artifact. Missing receipts and hard-interruption closure remain unresolved until an operator checks the exact owned-resource journals.

The unchanged worker starts its own clock before scientific imports. The wrapper imports only stdlib first. Provider setup, capture and cleanup remain inside the outer phase. Configuration/source preflight occurs after the outer clock origin but before installing its signal timer; it does not receive additional time, and unusually stalled preflight has no independently proven interruption bound. Later phase admission refuses insufficient remaining time. The hard cutoff may leave owned resources that require separately authorized recovery. No forced-stop recovery qualification is inherited.

## Operator binding

Future execution requires an existing Linux operator with pidfd/procfs support, the exact locally provisioned immutable numerical image, a local Docker socket, a stable operator-controlled checkout, private preprovisioned control/quarantine roots and an independent image/source/input-boundary approval. The copied transport deliberately refuses unsupported platforms; this is not a host fallback for macOS. Imports precede source reauthentication, so the operator must not mutate the checkout during execution.

Run from the repository root with the pinned component path:

```text
python3 -I -B benchmarks/neural/NEURAL-022/implementations/submitted-program-v1/run.py prepare --configuration PREPARE_CONFIG.json --output FRESH_PREPARE_DIR
python3 -I -B benchmarks/neural/NEURAL-022/implementations/submitted-program-v1/run.py run --configuration RUN_CONFIG.json --program PROGRAM.py --output FRESH_ATTEMPT_DIR
```

Configuration schema `neural022_delivery_configuration_v1` binds `source` to the exact `SOURCE.json` bytes/SHA-256 descriptor, `image` to the original image in `common.py`, and absolute operator paths `docker_binary`, `docker_socket`, `control_root`, `quarantine_root`. It also supplies `mechanical_policy_path`/`mechanical_policy_pin` and `allocation_path`/`allocation_pin`. Preparation adds `original_inputs_root`, containing the five original saved inputs described by the portable contract. Programme execution adds `packet_root` and the exact `packet_pin` for `PACKET.json`. Source-only construction does not supply or authorize these operator locators.

The policy must have schema `neural022_delivery_boundary_v1`, the exact `source` and `image`, a pinned `image_inventory_sha256`, `operator_approved: true`, and `approved_rule: exact_original_projection_then_public_candidate_then_private_grade`. That record must represent actual independent review; generating its JSON is not evidence that a boundary has been qualified.

Allocation schema `neural022_fresh_delivery_allocation_v1` binds `source`, `stage` (`prepare` or `run`), `operator_approved: true`, `historical_failed_projection_seconds: 150`, `current_history_sha256`, `current_prior_cumulative_seconds`, `new_cumulative_ceiling_seconds`, `new_whole_seconds` (150 or 210) and `operator_artifact_bytes` (at least 16,777,216). The current external history must include every earlier charge, including the failed 150-second packet attempt. The historical counter is not a new grant, and this component cannot erase it. Each new attempt needs a fresh complete allocation; there is no automatic retry. Transport I/O caps are explicit in `run.py` and `grade.py`; their counters exclude unobserved producer/kernel/library I/O and exact process-tree peak memory.

Partial outputs and all failure receipts must be retained. Failures before output creation may produce no component receipt; after creation they can leave partial commitments. A `COMPLETE.json` file does not override a later `FAILED.json`, nonzero process exit or uncertain resource closure. Never reuse a failed output directory.

## Scientific interpretation and provenance

The original Han session and retrospective movement/condition timing are exposed. The fixed passive neural reference is privileged by passive labels. Original trial/context overlap and the single-animal/session limitations remain. This is an exposed retrospective active-to-passive comparison, not an unseen animal/session test, raw causal spike reconstruction, direct signal understanding, native LLM condition or a SOTA claim.

`PROVENANCE.json` records the original source pins, exact transport delta and unchanged numerical sources. The portable contract removes only two unused machine-history locator fields; required scientific fields, original input pins, expected losses and per-entrypoint source pins remain unchanged. Its new identity is intentionally distinct. Absolute private locators are excluded from this component.

Generated controls exercise the complete original projection and scorer, all seven comparisons, public-last-row rejection before private dispatch, exact request/exposure/mount wiring, requested and admitted role profiles, submission digest binding, immutable snapshot modes, candidate failure propagation, trusted partial projection preservation, stage/history refusal, and grader cleanup after admission refusal. These are source/software controls on invented full-panel data and generated transport doubles. Authentic payloads, labels, Docker/native runs and model calls were not used.
