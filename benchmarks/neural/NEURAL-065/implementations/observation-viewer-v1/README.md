# Complete EEG query observation presentation

This component closes the gap between the task's prepared binary EEG windows and
an inspectable participant observation. It creates an offline HTML collection
with every query in the evaluator's frozen query manifest. Each page contains
every original float64 sample and synthetic channel, relative sample times,
volts, an exact numerical table and a trace with typed channel/sample navigation.
It does not fit, filter, average, clip, resample or rank neural observations.

This is **observation presentation source**, not a completed direct-observation
or viewer benchmark. No authentic signal, participant, model or browser runtime
was run to qualify it. It does not enforce no-tools access, fresh case state,
calibration entitlement or matched compute. The canonical task's access and
scientific-readiness statuses remain unchanged. Programme results and future
responses to this presentation must remain separate conditions.

## Operator use

First prepare every selected EEG recording using
[`brainvision-observations-v1`](../brainvision-observations-v1/README.md), reconcile
the complete selected sentence population, and freeze the private evaluator
packet with the emitted observation hashes. Export its public query manifest
using `initial-evaluator-v1/evaluator.py queries`. The public manifest contains
only the packet digest, opaque query IDs and neural-asset hashes. This viewer
does not read the private packet, alignment plans, logs, transcripts or targets.

```sh
python3 view.py \
  --queries /operator/public/queries.json --queries-sha256 QUERY_FILE_SHA256 \
  --observations /operator/prepared/session-a/observations.json MANIFEST_A_SHA256 \
  --observations /operator/prepared/session-b/observations.json MANIFEST_B_SHA256 \
  --max-input-bytes FROZEN_INPUT_BYTE_LIMIT \
  --max-output-bytes FROZEN_OUTPUT_BYTE_LIMIT \
  --output /operator/delivery/query-viewer
```

Repeat `--observations` for all required prepared recordings. Hashes must come
from independently frozen preparation evidence. Input and output limits are
positive byte counts, fixed before export; output accounting includes HTML and
the collection receipt. Open the new `index.html` locally. Pages have no external
dependencies or network requests. Only this newly created directory is intended
for participant delivery; do not share operator source/parent directories.

The exporter joins by both opaque query ID and exact observation hash. It refuses
missing queries, duplicate observation IDs across sources, unknown fields,
noncanonical paths, incompatible shapes/units/axes, changed bytes, nonfinite
samples and symlinked assets. Query order follows the evaluator manifest.
Nonquery prepared windows may be present in input manifests; their signal bytes
are neither read nor exported. Full coverage here means the complete frozen
query manifest, not independent proof of authentic source-population inclusion.

Output is published atomically after validation; failed staging is removed and
existing outputs are never overwritten. Metadata reads are limited to 4 MiB per
file. This presentation profile supports at most 64 MiB of float64 data per
query. Larger windows are refused without cropping; an expanded profile needs
prospective resource and browser qualification. Exporter memory holds one query
and its encoded HTML at a time, plus manifest metadata. Base64 preserves exact
little-endian float64 bytes and expands signal storage by roughly one third.

## Participant observations

Each case page exposes only allowed signal and coordinate metadata. Select a
synthetic channel and first sample, then display 1–4096 consecutive samples.
Previous/next controls reach the entire original sequence. Every selected sample
appears in the trace and numerical table; no display decimation occurs. Times
are sample indices divided by the declared frequency, relative to the window,
with no absolute acquisition times or keypress markers. The voltage axis scales
to the current viewport and is labeled explicitly; compare numerical volts when
changing views. Synthetic channel IDs preserve source order, but electrode
locations and a shared cross-person anatomical map are unavailable.

This is a query-only transport. The independently frozen training/calibration
support and its declared per-person sentences/keystrokes must be delivered
separately and identically to each compared access condition. The query viewer
does not reveal target transcripts or use target-derived event assistance.

`collection.json` records the packet and input manifest digests, complete query
count, input bytes, and exact hashes/sizes of the HTML files. The command returns
the collection-file digest and total output bytes. This binds the generated
presentation; it does not attest source authenticity or operator isolation.

## Checks and remaining limits

```sh
python3 -I -B -m unittest discover -s tests -p 'test_view.py' -v
node tests/test_navigation.cjs
```

Generated controls cover complete joins across two preparations, evaluator order,
lossless raw bytes, units/dimensions, target and private-path exclusion, missing
cases, corrupt/nonfinite samples, unknown fields, symlinks, byte budgets, atomic
failure cleanup and the CLI. The Node control executes the inline script with a
generated DOM/canvas shim to check numerical rows, channel changes, boundary
navigation and finite plot coordinates for extreme values. It does not run a
browser. These controls do not establish browser usability on authentic
large recordings or unaided neural interpretation. Authentic alignment, physical
visits, population selection, template split, sensor interpretation, reference
decoder and matched language-only competence remain unqualified. The existing
typed-button CER endpoint, complete-scoring policy and source pins are unchanged.
