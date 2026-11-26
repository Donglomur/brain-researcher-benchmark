# Complete direct numerical contexts for NEURAL-031

This package presents one authenticated existing public context as deterministic
numerical JSON, retains its first supplied response, and collects all forty
context/view outputs into the existing submission schema. It does not prepare
new biological inputs, run a model, enforce a sandbox, open private targets or
compute a score. The programme exports and scorers are unchanged.

## Scientific condition

The existing panel remains 20 mice, 774 baseline-defined requests per view and
731 observed follow-up/baseline volume ratios. All 43 unavailable-target requests
still require predictions. The two information views are baseline morphology
and baseline plus neural measurements. Both share the same permitted training
rows, training labels, mouse grouping and missingness indicators. The baseline
view physically has four columns; the neural view has six.

Direct numerical presentation versus programme execution is a **separate access
axis** from baseline versus neural information. A future comparison can evaluate
both information views under each access condition; it must not relabel the
existing neural-information gain as a causal effect of tools. Presentation,
reasoning, authoring, memory and compute also need prospective declarations.

Each presentation preserves the selected context's public manifest and six
arrays: `train_x`, `train_y`, `train_mouse`, `train_rowid`, `query_x` and
`query_rowid`. Finite float64 values, including signed zero, round-trip through
JSON numbers. Existing NaN training labels and neural measurements become JSON
`null`; they are missing, not zero. Common missingness indicators remain numeric.
No query target, query availability mask, other context, complete support roster
or operator path enters the participant presentation. The nineteen training-mouse
groups already permitted in this context remain visible.

The target is the measured follow-up/baseline ratio, with one meaning no change
and zero permitted. The inherited public manifest's `next_day` wording is kept
byte-stable as provenance; the new instructions explicitly state that elapsed
visit time is unqualified. These are processed morphology/coactivity measurements,
not raw microscopy, native waveforms or a reproduction of the source paper's
pooled stable-spine correlation.

**Forty fresh participant contexts are required.** Another fold's training
labels reveal this fold's answers. Neither a JSON receipt nor these local
utilities can prove a fresh remote context, no-tools behavior or model isolation.
Only `OBSERVATION.json` is participant material. `SOURCE.json`, `PRESENTATION.json`,
capture receipts, inventories, the full support and all other exports stay with
the operator. The public manifest nested in the observation is the same
participant-permitted current-context manifest as the existing programme export.

## Source and input selection

Use an existing Python/NumPy environment and an ordinary operator-controlled
source tree. `SOURCE.json` pins this package and the unchanged bounded I/O/NPZ
decoder, original context identity roster, and historical ratio endpoint.
The operator supplies that manifest's exact SHA-256. Dependencies are captured,
authenticated and executed from those bytes without an ambient module cache.
The already executing launcher and Python installation remain trusted; this is
not adversarial host attestation or execution authority.

Production has no alternate-cohort argument. `present` selects the original
manifest/data descriptors for one fold/view from the pinned public
`paired-delivery-v1/SOURCE_INPUTS.json`, then reads only that exported
`manifest.json` and `data.npz`. Both pins are checked before decoding. No original
projection, other archive or protected file is read. Generated tests substitute
invented identity rosters in memory; this is not a production admission option.

The output contains `OBSERVATION.json` and operator-only `PRESENTATION.json`.
Preserve the returned presentation descriptor externally before delivery. The
payload is deterministic and capped at 512 KiB; the original input caps remain
256 KiB for data and 16 KiB for the manifest. A bound does not establish a model's
token capacity. A later backend must receive the whole context or refuse it;
truncation, selecting fewer examples or changing feature precision changes this
condition. No model/provider call is included here.

## First supplied response and complete collection

The participant returns only:

```json
{"schema":"neural031_direct_response_v1","request_id":"COPY_FROM_OBSERVATION","rows":[{"row_id":0,"prediction":1.0}]}
```

The example is schematic: every query row must appear in original order. The
request ID is supplied in the observation and needs no participant hash
calculation. Booleans, nonfinite/negative values, missing, duplicate, reordered
or extra rows and a different context/view identity are rejected.

