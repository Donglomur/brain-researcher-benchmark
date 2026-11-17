# Operator provisioning for the 400-case waveform pair

This is one completed finite implementation of NEURAL-077: two exposed
development people, 200 cases each, with four original demonstrations per query.
`README.md` gives the freeze/run/compare commands. Keep public delivery,
participant code, operator receipts and private grading inputs in separate
operator-owned locations. Source code alone does not distribute the data below.

## Selected available runtime

The accepted run used macOS on Apple Silicon, the existing `/usr/bin/sandbox-exec`,
an operator Python 3.11.6 environment with NumPy 1.26.3, and framework Python 3.11.5
for restricted participants. Both interpreters and NumPy were already installed;
the full new 400-case route and fresh paired grade executed successfully.

| Runtime operand | Observed identity |
|---|---|
| `/usr/bin/sandbox-exec` | 102560B; SHA256 `4835a0fb96364a8153e20fc27028ef0d8a8d4f3e6a47e1fff28b012369121531` |
| `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11` | 152624B; SHA256 `ff2d7180d4aa2dcc03193194c1999509239e00101ade54fcdd736d9fc25bd0c6` |
| Operator Python executable target | SHA256 `4959d784e83b29c47836a946a6ce6ac7f8f36bb1edc90b394dde44a6376cb1a1` |

The participant profile is a complete embedded, stdlib-only declared program;
NumPy is needed by the trusted operator/collector/evaluator, not inside that
restricted client. No GPU, model weights, Docker image, SciPy, sklearn or provider
credential is required for this route. The existing old Docker grader remains
a separate implementation; its image availability is not a dependency here.

For a clean machine, provision macOS with the selected Seatbelt command, a
framework Python permitted by the existing transport, and a separate operator
environment containing the pinned NumPy version. Then verify actual interpreter,
sandbox and source identities before selecting that environment. The accepted
machine is available and exercised; a clean-machine reinstall, frozen whole-OS
image or equivalence of another Python/NumPy/OS version is not claimed. Changes
to that runtime are a separately named qualification, not a silent fallback.

## Exact packet needed, without a fresh raw-data download

The public delivery directory must contain these five original `public/` files.
They total 14,672,090 bytes. The exporter pins are unchanged and checked by the
entrypoint; no substitute derivative or input-hash override is provided.

| File | Bytes | SHA256 |
|---|---:|---|
| `queries.jsonl` | 14521484 | `1a34369834d022d0dc332293b6cd120df006195855c08087697bcdd823b1f126` |
| `demonstrations.json` | 129921 | `19e4018216376af334fd5ead21e2c33d5761d9d56ce5c76d3a89411483906ed2` |
| `prompt.txt` | 1703 | `2ecc6656d099083f2d87112147430aa1f780c714ce31579e025c69ac74ec77a0` |
| `response_schema.json` | 480 | `bd0c92c7016a20b039fbb273aad8802be1da088b0f1fec3e15fac0a1070eed12` |
| `manifest.json` | 18502 | `edb93d2e6003e90afb54f8f62a97ceccd6088c59ba4fba1e4a2fb780c6bf9dc8` |

The accepted operator already holds this exact verified packet; its local paths
are recorded in the private execution protocol. Provision the packet through
the operator's authorized data channel, for example at
`/operator/neural077/delivery`, and pass that directory to `--delivery-root`.
If reconstructing it from original ERP CORE assets, use the existing
`complete-direct-condition-v1/delivery.py build` recipe and exact asset pins;
that is a separate preparation operation and is unnecessary for the cached route.
The packet preserves complete 1024-sample Cz/Pz epochs, original rereferencing
and baseline, four demos and opaque trial IDs. Verify the chosen model's token
capacity for the complete numerical prompts; do not downsample or truncate them.

## Protected grading inputs

These four existing operands total 110,633 bytes. Only the trusted evaluator
may receive their paths. Populate the private-locations JSON shown in README;
both predictions are validated before that file is opened.

| Registered operand | Bytes | SHA256 |
|---|---:|---|
| `rest/development-001/targets.npz` | 39422 | `8af103a414408567e44eb05f92ef481345d6e8a421ea4b8da1b28eccb3ab06c7` |
| `rest/development-002/targets.npz` | 39422 | `abb7c6d86cc423f5b9d0b597d374c9519c48359b5a563abacd197114db42ed14` |
| `grade.json` | 31063 | `0fe512dd65366608d22839e7cfae83f19abe09a559c6d27e5e44808d7e0bc07a` |
| `prediction_commit.json` | 726 | `f0b02bea5df3717fca94833ef5caa11e0ead25ebdab9b9f2cd3b15af3e9e1dc8` |

The accepted operator also holds these exact protected files. Provision them
under a private location such as `/operator/neural077/grading` and populate the
locations JSON with its actual absolute paths; never mount it for participants.
Keep exact frozen reference lineage and all six arms. No refitting or original
reference prediction-array load is needed. Private labels and raw source data
are not bundled in the repository or in this public receipt.

Ordinary new comparisons use two completed arm directories with `--a` and `--b`.
The special `--legacy-control` option accepts only the historically pinned
fixed-0.5 no-tools proof. If reusing it on another operator machine, provision
the exact accepted proof directory at a private operator location such as
`/operator/neural077/accepted-no-tools-proof`; required identities are fixed in
`pair.py` and preserved in the actual-control evidence.
It is an evidence-reuse shortcut, not a dependency on a new model study.

## Optional later model integration

The existing `waveform-transport-v1/provider_bridge.py` exposes
`exchange(prompt, model=..., max_output_tokens=..., send_json=..., record=...)`
and framed `serve(...)` for the no-tools condition. It builds one fresh prompt,
requests no tools/retrieval/history, refuses silent model-ID changes and retains
bounded request/response evidence through operator-injected sender/record hooks.
It is an available provider-neutral interface, not a bundled authenticated HTTP
backend. Its sender, credentials, capacity and no-tools policy need study-specific
qualification. Place remote communication in a trusted operator broker; the
selected macOS participant cannot access the network. Never add credentials or
a network sender inside the frozen restricted client.

Model selection, provider capacity, actual AI/human scores and scientific
interpretation are subsequent studies. None changes this implementation's one
benchmark count, original cohort or protected grading requirements.
