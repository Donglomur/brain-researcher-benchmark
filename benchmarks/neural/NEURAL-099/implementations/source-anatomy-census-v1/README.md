# Source anatomy and observation census

This component inspects the complete, authenticated 26-file MGN recording release
for NEURAL-099. It recovers unit-to-contact anatomy, source cluster labels, clock
declarations and available observation metadata. It does not read spike values,
waveforms, response targets or images, and it does not compute a firing-rate score.

`SOURCES.json` pins every file in DANDI **001421 / 0.250521.2343**: 455,615,424
bytes in total. The files were already available for this source audit; no new
recording was downloaded. Raw files and the detailed census remain outside Git.
The data are CC BY 4.0; the [versioned release](https://doi.org/10.48324/dandi.001421/0.250521.2343)
and [source paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC12216178/) identify the
authors and acquisition.

## Run the metadata inspection

Use Python 3.11 or later with NumPy and h5py. Supply the directory containing the
26 original NWB basenames; the output must be a fresh file.

```sh
python inspect_metadata.py \
  --raw-root /path/to/authenticated-mgn-nwb-files \
  --output /path/to/external-evidence/mgn-metadata.json
```

The inspector verifies all source bytes against the packaged pins before reading
allowlisted metadata values. It preserves integer unit IDs and contact-row
references, including repeated contact assignments. Response/index/waveform
objects cannot be read through a permitted metadata-name alias. Other dataset
headers are inspected without loading their numerical values. The report retains
unassigned anatomical labels, literal coordinates, execution-source hash and
dependency versions. It applies no physical-unit conversion or unit selection.

## What the complete source census establishes

All 26 files declare NWB 2.7.0. They contain 2,053 sorted source clusters:
458 labeled `good` and 1,595 labeled `mua`. These are source clusters, not a count
of independent biological neurons. Their referenced electrode locations are:

| Literal source location | Declared clusters |
| --- | ---: |
| `MGv` | 948 |
| `MGd` | 96 |
| `MGm` | 143 |
| `MZMG` | 93 |
| `BIC` | 81 |
| `SG` | 26 |
| Blank / unassigned | 666 |

The broad probe-group label `MGN` cannot replace these contact assignments.
Named strata can support a future region-specific target; unassigned clusters
must remain explicit. This census does not merge `SG` into `MGm`, merge `MZMG`
into `MGv`, assign blank contacts, or choose favorable regional support.

The exact [NWB 2.7.0 Units schema](https://github.com/NeurodataWithoutBorders/nwb-schema/blob/2.7.0/core/nwb.misc.yaml)
defines `spike_times` in seconds. The
[file schema](https://github.com/NeurodataWithoutBorders/nwb-schema/blob/2.7.0/core/nwb.file.yaml)
defines the common reference time. Together with the paper's Open Ephys,
Kilosort 2.5, Phy and Bombcell methods, this supports calling the released values
**deposited spike events**. The Units group's waveform-voltage wording does not
change timestamp units.

All files have 64 contact coordinates with literal `x=z=0` and `y=20,40,...,1280`.
NWB 2.7.0 does not declare units for these electrode coordinate columns. The
paper reports 20-micrometer probe spacing, but that compatibility does not
establish the deposited coordinate origin, frame or anatomical transformation.
No automatic depth scaling is justified by this census.

## What still prevents physiological rate qualification

No MGN file supplies `units/obs_intervals`. That field is **not mandatory evidence**:
an authenticated continuous-recording duration, common clock and unit support
could instead establish observation coverage. Neither such a bridge nor the
original converter was recovered from the inspected release and bounded official
source search. Trial stop times describe click pulses; image clocks and first/last
spikes are not a substitute for recorded neural exposure. A source cluster with
zero released events in a bin is therefore not independently verified observed
silence in that bin.

Physiological rates need justified time exposure and an eligible source-cluster
denominator for each named region. The earlier all-cluster, fixed-window nominal
rate packet does not supply those proofs. This component preserves that packet
and does not reclassify its results as the current anatomical prediction target.

Animal grouping also needs care. The paper explicitly describes MGN recordings
following A1 recordings in some mice. The complete source inventories share the
exact subject identifier `HK210212` between archives 001419 and 001421. Group that
identity if combining archives; absence of other exact-name overlaps does not
resolve differently named aliases. The IC archive has 13 files but 12 declared
subject identifiers, whereas the paper describes 13 mice; this discrepancy stays
unresolved rather than treating files as independent animals.

`SOURCE_FINDINGS.json` binds the inspected source and retained review receipts.
These are source-construction findings, with no candidate/model runs, physiological
rate score, source-paper reproduction, or scientific-readiness promotion.
