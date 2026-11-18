# Trusted provider binding for the numerical waveform pair

This component supplies the missing executable OpenAI Responses sender and a separately named provider-arm admission. It reuses the existing `waveform-transport-v1/provider_bridge.py`, original complete response collector, and `waveform-pair-v1` protected evaluator. The original macOS programme implementation is unchanged.

The condition remains `legacy_waveform_no_tools`: all 400 original numerical Cz/Pz queries, four demonstrations per query, and the same two previously exposed development people. Labels indicate experimental target/standard events; they do not identify physiological P3 presence. This component is not the visual viewer condition. A provider request does not establish native neural understanding.

## Trust and authentication

The trusted operator owns this source, its dependencies, configuration, credentials, and private artifact locations. The remote model receives only the complete original prompt and the existing strict scalar-response request. The fixed sender uses HTTPS `api.openai.com:443/v1/responses`, standard certificate/hostname verification, no proxy configuration, no redirects and no automatic retries. It keeps the original adapter's explicit model, no-tools, no-history, disabled-truncation and structured-output settings.

An authorized operator application must supply the credential **in memory through an inherited anonymous pipe**, then close the pipe's write end. Pass only its read descriptor number to `--credential-fd`; the operator consumes and closes that descriptor. This does not inherit an API-key environment variable, read a credential file, write a key to disk, or put a key in a command line. Each fresh trusted client receives a new private pipe through `pass_fds`, alongside a public configuration pipe and an owned private custody-directory descriptor. Child environments contain only locale settings. These are trusted broker processes with explicit network authority, not the network-denied local participants.

Only generated marker strings are used by the shipped controls. No live credentials or API/model calls were used to qualify this source. In-memory clearing is best effort and is not a guarantee of whole-process memory erasure.

## Request and response custody

The client invokes the existing `bridge.serve()` once. It preserves the exact bounded request and complete response bytes in `REQUEST.bin` and `RESPONSE.bin`, and writes `HTTP.json` plus the original adapter receipt inside `BRIDGE.json`. It closes the HTTP objects and durably records the complete four-file custody set before allowing an answer to leave the adapter. No HTTP headers or exception strings are retained. Failure retains its bounded available prefix and a fixed error category; an incomplete or failed query cannot form an admitted arm.

Literal credential bytes in a request or server response cause refusal. For a response, only the contiguous prefix before a detected token is retained, with an explicitly incomplete credential-echo failure. Cross-chunk detection is covered. This does not attest that a server cannot encode or transform a credential semantically; the client never intentionally inserts authentication material into prompts or retained records.

The parent records the exact prompt bytes sent and first framed answer, waits for the child to exit, and independently rejoins the raw provider response, model/policy/token accounting and receipt. A child timeout, nonzero exit, forced stop, missing custody, repeated response identity, altered answer or failed receipt makes the whole campaign unscoreable. The local client timer is backed by the parent's deadline and kill/reap path; remote cancellation or remote billing after a local timeout is not established.

All 400 responses must succeed without retry. The original complete collector creates the NPZ. Provider admission rechecks every original context and response, then verifies every public NPZ probability against those answers. No partial submission or relabeling of a `protocol_only` collection as `macos` is supported.

## Operator entrypoints

These commands document a future separately admitted provider study. They are not an execution approval or a spending estimate. Supply an exact resolved model identifier, model-compatible output allocation, full-prompt capacity, existing interpreter, and reviewed resource limits.

```sh
python -B provider_arm.py run \
  --implementations-root /ABSOLUTE/NEURAL-077/implementations \
  --delivery-root /ABSOLUTE/ORIGINAL/DELIVERY \
  --output /ABSOLUTE/NEW/PROVIDER-ARM \
  --model RESOLVED_MODEL_ID --max-output-tokens 1024 \
  --credential-fd 3 --python /ABSOLUTE/EXISTING/PYTHON \
  --query-seconds 30 --campaign-seconds 12000 --max-prompt-bytes 262144
```

The supplied descriptor must already exist in this operator process. Merely placing `3` on the command line does not provision credentials. Do not put credentials in shell history or use a key-bearing shell command to create the pipe.

To pair a completed provider arm with the original closed macOS programme arm:

```sh
python -B provider_arm.py compare \
  --implementations-root /ABSOLUTE/NEURAL-077/implementations \
  --delivery-root /ABSOLUTE/ORIGINAL/DELIVERY \
  --a /ABSOLUTE/PROVIDER-ARM --b /ABSOLUTE/MACOS-PROGRAMME-ARM \
  --private-locations /ABSOLUTE/OPERATOR/PRIVATE-LOCATIONS.json \
  --output /ABSOLUTE/NEW/COMPARISON --timeout 60
```

The new provider-arm schema is admitted separately. The original `pair._admit_arm()` still validates B, including its frozen bundle and macOS receipt. A fresh trusted evaluator repeats both admissions and calls the unchanged `pair.protected_compare()`. Both public submissions must pass validation before even opening the private-locations file. The same six references, label dtype, case IDs, participant-macro balanced accuracy/log loss and paired arithmetic are retained. The richer 1,200-label feature programme is not substituted for B.

The operator needs Python 3.11+ and NumPy for the original collection/evaluation functions. The one-query client uses the standard library. `SOURCE_BINDINGS.json` authenticates the 15 original source dependencies before import; the current component also records its runtime source identities. Standard-library/OS state and a malicious trusted host are outside this source-level attestation. Current operator source and configuration must remain fixed for the complete study.

## Generated verification and remaining qualification

From this directory:

```sh
python -B -m unittest discover -s tests -p test_client.py -v
python -B -m unittest discover -s tests -p test_provider_arm.py -v
```

An external authoring stage can set `NEURAL077_TEST_IMPLEMENTATIONS_ROOT` to its existing authenticated sibling implementation directory. This is a test-only path override, not a runtime pin override. Controls use injected HTTP objects, generated pipes/processes, invented 400-case responses and invented targets. They do not contact an endpoint or establish an actual provider study.

Actual endpoint compatibility, resolved model behavior, remote context independence, token capacity, cost, response ownership across the real provider connection and empirical performance remain unqualified. No full model campaign, API spending, SOTA improvement, unseen-person inference or new benchmark count follows from these source controls. The existing successful fixed numerical waveform pair remains a separate accepted engineering observation.
