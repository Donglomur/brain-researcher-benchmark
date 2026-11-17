# Voltron electrical NPZ decoder with explicit units

The existing electrical decoder accepts exactly three NPZ members. A retained
source inspection found **four** in the first deposited electrical NPZ:
`time.npy`, `voltage.npy`, `stimulus.npy`, and `units.npy`. The archive's central
extent was valid; its fourth entry caused the earlier intake refusal. This
package makes the already reviewed strict four-entry successor available in the
task repository. It preserves the original decoder and failed intake history.

`decoder.py` and `test_decoder.py` are byte-identical to the independently
reviewed source identified by [SOURCE_PINS.json](SOURCE_PINS.json). The retained
[prior review](PRIOR_SOURCE_REVIEW.json) applies to those exact two files. Its
README hash identifies the earlier external README; the current README is a
new publication note, not that reviewed file.

## Interface and scientific boundary

`describe_frame_times(npy_bytes, declared_frames)` retains the existing
finite, strictly increasing, exact-count native-clock checks.
`describe_sweep(npz_bytes)` validates the complete four-entry NPZ structure,
checks the units record **before any numerical channel**, and returns structural
descriptors for the three numerical vectors. Both accept byte strings; neither
reads files, downloads data, runs models, or writes arrays.

The units record must be exactly 152 bytes: NPY 1.0, a 118-byte header, little
endian Unicode `<U2`, shape `(3,)`, C order, and strings `s`, `mV`, `pA` in
that order. These correspond to time, voltage and injected-current stimulus in
the author notebook. The decoder rejects mismatched units rather than silently
converting them. It rejects missing, duplicate and arbitrary extra entries;
object/pickle metadata; unsupported archive geometry; bad CRCs; and incomplete
DEFLATE streams. Numerical vectors must have equal nontrivial lengths, finite
samples and a strictly increasing time channel. Existing bounds remain 12 MiB
per numerical NPY and 32 MiB total expanded NPZ content. The string record has
its own exact 152-byte limit.

The successor emits the native sample extrema and clock values as hexadecimal
floating values. It applies no unit scaling, clock offset, liquid-junction
correction, resampling, gap filling, filtering or spike detector. These
structural checks neither establish physical synchronization nor create valid
support or independent electrical event labels. This is an operator component;
its electrical descriptors are forbidden participant inputs.

The observed four-entry format and units are established for **one** retained
NPZ. The other 228 electrical NPZs must each satisfy this profile during any
future complete preparation; no extrapolated format qualification is claimed.
The original population stays 34 frame-time arrays and 229 electrical sweeps,
covering 34 movies, 12 cells and six deposited subject groups. No subset is
admitted as the complete benchmark. The metadata grouping still does not
resolve the paper's seven-mouse description.

## Verification and source evidence

Run the portable generated suite through the shared two-slot test pool:

```sh
python3 -I -S -B test_decoder.py -v
```

The suite contains 14 tests covering stored/DEFLATE data, descriptors and local
ZIP64 combinations, entry order, mixed signal endianness, unit schema/value
refusals, duplicate/missing/extra members, Unicode, header safety, CRC and extent
checks, channel lengths, finiteness and clock ordering. Generated inputs do not
establish authentic waveform preparation. The current execution receipt is
kept outside Git; historical review tests remain historical evidence.

The source collection is [Janelia collection v1](https://doi.org/10.25378/janelia.c.5325254.v1),
with semantics from the [author loader v1](https://doi.org/10.25378/janelia.14141609.v1).
The original [acquisition paper](https://doi.org/10.1016/j.celrep.2021.108954)
evaluates smoothed waveform error; this registration's prospective event-F1
endpoint remains a different task. No authentic waveform was read or decoded
for this publication, no new acquisition was made, and no new event reference,
optical trace, comparator output or participant trial was produced.

Qualification: **reviewed source component with generated controls**. Complete
authentic preparation, independent electrical annotations, label-independent
optical extraction, protected six-subject execution and access-condition
comparisons remain unfinished. This adds zero benchmark registrations and
makes no scientific performance or readiness claim. Canonical task, scorer,
registry and historical files remain unchanged; integration may link this
component without promoting readiness.
