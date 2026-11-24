# Fixed waveform observation for NEURAL-081

This component renders the already prepared single-query EEG window into four
PNG pages. It fills the missing task-specific waveform renderer and supplies
identical image bodies for a direct packet and a typed `view_page` projection.
It does not acquire EEG, prepare authentic windows, select demonstrations,
contact a model, supply process isolation, or qualify either access condition.
The existing program implementation and its source closure remain unchanged.

`observation.prepare_observation(npy_payload, context_alias=..., view=...)`
accepts one C-ordered little-endian float32 NPY array of shape `[64,512]`, in
**volts**, with the existing canonical channel order. It rejects malformed,
extra, nonfinite, object, wrong-shape, and wrong-dtype input. The source protocol
already defines 64-channel samplewise average reference and four-sample means
from the fixed 512-Hz crop; this renderer does no further preprocessing. The
NPY is parsed with bounded standard-library code and is never unpickled.

The four pages each show sixteen channels, in unchanged source order. Every
sample is plotted, with two horizontal pixels per 128-Hz output sample. The
horizontal coordinate is the start of each four-source-sample averaging bin,
relative to the four-second crop; the final sample starts at 3.9921875 seconds.
Volts are converted to microvolts only for display. Every row has the same fixed
vertical range of -100 to +100 microvolts. Values beyond it saturate and receive
visible red ticks. There is no automatic scaling, sample thinning, smoothing,
feature extraction, outcome-dependent selection, or channel rejection. Clipping
and rasterization are lossy observations and must be disclosed when comparing
these conditions with programs that receive full float32 arrays.

`observation.direct()` returns metadata and all four images. Calling
`observation.page({"action":"view_page", "page":0})` through page 3 returns
the corresponding identical image. Other actions, zoom/scale parameters, extra
fields, negative indices, boolean indices, and out-of-range pages are refused.
Both responses contain only the opaque context alias, declared view, public
geometry/channel/class information, and PNG image content. PNG files contain
only IHDR/IDAT/IEND chunks; raw arrays, source paths, event times, person IDs,
held labels and numeric trace metadata are absent. The object retains rendered
PNG bytes, not the input array. This is an allowlisted projection API, not a
security boundary: a qualified host must render privately and deliver only its
serialized response, never expose the object or input process to participants.

The declared `ZERO` view accepts only positive float32 zeros, retaining the same
geometry and class schema. It cannot derive zeros by opening EEG in a ZERO role.
The host supplies a distinct issued context alias and separately authorized
zero input. The renderer does not verify alias issuance, source eligibility,
cross-query state isolation, complete ten-person/twelve-class support, or
matched demonstration selection. Those remain host/preparation responsibilities.

The endpoint remains twelve probabilities ordered `[1,2,3,4,11,12,13,14,21,22,23,24]`
for the instructed excerpt, not verified subjective imagined melody. Existing
participant-macro scoring, full support, and the target-last grading boundary
remain authoritative. No response is graded by this module. Introducing these
images to a participant is a separately declared observation condition; it does
not silently alter the existing text/tool-based I or frozen-program F protocol.
Direct/viewer modes remain **not delivered** until matching demonstrations,
transport, isolation, complete support and real controlled execution are supplied.

The generated tests exercise exact volts-to-microvolts geometry, an off-grid
single-sample transient, the final sample, first/last channel page mapping,
positive/negative clipping, EEG/ZERO geometry, direct/viewer image identity,
primitive NPY rejection, and the response allowlist. They demonstrate software
behavior only. Run them through the shared lightweight test pool as required by
the parallel builder policy; no authentic data or model calls are used.


## Complete matched demonstration projection

`session.prepare_session(query_npy, context_alias=..., view=...,
training_rows=..., expected_training_aliases=..., load_training_window=...)`
adds a host-side session over the existing renderer. The host supplies all
permitted training rows in the same order as the matched program condition's
admitted `train_rows.json`; the independent `expected_training_aliases` list
must match exactly. Each training row has only `row_alias`, `group_alias`,
`label`, and `npy_sha256`. The label is the permitted training instruction class;
there is no query-label argument. The session requires unique row aliases,
excludes the current query alias, and requires all twelve canonical classes in
each of exactly nine opaque training groups. It neither samples demonstrations
nor selects apparently informative trials. Metadata is detached at admission so
later caller mutation cannot relabel a demonstration.

The private loader receives only an admitted training alias. Its returned bytes
must match the row's SHA256 before strict waveform decoding and rendering. In a
ZERO session, every loaded training window must independently contain positive
float32 zeros; a matching hash does not bypass that rule. Missing, changed or
invalid input raises an error rather than skipping a demonstration. The host
must bind these pins and labels to the actual complete prepared training role,
exclude the held participant, and charge all preparation, repeated rendering,
reads and delivery. Supplied aliases and coverage checks do not authenticate
source provenance: two consistently incomplete host inputs cannot prove full
source coverage.

`session.metadata()` supplies the complete permitted labeled roster without
opening training waveforms. `session.direct_packets()` streams every labeled
four-page training observation in that order, then one unlabeled four-page
query. The host must exhaust and deliver the entire stream before accepting a
direct prediction. An interrupted prefix is not a complete observation; a
qualified transport must fail closed rather than silently truncating it. The
session does not predeclare that complete support will fit a provider context.
No smaller demonstration subset or larger resource allocation is authorized by
this interface.

`session.page({"action":"view_page", "row_alias":..., "page":0})` exposes
only a page of one permitted demonstration or the current query. A training
reply carries its allowed group and label; a query reply carries neither. The
image response is the existing fixed projection, byte-identical to the matching
direct packet. Unsupported actions, scales, pages and other-query aliases fail
before any training loader call. The private pins and loader do not appear in
serialized responses. Only those responses may be exposed to participants.
Loader failures become a generic unavailable-observation error; original loader
diagnostics and exception context remain private host material. A host must
never send traceback or exception-object details as a participant response.

These are source interfaces for a separately declared observation condition.
They do not change F/I permissions, add fitted-reference outputs to a direct
condition, establish identical information to the full-precision program input,
or qualify model transport or isolation. Direct/viewer conditions remain not
delivered pending authentic complete input and independent runtime qualification.
The endpoint and existing full-study scorer are unchanged. Generated session
controls test complete roster joins, actual direct/viewer image correspondence,
missing/changed support, label separation, ZERO enforcement and rejection before
reads; they are not neural understanding or performance evidence.
