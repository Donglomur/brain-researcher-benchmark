# Restricted omission-history display

This component renders the existing complete paired direct-numeric requests as
one standalone HTML page per event and information condition. N includes a plot
and exact numeric table of all twelve preceding population-history bins. T
contains the same preceding stimuli, timing, seven recording-context fields and
opaque grouping tokens, with no neural history. Every page states the baseline,
units, three target intervals and response schema. There are no scripts, network
resources, target lookups, hidden query rows or links to other events.

This adds a restricted display and response path. It does not qualify a browser,
host isolation, participant, reference model, native data support or the task's
scientific endpoint. The plot is a presentation of the same numbers, not a raw
cell-level trace. It does not change the 73/15/19 mouse split, native frame guards,
eligible events, FIT-only scaling or hierarchical scoring.

Use already prepared allowed views outside the repository:

```sh
python3 -I -B viewer.py render \
  --timing /operator/query-T.json --neural /operator/query-N.json \
  --output /operator/restricted-pages
```

The new output directory contains every T/N page in a complete `MANIFEST.json`
with its event, condition, ordinal, request binding, presentation binding, byte
count and file digest. The command prints the canonical manifest SHA-256. The
manifest is written last; a failure leaves an incomplete directory without a
completion manifest. Existing outputs cannot be overwritten. The operator must
retain a failed partial directory as failure evidence, not use it as a subset.

The trusted host must verify each page's byte count and digest against the frozen
manifest and deliver **one page at a time in a fresh participant context**. Do not
give the participant the whole output directory or operator manifest. Keep T and
N contexts separate, prohibit source lookup/tools/query feedback, and schedule
every manifest entry. Scrolling or browser magnification reveals only that
page's existing observations. Browser, memory and network enforcement require
independent host qualification; CSP and prompt text alone cannot establish it.

Each page supplies a copyable response template. Replace the three null
placeholders with finite numbers. Save exactly one response per page in manifest
order, including its `presentation_sha256`. A direct-numeric response without
that field is rejected, and collected results are labeled `restricted_viewer`.

```sh
python3 -I -B viewer.py collect \
  --timing /operator/query-T.json --neural /operator/query-N.json \
  --responses /operator/viewer-responses.json \
  --manifest-sha256 PRECOMMITTED_MANIFEST_SHA256 \
  --output /operator/viewer-predictions.json
```

Collection regenerates the same pages and checks the manifest hash before
admitting responses. It rejects a missing, reordered, malformed or differently
bound response rather than scoring a subset. The resulting `predictions.T` and
`predictions.N` use the unchanged original scorer format. No query targets are opened
and no score is computed. Hashes bind content, not producer authenticity or what
the participant actually saw.

Optional fixed FIT demonstrations use the existing numeric-delivery protocol:
add `--fit-timing`, `--fit-neural` and `--demonstration-ids` to both commands. Both
complete 73-mouse FIT views and the same explicit ordered ID list are required.
Only those selected FIT targets are displayed, in the same order in T and N.
The condition is recorded separately from zero-shot; demonstration selection and
budget must be frozen prospectively and matched to any comparator. Zero-shot
accepts no FIT inputs. No demonstration count or selection policy is invented.

The renderer preserves every supplied value in text tables; plotting uses a
stable symmetric scale and never clips the underlying numeric observations.
All prepared query rows must include the same 19 query mice and paired schedule.
Authentic completeness still depends on the preparation producer's independent
native-frame and census proof. This module cannot discover omitted native events.
Construction materializes the complete request bundle and rendered pages in
memory. Full authentic event counts and rendering memory remain unmeasured;
operators must qualify and budget them before a complete participant run.

Run `python3 -I -B -m unittest discover -s . -p test_viewer.py -v` from this
directory. Generated controls check full paired support, every displayed field,
separate event pages, allowed FIT targets, extreme-value plot arithmetic, escaped
markup, absence of executable/external content, distinct response bindings and a
render/collect CLI round trip. They establish software behavior only, not actual
browser display, neural interpretation or model/program performance. Standard
library only; runtime source dependencies are recorded in `SOURCE.json`.
