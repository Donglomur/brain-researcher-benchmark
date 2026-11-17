# Owner operations

All commands below belong to the trusted operator. They are not candidate tools. Use a separate private work directory outside this source package, with mode 0700 and umask 077. Actual scientific-operand preparation and container execution require a selected runtime window; the current source assembly performed neither.

## 1. Provision the exact operands

Copy LOCATIONS.template.json to an owner-private location. Supply paths for all 17 fixed external slots. Six participant documents come from the pinned package; the fresh delivery-basis record supplies the remaining slot, giving exactly 24. The separate full120 reference is also owner-provided.

The setup helper preserves every fixed byte count and digest from the engine templates. It accepts only the delivery-basis, current owner-interpreter and runtime-policy pin metadata as operator choices. It does not download, inspect, create, replace or interpret scientific assets. The existing owner will authenticate their actual bytes and reject substitutions.

Provide a fresh delivery-basis JSON under schema nider_owner_selected_delivery_basis_v1, binding the exact paper SHA256, local_isolated_candidate_access scope, a nonempty basis and selecting owner. It records the operator's basis; it is not legal clearance. Supply an actually admitted runtime-policy graph, not a document with guessed identities. The interpreter must be a regular non-symlink executable no larger than 8 MiB and match the interpreter that runs the trusted owner.

The template's policy is an explicit example within the existing owner's allowed limits. Select the actual policy prospectively. Setup uses precisely the same policy and comparison ID for A and B; no paid model service is configured.

## 2. Emit deterministic preparation requests

```sh
/absolute/regular/python3 -I -S -B /absolute/package/setup.py bind \
  --locations /private/locations.json --output /private/nider-setup
```

The output directory must not exist. The helper writes ASSET_MANIFEST.json, FULL120_OWNER.json, PREPARE_A.json, PREPARE_B.json and SETUP_RESULT.json, mode 0600 under mode 0700. It refuses source/output overlap, aliased operand paths, symlinks, unknown slots, invalid pins and policy expansion. SETUP_RESULT explicitly reports authentic_operands_read=false and runtime_admitted=false. An interrupted partial directory is not a successful setup and must not be overwritten.

SETUP_RESULT contains each exact prepare_argv array. Execute the selected array as arguments without shell eval, or use its values directly:

```sh
/absolute/regular/python3 -B /absolute/package/engine/owner/owner_package.py \
  /private/nider-setup/PREPARE_A.json EXACT_PREPARE_A_SHA256
```

This existing owner now authenticates the real operands/runtime and creates the private run-A session. Failure is a failure; setup success does not waive admission. Use independent authoring contexts for A and B.

## 3. Author through the bounded gateway

The prepare result supplies authoring_argv for the existing gateway. Execute that exact array. The operator keeps its arguments, plan and private paths; only stdin/stdout JSON-line traffic goes to the candidate.

After ready, the candidate may send:
```json
{"op":"exec","command":"cat /task/OUTPUT_INTERFACE.json"}
{"op":"submit","program":"THE COMPLETE R PROGRAM AS A JSON STRING","deviations":"A nonempty account of choices and deviations."}
```

Only exec and submit are accepted. Shell commands execute inside the owned offline container. Submission freezes the program and deviations after verified cleanup. No candidate-supplied host path, grader request or secret is accepted. A real submission must satisfy the full field schema; the schematic string above is not an oracle.

## 4. Prepare and execute protected assessment

The trusted session is run-A/OWNER_SESSION.json. Bind its exact observed SHA256:

```sh
/absolute/regular/python3 -I -S -B /absolute/package/setup.py followup \
  --operation prepare_assessment --operand /private/nider-setup/run-A/OWNER_SESSION.json \
  --sha256 EXACT_SESSION_SHA256 --output /private/nider-setup/ASSESS_A_REQUEST.json
```

Run engine/owner/owner_package.py with the emitted request path and digest. It validates the completed signed handoff and emits assessment_argv. Execute that exact existing outer-observer array once. The unchanged engine runs the same frozen R program in four isolated candidate containers and then, only after all four close, invokes the trusted original-reference comparator. Do not bypass the observer with a direct protected_runner call.

## 5. Present the saved outcome

Use setup.py followup --operation summarize with run-A/ASSESSMENT_READY.json, its exact SHA256, and a fresh private request filename. Pass that request and digest to owner_package.py. Summarize validates saved source/program/case/runtime/cleanup/custody joins; it does not refit or reclassify scientific results.

Only the candidate_feedback object, or the contents of PUBLIC_RESULT.json, is an allowed candidate result. Enclosing paths, full numerical-error reports, references, hypothetical inputs, keys, raw owner exceptions and private receipts stay private. Incomplete execution is not a score. There is no intermediate assessment feedback.

Repeat the same sequence for B using its own independent context and run-B directory. The shared policy/material/interpreter/runtime identities must remain matched. The unchanged configuration.paired_handoffs check exists for trusted pair review; this setup helper does not pretend to have executed that review.

## Runtime contract

Actual owner: Linux ARM64, positive numeric UID/GID, conventional local Docker numeric mapping at unix:///var/run/docker.sock. Remote daemons, rootless/userns mapping, AMD64/emulation and the historical Mac owner are not substitutes. Dependency image: admitted inert-default clean-offline-dependencies-v2-inert-default, R 4.3.2/meta 7.0-0 and complete pinned dependency evidence. Image identity/config/layers and absence of private assets must be checked by the existing policy.

Candidate resource limits remain the unchanged source contract: 1 CPU, 2 GiB, offline, read-only root, bounded writable work/tmp, exact read-only mounts, output at most 65,536 bytes. The protected assessment observer's 240-second/one-attempt limits remain unchanged. Current target/image/bind-mount behavior and resource admission have not been established by this kit.
