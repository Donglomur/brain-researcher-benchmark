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
