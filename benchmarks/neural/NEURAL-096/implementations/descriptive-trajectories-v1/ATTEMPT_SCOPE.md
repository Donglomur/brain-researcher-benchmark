# Attempt adapter: usage and validation scope

This source adapter connects declared observation access, a single captured answer
and the existing operator grader. Its accepted 40 generated checks validate local
file/API commitments. They are not an AI evaluation or a participant sandbox.
The earlier authentic preparation, arithmetic and local SVG exercise remain
recorded in [VALIDATION.json](VALIDATION.json) and
[DELIVERY_VALIDATION.json](DELIVERY_VALIDATION.json).

## What each arm can request

The operator builds separate material roots. The native root has a sanitized
index and the 48 cell PNGs; it has no numeric aggregate JSON. The programme root
has the same sanitized index and the byte-identical prior-specific aggregate JSON.
An absent prior remains explicit, while an available prior in that cell remains
available. Neither arm receives differences, evaluator vectors, reference answers
or individual-trial responses.

Participant request dictionaries contain only these selectors:

| Request | Native | Programme |
| --- | --- | --- |
| `{"kind": "index"}` | Sanitized index | Same sanitized index |
| `{"kind": "view", "cell_id": selected_cell_id}` | One declared PNG | Refused |
| `{"kind": "observations"}` | Refused | Original aggregate JSON bytes |

The operator supplies all paths and frozen commitments. Participants do not
choose filesystem paths, execute an arbitrary callback through this adapter or
request grading feedback. Refused selectors and valid requests that fail material
integrity checks consume the request count. Delivered bytes and a fixed response
header reserve are charged against the declared response budget. Requests after
sealing are refused.

## Operator usage

The following is an API wiring example, not a command that discovers or downloads
data. All uppercase identities and lower-case input/path variables are supplied
by the operator from independently verified source and rendering closures. Load
`attempt` and `attempt_grade` from authenticated operator code, with their trusted
imports fixed before use. Absolute output paths must be fresh, outside Git, and
separate from input/material/attempt roots. Maintain a separate operator ledger
for global attempt uniqueness and the frozen commitments.

A native materialization additionally needs an externally verified raster closure.
`png_sources` maps each of the 48 exact cell IDs to a `path`, `bytes` and `sha256`
commitment. Header/dimension and byte checks in this adapter do not establish that
a PNG faithfully depicts the intended biological data.

```python
from attempt import (
    materialize_native, materialize_programme, create_attempt,
    request_observation, submit_final, verify_final,
)
from attempt_grade import grade_attempt

# These hashes refer to the original observation/index and preparation closure.
common_binding = {
    "observation_manifest_sha256": OBSERVATION_MANIFEST_SHA256,
    "observation_sha256": OBSERVATIONS_SHA256,
    "preparation_completion_sha256": PREPARATION_COMPLETE_SHA256,
    "index_sha256": ORIGINAL_INDEX_SHA256,
}
native_material = materialize_native(
    original_index_bytes, png_sources,
    {**common_binding, "renderer_manifest_sha256": RENDERER_MANIFEST_SHA256},
    native_material_root,
)
programme_material = materialize_programme(
    original_index_bytes, original_observation_bytes,
    common_binding, programme_material_root,
)
# Retain these returned commitments in the independent operator ledger.
native_material_sha = native_material["material_manifest"]["sha256"]
programme_material_sha = programme_material["material_manifest"]["sha256"]
```

Materialize each root once. The example below creates one chosen arm; a comparison
requires a separately registered attempt and fresh attempt root for each arm.
Instruction and answer-contract hashes bind declared operator configuration; they
do not prove what a provider actually delivered to a model. The operator must
verify that delivery separately.

```python
material_root, material_sha = (
    (native_material_root, native_material_sha) if arm == "native"
    else (programme_material_root, programme_material_sha)
)
config = {
    "attempt_id": globally_registered_attempt_id,
    "max_requests": declared_request_cap,
    "max_response_bytes": declared_response_byte_cap,
    "max_final_answer_bytes": declared_answer_byte_cap,
    "instruction_sha256": INSTRUCTION_SHA256,
    "answer_contract_sha256": ANSWER_CONTRACT_SHA256,
}
created = create_attempt(material_root, material_sha, config, attempt_root)
attempt_sha = created["attempt_manifest"]["sha256"]
# Persist attempt_sha independently before delivering observations.
index_response = request_observation(
    material_root, attempt_root, attempt_sha, {"kind": "index"},
)
selector = (
    {"kind": "view", "cell_id": selected_cell_id} if arm == "native"
    else {"kind": "observations"}
)
response = request_observation(material_root, attempt_root, attempt_sha, selector)
# A separately qualified transport would deliver response["body"] with its
# declared response["content_type"]. This API performs no provider/model call.

capture = submit_final(attempt_root, attempt_sha, participant_answer_bytes)
final_sha = capture["receipt_pin"]["sha256"]
# NOW persist final_sha in independent operator custody, before any readback.
# This persistence is an operator-ledger operation, not an adapter function.
# Never replace it by hashing the current FINAL.json during verification.
if capture["receipt"]["status"] != "captured":
    raise RuntimeError("Answer was rejected; this attempt remains sealed")

verified = verify_final(attempt_root, attempt_sha, final_sha)
# Operator-only: the operator ledger supplies the original final_sha again.
grade_receipt = grade_attempt(
    prepared_directory=operator_prepared_directory,
    completion_sha256=PREPARATION_COMPLETE_SHA256,
    observation_manifest=operator_observation_manifest,
    observation_manifest_sha256=OBSERVATION_MANIFEST_SHA256,
    attempt_directory=attempt_root,
    attempt_manifest_sha256=attempt_sha,
    final_receipt_sha256=final_sha,
    output_directory=fresh_operator_grade_directory,
    participant_material_roots=(native_material_root, programme_material_root),
)
```

