# Original MATLAB source admission and locked-array normalization

This component adds two executable source operations for **NEURAL-025**:

1. `inspect-raw` checks every one of the ten original imaging MAT files against
   the published filename, size and MD5, plus an operator-pinned SHA-256. It
   reads only the requested trial eligibility/identity fields and small ROI
   timing metadata, preserves every raw trial and exclusion reason, and records
   the complete selected original trial-number sequence.
2. `normalize-locked` reads the author's **pre-ZETA/PCA** `kinematics`, `neurons`
   and `M` structures. It checks them against the pinned raw inspection, selects
   the exact 51 rows from −100 to +400 ms without interpolation, and creates the
   existing private `dataset`, `protocol` and `context` request. The existing
   metadata-only split freezer and normalized-data validator are called directly.

No model is fitted or scored by either operation. These are operator commands;
**the resulting normalized request contains private query targets**. Use the
separate [participant delivery](../participant-delivery-v1/README.md) to produce
an allowed participant packet. Do not give this request or the raw inspection to
an evaluated participant.

## Actual source format and source boundary

A bounded HTTP range read of original Figshare file `60333002` returned a
MATLAB 7.3 header and the HDF5 signature at byte 512. The complete article
metadata identifies all ten imaging assets as `application/x-hdf`. The copied
[asset record](PRIMARY_ASSETS.json) preserves their identifiers, sizes, published
MD5s and the exact metadata/header evidence. None of those ten complete files
was downloaded or scientifically processed during construction.

The reader supports MATLAB 7.3/HDF5 struct arrays, internal object references,
scalar nested structs, logical/numeric matrices, UTF-16 character vectors and
cell-string metadata. It reverses HDF5 storage axes back to MATLAB axes. It
refuses MATLAB v5, sparse/complex/compound numeric data, region references,
external storage, virtual datasets, nonlocal HDF5 links and unsupported nesting.
Every requested dataset is charged against a decoded-element bound before its
contents are read. Unrequested signal and pose fields are not loaded by
`inspect-raw`. Native HDF5 metadata allocation and native library behavior still
require an externally bounded process; this code is not an OS sandbox.

The pinned author's [loadLockSave source](loadLockSave.source.m) explicitly
creates the joint-angle `liftLocked` files using **all neurons**, a
−200:10:800 ms grid, 35 ms neural smoothing and `liftTimeDLC`. It stores returned
configuration in `M.config`; `loadLock4Decode` supplies `config.datasetInfo`.
Its `save` call does not set a serialization version. There is **no released
liftLocked file in the captured Figshare file list**. An authentic author-created
locked export, saved as MATLAB 7.3 without altering values, is therefore still
an external prerequisite for `normalize-locked`. This adapter does not perform
raw-to-locked extraction or replace the missing inverse-kinematics helper.

