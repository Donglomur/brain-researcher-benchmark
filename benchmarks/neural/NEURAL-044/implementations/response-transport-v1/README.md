# One-case held-response participant transport

`alm.response_transport_v1` adds a participant input/output path for the existing NEURAL-044 paired response comparison. It accepts exactly one public packet produced by `prepare_response_comparison`, starts a fresh process, sends one JSON request, collects one complete JSON response and returns the unchanged scorer submission shape (`case_id`, ordered `ids`, finite `responses`). It never opens protected targets or invokes a scorer.

The caller-owned packet is detached into a JSON-safe snapshot before validation, hashing and transmission. Later caller mutation cannot add fields or alter the delivered view. Resource limits are separately copied before validation; admission, the wall deadline and output caps use the exact limits decoded from the serialized request, so later caller mutation cannot enlarge the enforced budget. Fixed recipe fields are checked with their exact declared types; boolean/numeric substitutions are rejected.

The strict input schema rejects extra fields such as source identities, private responses, cohort records or reference predictions. The request preserves all supplied training/query rows, eight feature columns, opaque training-mouse groups, response units, the fixed reference recipe and source/disposition commitments. Both arms receive the same public-packet digest and limits; their arm label is distinct. The host supplies a pre-query recipe commitment. Accepting that digest does not itself establish a frozen code environment.

A participant returns exactly one newline-terminated UTF-8 JSON object with `schema=neural044-response-transport/v1`, the request's `packet_digest`, `case_id`, ordered `ids`, and its full `responses` vector. Duplicate JSON keys, nonfinite numbers, booleans as numeric values, incomplete or reordered IDs, a mismatched packet, extra fields and trailing stdout are rejected. A valid-looking output from a failed or unfinished process is rejected. Answer parsing remains inside the exchange budget: validation that finishes after the deadline is refused before cleanup and cannot produce an accepted answer.

`run_case(public, arm, limits, recipe_commitment, command, cwd, max_input_bytes=...)` uses an explicit argument vector without a shell. It bounds total stdout/stderr bytes and the exchange wall deadline, drains bounded pipe chunks, waits for the direct child and requests retirement of its newly created process group before accepting the answer. A fresh process is used for every call. Catchable interruption during child creation is deferred until the returned child is owned; interruption during exchange or cleanup cannot skip the normal retirement path. Cleanup may add up to one second of waiting after the exchange deadline. An uncatchable termination or host failure still requires external containment.

## Scope and remaining host obligations

This is a **response-prediction transport component**, not completion of the full benchmark or a native neural-understanding experiment. It uses numerical features and training responses, so it belongs to the tool/programme conditions. No direct-observer or visual-viewer mode is claimed.

A fresh process and a narrow stdin packet do not restrict filesystem or network access. The supplied `cwd` is not a sandbox. The caller must provision a genuine isolated per-case view before use: another mouse's public case includes training responses that can reveal this case's held-out targets. Never mount or expose the complete public case directory to a participant. The adapter's minimal environment and thread settings do not enforce RAM, CPU, tool access, model calls or token budgets. Its receipt explicitly leaves provider and scientific qualification false. Process-group retirement requested by this component is not independent host isolation certification.

The external host must also authenticate the complete prepared cohort, freeze the code/recipe before query access, preserve equal tools/resources across arms, and collect every required case exactly once without cross-case state or score feedback. It must retain attempt failures and commit **both arms' complete response submissions plus the separate investigation report** before invoking `ResponseComparisonOperator.evaluate_perturbation`. This module does not publish the missing investigation-observation channel or implement full-cohort scheduling and commitment. Public `run`/`score`, scientific gates and canonical task metadata remain unchanged.

The original source census, per-recording NWB mappings, units/clocks, independent baseline/cell links, pretest site classifications and authentic reference execution remain unqualified. No recording, target, empirical prediction, model run or reproduction result was used in this construction.

## Verification and integration

`test_response_transport.py` contains seventeen generated software controls. They exercise exact paired packet identity, private-field rejection before launch, malformed and incomplete answers, caps, fresh processes, failed-child output, deadlines and the interruption/acquisition race. The first eleven controls passed on the initial component. Independent review then found three issues: post-parse deadline enforcement, caller-mutation between validation and transmission, and boolean/numeric recipe equality. A second attempt passed three focused amendment controls for those repairs; the original eleven were not replayed. Three further controls cover limit mutation during request construction and after serialization, including output-cap enforcement and deadline refusal before launch. All three failed on the preceding source as expected; the repaired complete seventeen-control suite passed. These process fixtures do not establish genuine isolation or scientific performance.

Proposed CI command from repository root:

```sh
python3 -B benchmarks/neural/NEURAL-044/implementations/response-transport-v1/test_response_transport.py
```

The test uses only the standard library; preserved numerical modules are imported for their existing definitions and no numerical fit is executed. The sole integrator must enroll this command and regenerate applicable source/ownership manifests for the new module; CI enrollment and hosted execution have not occurred in this private package.