Capture is byte-based, not a scientific-validity check. Even malformed JSON within
the size/type bounds is captured once; there is no format feedback followed by
resubmission. A type/size rejection also seals the attempt. The bridge verifies the
original final commitment before and after grading, checks preparation/observation
bindings, and delegates unchanged to `prepare.grade_submission`. Grading remains
private, supplies no participant feedback, and preserves failed output without an
automatic retry. Give the bridge both actual participant material roots; output
placement checks also protect the preparation, observation bundle and attempt.
These lexical checks depend on truthful caller declarations and are not an OS
access boundary. An attempt nonce distinguishes local manifests; it does not
replace the operator's global uniqueness ledger.

## Engineering ceilings and validation

Configuration selects positive caps within module ceilings of 128 requests,
512 MiB charged response bytes and 128 KiB final-answer bytes. These caps are
engineering safeguards. They have not been experimentally validated as an equal
model budget, an optimal viewing strategy or a difficulty policy for the two arms.

[ATTEMPT_VALIDATION.json](ATTEMPT_VALIDATION.json) records one coordinated run of
40 generated methods: 20 adapter checks, 17 bridge checks and three integrations
using the real capture/verification core with only the scientific grader stubbed.
All passed with zero skips. Fixtures cover all 48 cells, both access arms,
one-sided missing priors and blank 1360×1180 PNGs. The run imported no NumPy,
Pillow or scientific `prepare` module, opened no authentic data, and executed no
renderer, provider or model. Blank PNG fixtures exercise file and API behavior;
they cannot qualify image semantics. A previous 16-method bridge run used an older
bridge and is historical, not an additional 16 new checks. The anticipated CI
artifact total is 114 methods (prior 74 plus these 40), not a claim that all 114
were executed together in this run.

A separate generated raster probe was accepted after operator postflight and
independent saved-result/visual review. One admitted execution completed three
renders: the same supported fixture twice and an unsupported fixture once. The
18-file closure contains 3,202,334 bytes; its six raw/normalized PNGs are
1360×1180, and both repeat pairs were byte-identical. Exit status was zero and
wall time was 13.948 seconds. Peak RSS was not persisted: the declared 512 MiB
allowance is neither a measured peak nor an established process-tree memory bound.

This establishes the observed local generated-image runtime and scoped fixture
legibility. Labels are about 10 pixels high; quarter gridlines cross the
unsupported-prior sentence, which remained readable in the inspected fixture.
The review does not qualify all font glyphs, complete OS/Rosetta dependency
closure, whole-image alpha semantics, provider resizing/compression or every
possible unit label. The generated worker's fixed interior checks and independent
visual inspection are distinct evidence. No authentic 48-image raster run,
provider transport or model attempt was performed by this probe. An exact
full-48 proposal is separate pending work, not a completed result here.

## Scientific scope remains unchanged

The response-conditioned Set–Go estimand retains 204 trials, the original
150/54 split, 54 units, 20 phase bins and all 48 split × recording-segment ×
effector × direction groups (27 supported, 21 explicitly unsupported). Each
trial's counts are divided by its actual bin exposure, then averaged with equal
trial weight within each prior. Long minus short is summarized by four fixed
quarter signed means and four quarter RMS values. There is no positive-sign
requirement, hidden dropping of unsupported groups or new score threshold.

These eight values are deterministic descriptive phase summaries, not a complete
unit-level geometry claim or an original paper result. Successful programmed
arithmetic alone does not establish learned neural understanding. Numerical error,
support conclusions and uncertainty qualifications remain separate. The one
animal/session and six nonrandomized recording segments do not identify
population uncertainty; the uncertainty outcome remains `not_qualified`.

Both arms represent the same aggregate information, but the original SVG uses
256 shade levels on common axes while programme access preserves numeric JSON
precision. A raster/provider path can add further loss. Continuous numerical
scoring is unchanged; no easier native tolerance compensates for that loss.
An observed arm difference would not by itself isolate a pure tool-use effect.
No model attempt, biological performance, SOTA claim, inference qualification or
canonical task-readiness promotion follows from this adapter stage.
