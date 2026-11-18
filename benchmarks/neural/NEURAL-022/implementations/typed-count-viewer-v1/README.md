# Typed count views for active-to-passive transfer

This component adds an operator-side typed viewer and complete answer collector
for **NEURAL-022**. It consumes the existing committed numerical export, preserving
141 active calibration trials, all 92 queries, six 20 ms bins and 65 unit positions.
It adds no task, scientific result, authentic-data run or model evaluation.

The views are exact decimal **binned spike-count grids**, not raw voltage traces
or inferred within-bin spike rasters. Calibration views include their original
two-component nominal velocity labels. Query views include only opaque identity,
active/passive mode, commanded direction and counts. No query target, private
reference or score is read. The original public scientific excerpt remains
available, including historical information that was already exposed.

## Typed interface

`viewer.py` uses the standard library. The operator selects the SHA256 of an
accepted `numerical-observation-v1/EXPORT.json`; the reader authenticates that
file and its complete `OBSERVATION.json`, including the pinned predecessor source
and producer identities. It does not reopen prepared arrays or private files.
Commitments establish agreement with the operator's selection; they do not prove
that the selected observations are authentic. Source custody remains external.
The Python API also requires the exact manifest bytes and the operator-selected
manifest SHA256: `Session(observation_bytes, export_manifest_bytes, export_sha256)`.
It checks that the observation's extent and hash equal the selected manifest's
observation descriptor before creating session state. A standalone export hash
or descriptor cannot be paired with unrelated panel bytes.

```text
python3 -I -S -B benchmarks/neural/NEURAL-022/implementations/typed-count-viewer-v1/viewer.py \
  --export /absolute/accepted-numerical-export --export-sha256 OPERATOR_SELECTED_SHA256
```

The process accepts one bounded JSON object per line on stdin and replies with
one JSON object on stdout. Only these four actions exist:

```json
{"action":"about"}
{"action":"view","split":"training","index":0,"units":[0,65],"bins":[0,6]}
{"action":"view","split":"query","index":91,"units":[63,65],"bins":[5,6]}
{"action":"answer","index":91,"velocity":[0.02,-0.03]}
{"action":"finish"}
```

View indices preserve original public order. Unit and bin crops are half-open,
with no smoothing, normalization, hidden selection or arbitrary expression
evaluation. Every original cell remains requestable. Calibration access and
viewing particular crops are optional. Available information is distinguished
from information actually requested, which is recorded in the operator receipt.

Each first accepted answer is final; subsequent replacements are refused. All
92 answers are required before `finish`. Answers can arrive in any order, but
the completed prediction table uses the unchanged original public order and
`neural022_predictions_v1` schema. The existing public candidate validator accepts
this table. The artifact grader still requires its separate trusted submission
commitment after producer closure; this component does not dispatch that grader.
Do not label these predictions as a `direct_numerical_full_panel_v1` attempt by
passing them through that arm's collector: this viewer has its own condition and
receipt. Presentation, retrieval and first-final policy differ from the full-panel
arm, so a score difference would not isolate a causal effect of tool access.

The original passive 40-query loss, active 52-query secondary loss, all sixteen
mode-direction strata and seven signed reference comparisons remain unchanged.
The passive references used extra passive calibration labels. This component
does not implement kinematic matching or turn the exposed single-session result
into causal, online or cross-animal evidence.

## Bounds and evidence

The default operator session permits 4,096 attempted actions and 16 MiB of
participant replies. Source API limits may be frozen lower, but at least 327
actions and 12 MiB are required: generated worst-integer controls establish room
for `about`, all 233 complete views, all 92 answers and `finish`. Requests are
bounded to 4,096 bytes before hashing, a grid to 128 KiB, and the complete input
panel to 2 MiB. Oversize framing or exhausted capacity fails rather than
truncating inputs or admitting a partial answer. The operator receipt is capped
at 2 MiB. These are application bounds, not a wall-clock or operating-system
resource supervisor.

The receipt records input commitments, exact request/reply hashes, an ordered
event chain, requested crops, completeness and byte/action counts. The CLI writes
it to stderr after complete collection. An external operator must retain it,
freeze `SOURCE.json` and the executed code, observe successful process exit and
verify resource closure before accepting an attempt. A participant-facing
`finish` reply alone does not establish any of those facts. Abrupt termination
or early EOF does not produce a complete receipt.

## What remains unqualified

This is a typed operator API, **not a participant sandbox**. Do not expose its
Python object, source files or raw export to a participant in a proposed viewer
condition. A separate admitted controller must enforce filesystem, process,
network, tool, context, delivery and cumulative-resource boundaries.

Replies contain SVG strings with exact numeric text. Structural SVG tests do
not establish raster rendering, readable display, model vision or human-like
inspection. If a model receives SVG markup, report that representation honestly;
an image-only comparison needs an independently qualified rendering adapter.
The receipt explicitly marks provider delivery, isolation, no-tools behavior,
image rendering and scientific qualification as unverified.

## Maintained generated controls

```text
python3 -I -S -B benchmarks/neural/NEURAL-022/implementations/typed-count-viewer-v1/test_viewer.py
```

Thirteen test methods cover all 90,870 count cells and calibration labels, exact
crops, complete maximum-int64 capacity, original 92-row prediction validation,
first-final answers, partial-answer refusal, malformed/oversize actions, source
and shape changes, stale/mismatched export-to-observation binding, transcript
ordering, and absence of private-file reads in the
loader. The operator may supply `--repository ROOT` when validating a private
postimage against its pinned existing dependencies. Tests use generated data,
not authentic signals or models. No existing passing scientific or native run
is inherited by this component.
