# Human-source recovery and endpoint limits

The new component computes the registered human manual-trace agreement endpoint
on a supplied, frozen alignment. It does not reconstruct the original aligned
trace panel. The source recovery below identifies consequential preparation and
reference-role gaps; it does not qualify reproduction or improvement. The
original Pt01–Pt03 cohort, per-patient Pearson metric, absence of a published
scalar aggregate and required neural-fidelity controls remain unchanged.

## Source roles recovered

The paper's code-availability section points to HumanNeuropixelsPipeline and
CorticalNeuropixelProcessingPipeline in addition to DREDge itself. Both were
inspected at immutable revisions; the exact retrieved and decoded-content hashes
are in [source-provenance.json](source-provenance.json).

The [human pipeline README at revision
d74413cb8ff48c6d52f11e8ce57a8a6829862c15](https://github.com/Center-For-Neurotechnology/HumanNeuropixelsPipeline/blob/d74413cb8ff48c6d52f11e8ce57a8a6829862c15/README.md)
describes `DepthMicronsTracking.csv` as the output of DREDge motion tracking.
It separately describes recording-specific metadata, channel selection and
subsequent voltage interpolation. This is evidence against treating every
`DepthMicronsTracking_Pt*.csv` name in the Dryad inventory as a manual reference.
The individual deposited CSV payloads were not opened, so their exact contents
and relationship to the published traces remain unverified. A DREDge output
must not be scored against itself as purported manual ground truth.

The [human preparation script](https://github.com/Center-For-Neurotechnology/HumanNeuropixelsPipeline/blob/d74413cb8ff48c6d52f11e8ce57a8a6829862c15/PreprocessingLoading/savingBinaryFilesorMotionRegistraton.m)
reads a separate recording-information spreadsheet. Its selected fields include
saved-channel count, depth limit and start/end times. In this pinned script,
channel selection uses the depth limit, while the time fields are saved into
channel-map metadata: the written signal matrix uses all time columns. Thus the
script and README do not by themselves recover the exact original temporal
crop. The inspected repository root, preprocessing directory and example-data
directory did not supply the referenced spreadsheet. That is a bounded source
finding, not a claim that the spreadsheet is unavailable everywhere.

## The manual-tracing example does not specify the paper comparison

The [manual pipeline README at revision
64e1949dd8ac44c0d8f0ac5329fc0a1297bef4e3](https://github.com/Center-For-Neurotechnology/CorticalNeuropixelProcessingPipeline/blob/64e1949dd8ac44c0d8f0ac5329fc0a1297bef4e3/README.md)
identifies its originating study as Paulk and colleagues' 2021 preprint. Its
workflow exports LFP surfaces, manually traces features in Blender, imports the
vertices and interpolates neural signals. The 2025 DREDge paper cites this
repository, but the example is not an authenticated Pt01–Pt03 correlation run.
Its README declares GPL version 2 or later, with separate component terms. No
upstream implementation code was copied into this new endpoint kernel.

The recovered scripts make the remaining alignment questions concrete:

- [`Export_STL.m`](https://github.com/Center-For-Neurotechnology/CorticalNeuropixelProcessingPipeline/blob/64e1949dd8ac44c0d8f0ac5329fc0a1297bef4e3/Export_STL.m)
  chooses a channel column and every fifth LFP sample for a surface. The factor
  is explicitly adjustable. The manual workflow also stretches the channel axis
  in Blender, so exported vertices are not self-describing physical coordinates.
- [`Load_CSV_from_blender.m`](https://github.com/Center-For-Neurotechnology/CorticalNeuropixelProcessingPipeline/blob/64e1949dd8ac44c0d8f0ac5329fc0a1297bef4e3/Load_CSV_from_blender.m)
  sorts vertices by their first coordinate, applies the example factor five to
  that coordinate, adds `START_TIME`, and applies a factor 0.07 to the absolute
  second coordinate. It does not establish original patient-specific units,
  origin, polarity or vertex selection for the reported correlations.
- [`read_LFP_from_bin.m`](https://github.com/Center-For-Neurotechnology/CorticalNeuropixelProcessingPipeline/blob/64e1949dd8ac44c0d8f0ac5329fc0a1297bef4e3/util/read_LFP_from_bin.m)
  converts its start/end arguments from seconds with a fixed 2500 Hz rate.
  The Blender import's addition of `START_TIME` to a sample-like coordinate
  cannot establish a general seconds-to-samples conversion. The provided
  [`main_pipeline.m`](https://github.com/Center-For-Neurotechnology/CorticalNeuropixelProcessingPipeline/blob/64e1949dd8ac44c0d8f0ac5329fc0a1297bef4e3/main_pipeline.m)
  uses a zero start, which cannot resolve the nonzero-origin ambiguity.
- [`Intarpolate_and_align_AP.m`](https://github.com/Center-For-Neurotechnology/CorticalNeuropixelProcessingPipeline/blob/64e1949dd8ac44c0d8f0ac5329fc0a1297bef4e3/Intarpolate_and_align_AP.m)
  removes duplicate trace coordinates, interpolates with `makima`, constructs
  LFP-sample support and expands it for 30000 Hz AP data. It serves AP voltage
  alignment, not the exact manual-versus-DREDge Pearson comparison. These
  duplicate, interpolation and boundary choices cannot silently become the
  source endpoint's matching rule.

No recovered script specifies the exact three manual traces and native DREDge
outputs, their paired temporal support, or the command producing the published
correlation vector. Positive affine coordinate conversion alone would not
change Pearson r; temporal alignment, sign and support still matter. The new
kernel therefore consumes an independently prepared exact pairing and performs
none of these unresolved transformations itself.

## Qualification and cost

The source acquisition retained 2,630,999 response-body bytes under reservation
`paper03-dredge003-source-01`, which is closed. There were 13 successful public
HTML responses, two GitHub API HTTP 403 responses and five raw-content TLS
failures with zero response-body bytes. Pinned source was recovered from normal
public GitHub blob pages. No recording, manual-reference payload, native author
inference, model fitting or candidate trial was acquired or executed. Prior
Dryad download failures were not repeated, and the large embedded demo notebook
was not downloaded.

Ten generated software controls pass, including independent review's preserved
large-offset Pearson counterexamples. Independent exact-rational checks confirm
the repaired numerical result. These controls establish computation and support
validation, not scientific reproduction. The operator still needs the original
recording-specific metadata, authenticated manual and author traces, original
preprocessing/alignment, reproduction tolerances, an improvement decision across
the full vector, dependence-aware uncertainty and fidelity evidence. Both paired
paper+data and paper+data+author-code conditions must preserve those same inputs
and endpoint. Canonical task/contract and historical source files were not
changed.