`capture` first authenticates the selected presentation, then exclusively creates
the context capture directory. It retains `FIRST_RESPONSE.bin` before checking
the externally supplied response pin and response schema. A malformed first
answer leaves `FAILED.json` and cannot be replaced in that directory. A missing
or unreadable response still leaves the failed reserved directory. Oversize
responses are refused at the original 128 KiB input cap; these are not successful
captures and must not be retried as the same assigned attempt. Preserve failures
and report the study incomplete; do not select a replacement response or exclude
its requests. The package does not implement an alternative failure-scoring rule.

A valid capture also writes `predictions.json` in the original
`neural031_ordinary_prediction_v1` schema and `CAPTURE.json`. Preserve the returned
capture descriptor outside the capture tree. This establishes the first bytes
supplied to this local capture call, **not** the provider's actual first answer,
the transport history, truthful operator behavior or a fresh model context.

The operator assembles a complete inventory from those retained descriptors:

```json
{"schema":"neural031_numeric_capture_inventory_v1","condition":"neural031_direct_numeric_context_v1","source_sha256":"SELECTED_SOURCE_SHA256","captures":[{"fold":0,"view":"baseline","capture":{"bytes":1234,"sha256":"CAPTURE_SHA256"}}]}
```

It must contain exactly forty entries, ordered fold 0 baseline, fold 0 neural,
through fold 19 neural. Freeze its exact bytes/hash externally. It is an operator
record, never a participant input. Both presentation and capture roots use
`foldNN/{baseline,neural}`. Collection requires every selected capture's exact
bytes, then authenticates its presentation, first raw response and prediction.
A consistent rewrite of response, prediction and capture cannot borrow the old
externally selected inventory. The operator remains responsible for preserving
the true descriptors; self-consistent metadata is not an independent execution
attestation.

Only after all forty joins pass does collection call the unchanged historical
endpoint's `validate_all`. It writes `submission.json`, `support.json` and a
condition-specific `COLLECTION.json`, covering all 1,548 predictions. Missing,
extra or failed contexts cannot produce a collection. No target pathname is
accepted, and no scoring function is called. This does not certify a model's
training-only method or absence of information acquired outside the transport.

## Commands

All output directories must be fresh and their parents must already exist.
Paths and pins are operator inputs, not participant-selected operands:

```text
python -I -B observation.py --source-sha256 SOURCE_SHA256 present \
  --input ONE_EXISTING_EXPORT --fold 0 --view baseline --output FRESH_PRESENTATION

python -I -B observation.py --source-sha256 SOURCE_SHA256 capture \
  --presentation FRESH_PRESENTATION --presentation-bytes N --presentation-sha256 SHA256 \
  --response FIRST_RESPONSE_FILE --response-bytes N --response-sha256 SHA256 \
  --fold 0 --view baseline --output FRESH_CONTEXT_CAPTURE

python -I -B observation.py --source-sha256 SOURCE_SHA256 collect \
  --support ORIGINAL_SUPPORT_JSON --presentations COMPLETE_PRESENTATION_ROOT \
  --captures COMPLETE_CAPTURE_ROOT --inventory SELECTED_INVENTORY_JSON \
  --inventory-bytes N --inventory-sha256 SHA256 --output FRESH_COLLECTION
```

The old qualified ratio-1 control and its historical scorer binding are not
retargeted. A future direct/programme study must freeze one exact common scorer
version prospectively, alongside complete observed-input and method custody.
The cancellation-safe ratio-scoring-v2 exists separately; these utilities only
reuse the original schema validator and compute no metric. No new programme
budget is created: its original 480-second complete batch remains historical.
Model context, total authoring/inference budget and any native execution need
their own selection. No private store, provider connection, image download or
dependency installation is supplied by this package.

## Generated validation and limits

Run `python -I -B test_observation.py --scratch-root EXISTING_SCRATCH_PARENT`.
Controls use an invented complete 20-mouse, 774-request, forty-view panel with
731 observed and 43 unavailable underlying ratios. They exercise lossless
presentation, signed-zero/subnormal/maximum floats, training-only missingness,
cross-context refusal, irreversible local first-answer capture, externally
anchored complete custody and original output validation. No protected score,
authentic material, model, Docker process or old fixed-control replay is needed.
Temporary fixtures are removed and their cumulative writes are reported.

Source capability, authentic presentation qualification, actual model/tool
performance and scientific generalization remain separate. This package adds
no new task, empirical result, readiness promotion or claim that metadata proves
enforced no-tools/native understanding.
