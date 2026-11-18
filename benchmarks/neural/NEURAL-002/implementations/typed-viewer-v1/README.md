# MorseEEG bounded PNG views and response collection

This source component adds the missing task-specific rendering and response
collection primitives for NEURAL-002. It is **not an admitted viewer service**,
an operating-system sandbox, a no-tools model run or an authentic-data result.
The registered direct/viewer condition remains unqualified. It neither changes
the task definition nor marks a source or scientific gate as passed.

`FoldViewer` accepts the existing `morse_views` training/query manifest bytes,
exact window extent/SHA-256 pins, the six fixed-window certificate fields below,
and a trusted `read_window(opaque_alias) -> bytes` callback. It opens no files and
performs no network or numerical fitting. The callback and manifest/pin custody
need an independent operator and later process/transport qualification. A caller
asserting a certificate or digest is not proof of authentic source lineage.

The unchanged source representation is little-endian float32, C-order, 62 channel
slots by 301 samples, in microvolts. All 9,672 training rows must span 31 opaque
participant groups, six task/speed cells, 26 class indices and two repeats. All
312 query rows must cover the six cells equally. Query manifests reject labels,
participant identifiers, chronology, source paths and any extra field. The
operator must still authenticate the private query class coverage through the
existing full-cohort preparation; public unlabeled metadata cannot establish it.
All window pins are required, but source bodies are read only on valid view calls.

The certificate is an explicit projection of the existing provider/extraction
certificate: `source_commit`, `sampling_hz`, `units`, `channel_names`, `policy`,
and `bad_channel_policy`. It excludes native dtype/scaling implementation fields;
the values supplied here are already the unchanged `windows.extract` output.
The public 62-channel order must come from authenticated common metadata. No
channel names or source certificate are guessed. The PO4 and TP8 slots must be
zero in every captured window; the renderer never performs rereferencing.

## Public interactions

- `index(role, offset, limit)` pages at most 52 existing public records. Training
  records include their permitted group and class index; queries expose only an
  opaque alias and task/speed cell. All calibration rows remain accessible but
  calibration viewing is optional.
- `view(request)` accepts exactly `role`, `id`, `channel_start`, `channel_count`,
  `sample_start`, `sample_stop`, and `uv_per_division`. It displays one to eight
  contiguous channels and at least two samples, allowing every one of the 62
  channels and all 301 samples to be inspected. Stop indices are exclusive.
  Gains include 0.5, 1, 2, 5, 10, 20, 50, 100 and 200 microvolts per division,
  plus fixed powers of two from 2^-149 through 2^128. The latter cover the full
  finite float32 magnitude range without a data-derived display scale.
  There is no signal-dependent autoscaling, normalization, filtering
  or sample decimation. A renderer cannot undo preprocessing already performed
  upstream; that provenance remains an operator responsibility.
- A response contains one RGB PNG and a public legend: channel slots/names,
  selected sample/time bounds, microvolt scale and rendering conventions. Each
  channel occupies one row. Gray grid lines mark one vertical division; the
  center line is zero. Red marks indicate values outside the selected vertical
  range. Increase the fixed gain to inspect larger excursions or decrease it to
  inspect small values. Display pixels still quantize position; the renderer
  is not a lossless numerical-data channel. No dynamic amplitude repair is
  applied. The legend reports software-marker-relative time and does
  not claim physical acoustic onset. PNGs contain only IHDR/IDAT/IEND chunks;
  raw sample arrays or hidden target text are not attached to them.
- `answer({id, probabilities})` accepts the existing scorer's 26-class simplex,
  with tolerance 1e-6. The first accepted answer for an alias is final. No label
  or score feedback is returned. `finish()` requires all 312 query answers,
  closes the session and returns their canonical JSON digest plus rows. The
  host must retain this result immutably, close the participant transport, map
  aliases through the operator-only inverse, and join all 32 independent folds
  before invoking the unchanged full scorer. A returned hash alone does not
  prove durable custody or completed process termination.

## Remaining execution and scientific work

The host object/callback must never be exposed to participant code. This package
does not provide a framed remote transport, credential handling, filesystem
isolation, action budget, durable interaction transcript, outer process owner,
all-32-fold coordinator or raster-image delivery to an actual model. These must
be selected and qualified before the component can define an operational typed
viewer condition. A PNG returned by a Python function is not evidence that a
model received or understood that image. This is a tool-mediated viewer design,
not a no-tools direct-observation implementation.

Authentic complete BrainVision intake, source scaling/markers, acoustic-prefix
information opportunity, behavioral joins, reference competence and the complete
matched controls remain unresolved. The 500-ms window, source trigger classes,
32 participants and balanced-accuracy endpoint are preserved. No negative or
positive scientific conclusion follows from generated rendering tests.

`test_viewer.py` uses invented full-count metadata and tiny in-memory generated
window values. It checks complete support, strict field/identity boundaries,
PNG coordinates and physical gain, sample sensitivity, visible clipping,
no reads after rejected navigation, exact snapshot identity, bad-channel/finite
checks, optional calibration, complete immutable answers, and interoperability
with the existing source constants. Run it as a task-local component test:

```
python3 -B benchmarks/neural/NEURAL-002/implementations/typed-viewer-v1/test_viewer.py
```

The private construction run sets `MORSE_LEGACY_ROOT` to the existing read-only
registered-runtime directory for the source-contract check. In the intended
public location that directory is resolved as its sibling. Component enrollment
and CI command selection remain with the sole integrator; the test is not yet
claimed to be in hosted CI.