Primary source: [GSK26-public pinned revision](https://github.com/kaufmanlab/GSK26-public/tree/815b610b3beddfed5a3abf611d3a465ab9e4ce5c),
[original data release](https://doi.org/10.6084/m9.figshare.28326998.v1), and
[loadLockSave.m](https://github.com/kaufmanlab/GSK26-public/blob/815b610b3beddfed5a3abf611d3a465ab9e4ce5c/preproc/loadLockSave.m).
The original source is CC0-1.0; data rights are a separate release requirement.

## Raw inspection inputs

The JSON manifest is pinned by the exact SHA-256 of its bytes. It has:

- `schema: "calcium_raw_mat73_manifest_v1"` and the exact `author_commit` above.
- `limits`: positive integer `max_file_bytes`,
  `max_decoded_elements_per_file`, `max_trials_per_session`.
- `sessions`: exactly the ten session IDs in `PRIMARY_ASSETS.json`, each with
  `session_id`, a relative `path`, exact `bytes`, and lowercase `sha256`.

The filename and byte count must match the fixed published inventory; checksums
are computed over the whole file. All ten advertised imaging files together
contain **12,707,357,935 bytes**. That source size is not a new download approval
or a claim that the files are locally available. Each full-file inspection needs
an appropriate admitted I/O/time allocation, even though only scalar metadata
is subsequently decoded.

The raw eligibility rule preserves the author expression:

```
success & ~isnan(grabTimeC) & liftRT<500 & goodDLC==1
& wrongZoneFirst==0 & movementTime<500 & timeToContact<1000
& has_radical==1
```

Native trial numbers must be unique positive exact integers. Binary flags and
finite scalar timing values are required, except that NaN timing is retained as
an author-defined exclusion. Nonfinite values outside that supported domain
abort inspection; they are not silently counted as author exclusions. In
particular, the original MATLAB expression could admit an infinite non-NaN
`grabTimeC` or negative-infinite duration. This adapter does not claim parity
outside its documented strict domain. The source-selection requirement for
`has_radical` is preserved even for the smoothed-event condition.

The output retains original order, all selected/excluded trials, source SHA-256,
ROI-lag vector length and fingerprint, and the `R(trialNumber)` indexing
check. Mouse identity and the date prefix are checked directly. Checksums match
published metadata; correct biological contents, extraction and clocks still
require scientific/native review.

## Locked normalization inputs

The second manifest has:

- `schema: "calcium_locked_mat73_manifest_v1"`, exact `author_commit`.
- `raw_inspection`: relative `path` and exact byte `sha256` for the complete raw
  inspection emitted above. A caller-provided hash binds this evidence; it does
  not independently attest which process produced it.
- `io_limits`: `max_file_bytes`, `max_decoded_elements_per_file`, and
  `max_raw_report_bytes`, all positive integers.
- `recipe`: the existing prospective within-mouse parameters: `window_ms`
  `[-100,400]`, `grid_step_ms` `10`, `target_field` (`jointAngles` or
  `jointVelocities`), `feature_variant` `smoothed_deconvolved_events`,
  `split_seed`, `cell_budget`, `pca_components`, `ridge_alpha`, and the existing
  normalized protocol's `limits` object. The published prospective recipe is
  seed 240926, 100 cells, 90 PCA components and ridge alpha 1. Smaller generated
  software fixtures are not qualified benchmark variants.
- `sessions`: ten entries with `session_id`, relative locked-MAT `path`, exact
  `bytes` and `sha256`, ordered `original_trial_numbers`, explicit
  `excluded_unlocked_trial_numbers`, `upstream_temporal_support_ms`, and
  `provenance` containing the six original pipeline SHA-256 bindings documented
  in [SCHEMA.md](../train-only-decoding-v1/SCHEMA.md).

The locked trial sequence must exactly match the complete raw eligible sequence.
Both neural and kinematic trial numbers and lock flags must agree in original
order. Every unlocked exclusion must be explicitly declared; discordant lock
masks, undisclosed drops or reordered pairings refuse the whole operation.
Native LR 1/2 maps to left/right. Exact joint order, source configuration and
source asset filename in `M.config.datasetInfo` are checked. Source-declared
angle/velocity units are attached by field name and validated by the existing
pipeline; no native unit field is read or independently calibrated here.
Angles and velocities are separate requests, never one 48-channel outcome.

The locked ROI count and complete lag vector must match the raw inspection's
`M.ROILags` count and vector; this count is not independently measured from
`R.events`. All supplied locked columns are retained for downstream training-only
selection. The names `session:source-column-N` identify supplied session-local
column positions. Matching lag metadata cannot prove original neural column
order, especially when lags repeat. Original column lineage, anatomical cell
identity and cross-session correspondence remain external requirements.
No outcome-dependent ZETA cell screening is introduced by this adapter.

The recovered RADICaL source grid ends at +800 ms while the existing normalized
contract requires upstream support through +900 ms. This component **refuses
RADICaL normalization** until that source/policy mismatch is reviewed; it never
invents an extra 100 ms or changes the current contract. Raw eligibility
inspection remains useful for either eventual feature route.

## Commands and downstream path

With an independently pinned manifest and provisioned original inputs:

```sh
python3 -B admission.py inspect-raw \
  --manifest raw-manifest.json --expected-manifest-sha256 "$MANIFEST_SHA256" \
  --input-root /absolute/operator/input --output /absolute/operator/raw-inspection.json \
  --max-manifest-bytes 1000000 --max-output-bytes 10000000

python3 -B admission.py normalize-locked \
  --manifest locked-manifest.json --expected-manifest-sha256 "$MANIFEST_SHA256" \
  --input-root /absolute/operator/input --output /absolute/operator/normalized-request.json \
  --max-manifest-bytes 1000000 --max-output-bytes 100000000
```

The example byte limits are explicit caller-selected examples, not measurements
of the authentic full cohort. Dependencies are Python 3.11+, NumPy and h5py.
No SciPy/MATLAB installation is needed to read an already-created supported
export. Output is written privately, only published after complete serialization,
and never overwrites an existing path. A refused operation exits nonzero.
No bytes are sent to a provider or network by these commands.

`normalized-request.json` directly supplies `dataset`, `protocol`, and `context`
to the unchanged predecessor `pipeline.py` scorer/reference controls and
`participant-delivery-v1/delivery.py`. Its protocol/context digests are returned.
The normalized pipeline itself revalidates the complete cohort, complete trial
splits, all 51 samples and all 24 channels. Normalization does not run reference
fits, create candidate predictions, establish no-tools execution, or score an AI.

## Evidence and outstanding work

Generated HDF5 controls exercise actual reading, field/axis handling, complete
cohort normalization, identities, malformed/unsupported inputs and CLI behavior.
They are software tests. The separate primary-source inspection read one 520-byte
header and small metadata/source bodies; it did not inspect authentic scientific
arrays or trial values.

Still outstanding: provisioned full originals and author-created locked exports;
authentic raw eligibility and preprocessing/clock admission; exact provenance
bodies and original-trial correspondence; measured full-resource costs; competent
reference runs; protected participant execution; and scientific qualification.
The source-readiness count and the scientific task definitions are unchanged.
