# Complete evaluation observation pages

NEURAL-058 currently supplies programme-side arrays but declares no restricted
viewer delivery. `viewer.py` supplies a host-side typed numeric page interface for
already admitted evaluation projections. Every original timestamp, spike event,
unit, anatomical coordinate/missingness flag, neural-domain interval and allowed
context value has a rendered place. Duplicate events are retained. This is a
source implementation of observation delivery and response validation; it does
not establish an operational viewer condition, no-tools result, full benchmark
qualification or measured neural understanding.

The authoritative scope remains 29 evaluation sessions from 13 held animals,
with all original emitted windows and timestamps. Training remains 423 sessions
from 126 separate source animals. Signed velocity and absolute speed remain two
separate response heads; no target metric, weighting, split, native source pin or
historical implementation is changed.

## Host integration

Use the existing `implementation-v1/program/corpus.py` loader on an independently
admitted evaluation role projection with `training=False`. Do not pass training
sessions or the private target/joins store. `required` must come from the admitted
complete evaluation roster, in original session-ordinal order, rather than being
inferred from whichever sessions happened to load. It contains exactly `session`,
`animal`, `session_ordinal` and `animal_ordinal` per row. Its aliases are opaque
prepared aliases. Failed loads are failures, not permission to shorten the list.

```python
from viewer import EvaluationViewer, parse_response

# Operator-only objects; never mount them in the participant environment.
viewer = EvaluationViewer(
    loaded_evaluation_sessions, required_evaluation_roster, role="J",
    page_rows=16, max_cells=selected_cell_allowance,
    max_actions=selected_action_allowance,
    max_svg_bytes=selected_rendered_byte_allowance,
)
navigation = viewer.catalog()
svg = viewer.view({
    "session": navigation[0]["session"],
    "query": navigation[0]["query"],
    "table": "context", "page": 0,
})
# The isolated host renders svg to an image at its native declared dimensions.
# Only that image and safe navigation metadata are delivered to the participant.
response = parse_response(received_utf8_bytes, max_bytes=selected_response_allowance)
complete_predictions = viewer.validate_response(response)
delivery_evidence = viewer.coverage()
```

The same API supports `role="C"` with exactly the same context, timestamp and
anatomy pages. `J` additionally includes all spikes and neural-domain intervals.
A context projection cannot receive a neural page. Rendering uses full
round-trip numeric decimals, not binned counts, a fitted decoder or rounded
plots. Anatomy missingness is explicit. Pages have at most 32 data rows, fixed
14-pixel text, dimensions bounded by 4096 by 848 pixels, and explicit row/page
indices. Empty spike support has one visible empty page. Unsupported text or a
page exceeding readable bounds fails instead of truncating information. The
renderer escapes text markup and does not emit filesystem locators, source IDs,
target values or target joins.

`view` accepts only the four typed action fields shown above. It cannot execute
code, access paths, filter events, fit a model, summarize selected units, or return
raw arrays. Returned SVG is a **host transport**, not participant content: a real
restricted-viewer deployment must render the image and isolate the instance,
inputs and SVG source from participant tools. Safe navigation metadata contains
only opaque session/animal/query aliases, source-owned session/animal ordinals,
table names and row/page counts. The animal grouping and ordinal fields preserve
the same permitted cross-session organization as the programme input. The transport
must keep the requested opaque identity attached to each image because visual
content can be identical across repeated windows.

## Coverage and responses

`coverage()` counts unique successfully returned pages across the entire required
roster. Repeated views consume budget without increasing coverage. Failed or
over-budget actions consume action allowance and do not count as delivered pages.
All pages, including empty-event pages, must be returned for
`complete_delivery=true`; this records delivery, not attention or comprehension.
An incomplete delivery cannot support a complete-information comparison. Source
availability for all cases does not mean a participant saw them.

Response JSON has the shape `session -> query -> [[velocity, speed], ...]`, in
original timestamp order within each window. Parse the original bytes with
`parse_response`, then validate them. Duplicate JSON keys, omissions, extra
sessions/windows, missing timestamps, missing heads, booleans and nonfinite
values are refused. Negative predictions are preserved. The validator never
imports target values, computes R-squared, clips predictions or invents missing
answers. A separately admitted late grader must join these complete outputs to
the protected targets and retain the canonical animal-weighted endpoint.

## Comparison and deployment limits

Select and freeze matching page size, action/byte/time budgets and information
exposure policies before comparing modes. Use all the same permitted neural
support and cases as the program condition. The additional J pages are the
intentional neural-versus-context treatment; changing page limits to make one
condition easier is not an established matched comparison. The renderer freezes
the numeric observation text at construction, but an independently authenticated
host must still bind input identities and transcripts to an immutable operation.

This package is not wired into the historic authenticated programme, runtime
registry or provider transport. It does not supply source-example delivery,
participant isolation, a browser/model image client, trained reference competence,
physical memory enforcement, a complete direct no-tools packet, or model trials.
The selected cell count bounds table construction work and retained logical
content; it is not an RSS bound. Whole-corpus materialization, renderer resources,
image rescaling and all declared budgets require authentic preflight. Large
complete populations may be infeasible for a selected participant context/budget;
that outcome must be reported, not repaired by dropping windows or animals.
Program-source presence cannot be reported as native/direct understanding.

## Generated controls

```sh
python3 -I -S -B benchmarks/neural/NEURAL-058/implementations/observation-viewer-v1/controls/test_viewer.py
```

The controls generate 29 sessions and 13 animals solely to exercise the software
contract. They check complete delivery, exact event multiplicity and decimals,
C/J common-page equality, target/locator exclusion, escaping, budget refusal and
complete two-head responses. They are not physiological data, competent-reference
qualification, a participant performance result or proof of authentic feasibility.

The optional generated adapter control exercises the existing corpus loader and
its real NumPy scalar/array types before calling the viewer:

```sh
python3 -I -B benchmarks/neural/NEURAL-058/implementations/observation-viewer-v1/controls/check_corpus_adapter.py \
  --programme-root /absolute/repository/benchmarks/neural/NEURAL-058/implementations/programme-source/implementation-v1/program \
  --scratch-parent /absolute/owned/scratch
```

It writes only generated temporary NPY/JSON fixtures below the explicit scratch
parent and removes them on exit. It requires an already available NumPy; it does
not install dependencies or qualify the programme's pinned numerical image.
