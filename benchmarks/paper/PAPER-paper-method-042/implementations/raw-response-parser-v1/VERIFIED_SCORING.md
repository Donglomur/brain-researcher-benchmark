# Verify captured raw responses before vector scoring

`verify_and_score.py` completes the existing raw-response importer with a trusted
operator route from frozen raw answers through the converter's sixteen extracted
files to the original four-subject endpoint vector. It checks the entire bundle,
replays the original parser, and scores only the extracted JSON snapshots that
passed verification. It adds no task, model runner, scientific decision or
benchmark readiness.

The earlier `endpoint_vector.py` accepts independently supplied extracted files.
Its input hashes identify what it scored; they do not establish that those files
came from a particular raw-response conversion. This new entrypoint adds that
relationship without changing `raw_response.py`, `grounding.py`, or
`endpoint_vector.py`.

## Operator inputs and independent authority

First obtain a complete output directory from the existing converter. Retain the
raw panel, query roster, `conversion.json`, and all sixteen named extracted files.
The scoring contract still declares all four roles and S1/S2/S5/S7 and points to
those exact files. Annotation and image-order inputs remain operator-side.

Supply the expected **byte length and SHA256 of both raw panel and roster** from
an independently accepted capture record. Do not derive this authority solely
from the bundle currently under verification. A self-consistent replacement of
the raw data and its purported authority cannot be detected by this route. The
commitments attest accepted bytes, not their producer, model, observations or
exposure history.

```text
python3 -I -B verify_and_score.py \
  --raw-panel RAW.json --query-roster QUERIES.json \
  --expected-raw-bytes RAW_BYTES --expected-raw-sha256 RAW_SHA256 \
  --expected-roster-bytes ROSTER_BYTES --expected-roster-sha256 ROSTER_SHA256 \
  --conversion CONVERTED/conversion.json \
  --contract CONTRACT.json --annotations ANNOTATIONS.json \
  --image-order ORDER.json --output NEW_RESULT.json \
  --draws 1000 --seed 0 --confidence 0.95
```

Only Python 3.10+ and its standard library are required. Input paths must resolve
to ordinary, canonical files without symlinks; distinct input roles cannot alias
one inode. Existing outputs, including dangling symlinks, are refused. These are
trusted-operator safeguards, not hostile-filesystem or untrusted-candidate
isolation.

## Verification and unchanged scoring

Before payload reads, the route checks file roles and the combined input-size
bound. It checks each individual file bound immediately before capturing that
file. It captures each of the 22 JSON inputs once and checks file-state stability
during capture.
Strict JSON parsing rejects duplicate keys, nonfinite numbers (including overflow
such as `1e400`) and invalid Unicode. Later pathname replacement cannot change the
captured values that are scored.

The converter manifest must declare complete output and match replay metadata,
input pins and all sixteen output pins. A `complete: true` flag is required but
is not evidence of a historical converter process exit. The **new successful
verification operation** is the completion authority recorded by this route.
Existing conversion manifests and older scores are never relabeled as proof of
that new operation. Callers must independently observe the new CLI's successful
termination before admitting its result.

The route repeats the unchanged converter on the captured raw panel and roster.
Every extracted file must match both the recorded exact file pin and the bytes
emitted by the original converter's serialization recipe. This preserves numeric
image order, sorted category insertion order, all empty-query images and exact
numeric representation. Merely updating a tampered output's hash in
`conversion.json` does not satisfy replay. All extracted values are also compared
by the converter's existing complete-panel comparison routine.

Optional `--compare-extracted-panel` diagnostic metadata from the older converter
may be present. It is preserved only through the conversion-manifest byte pin;
its separate comparison input is **not consumed or attested**. Even a diagnostic
disagreement about that unused third-party panel cannot replace the new route's
mandatory exact replay of the sixteen files actually scored.

The raw query roster must match the scoring annotation/image-order population,
including empty images. The scoring contract must select the exact verified
files. The route then invokes the existing `score_subject`, `summarize`, and
`compare_vectors` functions on the verified in-memory objects. It does not call
the older file-opening evaluation functions. The complete four-role/four-subject
panel, first extracted box, explicit null/empty/invalid-answer failures, fixed
query denominator, strict IoU > 0.5, shared-image bootstrap, 12 contrasts and
published baseline labels are unchanged. Original exposure checks and scientific
holds remain in the result.

## Source and output custody

The loader captures and authenticates the full bytes of the existing parser,
grounding scorer and endpoint-vector module against explicit SHA256/size pins.
It compiles the grounding snapshot. For the parser and vector snapshots it uses a
fixed, checked AST adaptation that removes **only their original top-level
pathname-based grounding loader**, injecting that same captured grounding module
instead. All imports, constants, function bodies, grammar and arithmetic are
retained. The complete-source pins and expected loader-node spans/types/names
must match. This is openly recorded as an execution adaptation, not claimed to be
an unmodified top-level module import or native author execution. No legacy source
file is rewritten and no verified source is reopened for execution.

The output contains the exact consumed input identities, independent capture
commitments, source pins, full score rows, original summaries and endpoint vector.
Raw text is not copied into the report. Query identities and detailed scores
remain private operator artifacts. CLI errors identify the failure type without
echoing protected input contents.

The final output is serialized completely, written and flushed to an owned
pending file, then linked atomically to the requested new pathname. Existing or
concurrently created outputs are not overwritten. Failed validation, write,
flush or publication produces no new complete final artifact; pending-file
cleanup is attempted. A filesystem cleanup failure can leave a private pending
file, which is not a result. The caller must observe successful process exit.

## Bounds, controls and limitations

The raw panel has a 256 MiB file limit; each other JSON file has a 16 MiB limit;
the combined captured inputs have a 256 MiB limit; serialized output has a 64 MiB
limit. These are explicit engineering refusals, not scientific task limits or
measured memory envelopes. Parsed data, replay, audit metadata and output are
materialized in memory. An authentic operation needs independent resource
admission. This CLI supplies no timeout or operating-system resource isolation.

Generated controls cover a complete untouched bundle against the original
kernels; a miss-to-hit first-box edit with unchanged and updated file pins;
independent commitments; manifest and sixteen-stream completeness; subject/role
swaps; query and empty-image joins; numeric ordering; missing/empty/invalid-first
answers and exact threshold; generated 982-image population geometry; strict JSON;
input/output aliases and FIFO refusal; snapshot replacement; dependency pins;
wrong contract paths; output failures/races; optional-diagnostic scope; and the
actual converter and new verifier CLIs. They use generated boxes/text only.

Run `python3 -I -B tests/test_verify_and_score.py` through the project's default
coordinated test pool. `UMBRAE_CONTROL_ROOT` optionally retains all generated
fixture directories for evidence; without it, temporary fixtures are cleaned up.

No authentic model generation, annotation provenance, historical converter exit,
author-runtime equivalence, exposure fidelity, protected participant transport,
reproduction, improvement or readiness follows from these source controls.
