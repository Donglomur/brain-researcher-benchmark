# Direct numeric paired delivery

This component builds a direct no-tools request for **every event in both T and
N prepared query views**, then collects exactly one three-bin response per
request. It fills the missing numeric/context-to-response path identified in
NEURAL-063's understanding contract. It consumes `neural063_rows_v2` exports from
the existing preparation implementation. It does not read NWB files, private
query targets, native clocks, or model assets.

The endpoint remains population-average dF/F in `[0,.2)`, `[.2,.4)` and `[.4,.6)`
seconds after the scheduled omission, minus the final `[-.2,0)` history-bin mean.
Values are dimensionless dF/F, not percentages. N delivers all 12 explicit history
bins; its last bin is structurally zero. T delivers the identical preceding
stimulus timing, context and opaque hierarchy IDs. T/N source rows must match
exactly after removal of N's history. All 19 query mice and every supplied event
must remain in both conditions. The producer remains responsible for proving
that these supplied rows represent the complete eligible original schedule.

The request includes an instruction, units, half-open bin edges, the complete
allowed observation, and a content digest. Collection binds each answer to its
event, information condition and request digest. Missing/extra/reordered answers,
nonfinite values, booleans, query targets, extra input fields and mismatched paired
observations fail. The two output `predictions.T` and `predictions.N` lists use the
unchanged existing scorer's `{id, values}` format. Collection does not score them.

Zero-shot construction accepts no FIT inputs. The optional demonstration condition
requires both complete 73-mouse FIT exports and an explicit ordered list of FIT
event IDs frozen before participant delivery. Identical demonstration events and
targets appear in T and N; only N receives their neural history. FIT/query mouse,
session, experiment and event IDs must be disjoint. A demonstration condition is
recorded separately from zero-shot, and its input digests change the bundle
binding. Demonstration selection policy and count require a prospective operator
protocol; this component does not select examples from query outcomes.

From this directory, using existing prepared inputs outside the repository:

```sh
python3 -I -B direct_delivery.py build \
  --timing /operator/query-T.json --neural /operator/query-N.json \
  --output /operator/direct-requests.json
```

The command prints the canonical SHA-256 of the request bundle. The trusted host
delivers **one request at a time to a fresh participant context**, with no tools,
network/source retrieval, cross-event memory or query feedback. T and N must run
in distinct contexts so N cannot leak history to T. Save response objects in the
bundle's order (T then N per event). Each object contains exactly
`request_sha256`, `id`, `information` and `values`. This implementation does not
launch or attest a host sandbox; a prompt instruction alone cannot enforce these
boundaries. Only the request should reach the participant, not the full paired
bundle or the operator input files.

```sh
python3 -I -B direct_delivery.py collect \
  --timing /operator/query-T.json --neural /operator/query-N.json \
  --responses /operator/direct-responses.json \
  --requests-sha256 PRECOMMITTED_BUNDLE_SHA256 \
  --output /operator/direct-predictions.json
```

For demonstrations, supply the same `--fit-timing`, `--fit-neural` and
`--demonstration-ids` JSON files at both build and collect. Collection regenerates
the original requests from allowed inputs and checks their precommitted digest
before admitting responses. Outputs use exclusive creation and cannot overwrite
a frozen artifact. API callers must pass the trusted `build()` bundle to
`collect()` and the operator's pre-response digest, not an untrusted submitted
bundle/digest pair. Hashes bind content; they do not authenticate the data producer.

Keep direct numeric results separate from typed-viewer interpretation, per-event
tool-assisted investigation and frozen prediction programs. No viewer, actual
participant execution, reference qualification, native support qualification or
scientific performance result is established here. This is a generated-control
tested delivery/collection component; the overall task remains unqualified.

Implementation references are the unchanged task and understanding contracts,
the existing preparation's `algorithm.py`, `references/schema.py` and
`owner/scoring.py`. The primary source release is Allen Visual Behavior manifest
v1.1.0 / AllenSDK commit `a56bd8ea7613a812334602b64746cdd30c325a96`, already
identified by the task. No new source download was performed. `SOURCE.json`
records exact local source hashes; historical descriptors are unchanged.

Run `test_direct_delivery.py` only through the reviewed shared test pool. Tests
use generated 19-mouse query and 73-mouse FIT rows, never authentic target values.
They cover exact T/N delivery, explicit demonstration exposure, cross-split
identity leakage, forbidden fields, support loss, malformed responses, request
tampering, and an actual CLI build/collect round trip.
