# Complete Bugeon native inputs for NuCLR

This owner-side component connects the complete original Bugeon calcium inputs
to the existing nine source split projections and readout interface. It prepares
all **17 sessions, 69 subrecordings and 10,153 session-neuron observations**.
These are observations of neurons, including matched repeated cells; they are
not 10,153 independent biological replicates. No model is trained or scored.

The original source is [Figshare file 38046633](https://ndownloader.figshare.com/files/38046633),
`Bugeon et al 2022 v2.zip`, 946,468,709 bytes, publisher MD5
`4556ed80ce98ca13f909129e25f60f3a`. [source-profile.json](source-profile.json)
preserves the complete original central-directory inventory and its exact order.
Full-file identity and every original member name, size, compression method and
CRC must match before scientific extraction. A newly computed whole-file SHA256
is retained; the profile is not a claim that the complete archive has already
been acquired or run in this construction revision.

## Native input preservation

`prepare_source` extracts exactly 257 required members into new private files:
all 69 calcium/time pairs, and seven neuron files for each session. It retains
the original NPY bytes, array axes, row order and C/Fortran storage order. All
1102 archive members remain accounted for by the full source inventory; other
behavioral/image products stay in the authenticated original archive.

The release's [dataset descriptor](https://ndownloader.figshare.com/files/38046648)
defines the signal as **deconvolved calcium activity in arbitrary units**. The
author's variable name `df_over_f` does not change those units. Representative
authenticated headers show float32 Fortran-order frame-by-neuron activity and
float64 column-vector clocks. The reader checks every actual prepared header
and payload extent; representative observations do not stand in for full intake.
Numeric NPY loading never enables pickle or arbitrary object constructors.

Source neuron IDs are exactly `session_id_u{zero_based_column}`. All native label
rows, activity columns and source CSV identities must agree. Each session keeps
every experiment, including both `Blank/01` and `Blank/02` in the last SB030
session. There is no convenient-session subset or silent nonfinite-value deletion.

The complete native depth, plane, receptive-field and corrected-stack-position
values remain separate from the author's CSV strings. The package verifies
their row geometry and preserves finite/nonfinite values explicitly; it does
not assert an unverified numerical CSV conversion or invent a matching tolerance.
Identity and the source E/I/subclass labels are checked exactly. Eleven-class
labels come from the original split maps, including their merged source
categories; a subclass-prefix rule is not substituted.

Native `UniqueID` values identify source-matched repeated cells; NaN means
unmatched, and zero is a valid match. The package preserves source values and
forms subject-scoped relationship keys. It does not assert a global cross-animal
namespace, merge observations, change splits, or assign unmatched rows fake
biological identities. Native numeric metadata and original author CSV rows stay
in the private manifest. The source preparation ignores plane-offset timing;
this component preserves its shared frame clock.

## Explicit current-release ordering

[order-adoption.json](order-adoption.json) binds the reviewed condition
`nuclr_current_release_zip_experiment_order_v1`. The order is the exact original
ZIP central directory's first appearance of each experiment. Within each block,
all native frames and columns remain unchanged. The source's `i * 3600` timestamp
offsets are retained, with native/shifted extents, inter-block gaps and potential
240-second cross-experiment second-view boundaries recorded. Nonmonotonic
concatenation fails; no fabricated gap, reordering, interpolation or cropping
makes the input fit a sampler.

Normalization uses the exact full-session flattened 99th percentile. It is not
per-neuron, per-experiment, approximate, or fitted only to a chosen time window.
The preparation records NumPy version, percentile scalar dtype and resulting
normalized dtype. The lazy reader restores that scalar dtype before division.
Normalization therefore exposes the complete source session in the same way as
the author code; this is not independent train-only preprocessing.

The original author used unsorted filesystem iteration. Archive order is an
explicit reproducible current-release condition, not recovered historical order.
Although complete block permutation leaves the global percentile unchanged, it
can change seeded sampling, second views, batch order, time-limited observations
and distributed remainder truncation. Historical seeds or paper results are not
claimed equivalent. Downstream sampler settings, observation limits and device
count remain null until separately frozen for an actual model operation. This
input preparation performs no sampling or observation truncation.

## Original split and readout boundaries

`dependencies.py` authenticates and privately loads the unchanged sibling
`source-splits-v2` and `initial-evaluator-v1` code. Later topology checks use the
authenticated readout module, without reopening an unpinned evaluator path.
The split archive is recovered by its existing constructor-free parser.

All nine label/exposure projections are retained. Every original label-map row
gets an explicit native session/column address in the original map order, with
the original CV/outer memberships and development exclusions unchanged. The
E/I-inductive source artifact remains present and fails the existing selector:
its CV training includes held-out SB028 test units. It is not repaired or dropped
to turn the other eight records into a completed benchmark.

The bridge records `resample` as the required author balancing policy. The three
transductive routes remain unresolved: the README prescribes resampling, while
the pinned single-split script rejects that option and uses class weighting.
This component does not replace that script silently. A structurally valid
packet is not a qualified original execution route or an authenticated embedding
fit. Original paper-era split equality, five-seed comparators, the stronger
LOLCAT companion and scientific comparison rules remain separate requirements.

## Operator APIs

Use an existing Python/NumPy environment. Source construction does not install
dependencies. Full authentic acquisition and preparation must first receive
their finite resource allocation and operation review.

```sh
python3 native.py \
  --raw-archive /absolute/private/Bugeon-v2.zip \
  --metadata-archive /absolute/private/neuron_metadata.zip \
  --split-archive /absolute/private/splits.zip \
  --owner-output /absolute/private/new-preparation
```

The output directory must be new. Original members and JSON files use private
permissions. `COMPLETE.json` is written last; failed partial directories retain
`INCOMPLETE.json` and cannot be opened as complete. The native output contains
source labels and complete identities and must remain assessor-side.

```python
from native import NativeInputs, readout_packet

inputs = NativeInputs(private_preparation)
# Full population columns, a bounded interval of an exact original block:
block = inputs.read_block("sb025_20191004", "Blank/01", 0, 100)
# Joining is by explicit addresses, preserving the caller's original map order:
addresses = inputs.native_addresses(ordered_source_ids)
# Owner-supplied embeddings require their own actual fit/exposure evidence:
packet = readout_packet(joined_source_panel, checkpoints, context_variant,
                        frozen_representation_training_sessions,
                        inputs.receipt_sha256)
```

`readout_packet` calls the existing source selector before returning the existing
validator's packet; invalid E/I-inductive selection refuses. It forces the
recorded resampling policy but does not execute any fit or remove the
transductive execution-route hold. Model-side creation of the checkpoint arrays
is outside this component. Paper reproduction and improvement remain separate
outcomes under both information conditions.

The current prepared-block reader reauthenticates whole member SHA256s before
reading an interval. It returns copied arrays, preserves every neuron column,
and keeps source labels out of that numerical return. This is an owner IO API,
not participant isolation or a qualified high-throughput training runtime.

## Validation and qualification

Run independent generated controls from this directory with
`python3 -B -m unittest test_native_inputs -v`, subject to the operator's resource
controls. Controls use invented activity and metadata; they do not establish
authentic source preparation, benchmark difficulty, model success or readiness.
Source metadata review separately authenticated the cached neuron archive,
original label-map joins, official descriptor and six representative NPY headers.
It decoded no authentic neural array values.

Complete source acquisition/preparation, downstream sampler/exposure contracts,
source readout-route reconciliation, competent references, protected participant
execution and empirical reproduction/improvement qualification remain open.
This component creates no new task IDs and supplies no performance result.
