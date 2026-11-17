# Human-ripple long-table program component

This standalone source component runs one Python program against the original five-file processed-rate packet for PAPER-FIND-003, captures its JSON artifact, closes its container, and then applies the unchanged numerical and membership graders.

The task is **protocol-guided reconstruction of three fixed point-estimate mixed models**. It does not provide a paper-versus-code experiment, raw electrophysiology detection, historical afex inference, an improvement study, a blind holdout or proof that correct output was freshly computed. All numeric errors, coverage and membership diagnostics remain separate; there is no invented binary scientific reward.

## Inputs and runtime

Data and private answers are not distributed here. A maintainer must provide the exact five files identified by PUBLIC_INPUT_CONTRACT.json and a separately reviewed private reference bundle. The preparation receipt binds both and cites the maintainer's review. That receipt is trusted operator input, not independently generated evidence of scientific correctness.

The historical candidate image is fixed in RUNTIME_CONTRACT.json. It includes the previously used R 4.2.2/lme4 environment. The image is not included or pulled by this component. A matching, independently admitted local image, canonical Docker executable, selected local daemon socket and fresh capacity record are required. The runtime receipt's review hash is a provenance link supplied by the maintainer; the source package does not requalify the entire image or daemon.

The program ABI remains:

`python -I /program/program.py --input /input --out /output`

Produce only `/output/submission.json`, at most 262144 bytes. The nested model artifact is limited to 32768 bytes. TASK.md and DATA_AND_OUTPUT_CONTRACT.md describe all required fields, preprocessing and scientific conventions.

The new container bridge redirects candidate logs to the bounded stderr channel and implements file-output capture on stdout. Its capture routine rejects extra files, symbolic links, hard links and over-limit outputs. This transport differs from the historical holder-volume transport and has not received an authentic Docker execution qualification.

The bridge and candidate share UID 65534. The bridge implements the file-output ABI; it is not a separate security principal or evidence that an adversarial candidate computed the file honestly. A candidate may attempt to reopen the bridge stdout through the container's process filesystem. All captured bytes are therefore untrusted candidate output. Host ownership checks, bounded complete capture, confirmed container removal, strict numerical admission and the delayed private-reference callback define the evaluation boundary.

## Run

Prepare REQUEST_TEMPLATE.json as a separate private file, resolve all descriptors and set selected only after the finite operation is actually authorized. Supply its exact byte count and SHA256:

```sh
python3 -I -S -B run_program.py --request /absolute/private/request.json --request-bytes BYTES --request-sha256 SHA256
```

Each attempt has one 75-second whole horizon, 60 seconds for work, a 20-second candidate interval, 3 GiB candidate memory and 1.75 CPUs. No package installation or network is allowed. The trusted owner plans 512 MiB host memory in addition to candidate memory, other selected work and a 1 GiB margin. Capacity witnesses must be fresh and mutually consistent; those estimates are not hard global host-memory guarantees.

The candidate sees only its program, the five public inputs and the bridge. Its container has no reference, grader, operator request or Docker socket mount. The complete submission and lifecycle evidence are committed before the private reference can be loaded. Invalid submissions and whole abstention cause zero private reference callback reads. Closed execution failures remain distinct from numerical scores; uncertain cleanup or operator errors never become scientific zeros.

All results and raw lifecycle evidence remain in the fresh private output directory. Failed attempts and partials are retained. There is no automatic retry, deletion or cache cleanup. The caller must review terminal process/container closure before selecting another attempt after interruption.

The final result's `reserved_write_bytes_before_final_result` field is the reservation snapshot before that report is written. Its own bytes are also admitted and charged by the same write budget; the snapshot is not a total filesystem-I/O measurement.

The historical scientific/program results are reused as provenance only: eight historical program invocations, no external model calls, and 1290 seconds known family allowance. The portable transport is a new source component, so its source tests do not add to that scientific count or establish new readiness.

## Local source checks

These commands use only invented fixtures and stdlib Python; they perform no Docker operation, authentic-data analysis, fit or model call:

```sh
python3 -I -S -B verify_export.py
python3 -I -S -B tests/test_component.py
```

They exercise the real numerical graders, an independent signed-error check, membership/coverage failures, the lazy-reference boundary, strict output-file capture, exact container profile checks and a mocked full ownership lifecycle. Native container compatibility and authentic end-to-end operation remain unverified for this export.

