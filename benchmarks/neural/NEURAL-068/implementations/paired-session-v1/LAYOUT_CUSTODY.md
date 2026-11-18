# Protected layout export

`export_layout.py` connects the retained original/prepared metadata to the
already selected `scorer.make_layout`. It closes a concrete source-construction
gap: the legacy pool binds source/container hashes and support counts but does
not export the complete evaluation-mask bitmap and its current layout.

This component compares every clock/trial row and evaluation-mask bit before
producing a private layout. It preserves the 27-run metadata roster, selects
the exact 14 later-calibration originals, and retains all 84 run/arm/budget
contexts, seven velocity labels and complete third-segment query support. It
does not replace the original preparation, split policy, importer, scorer or
historical execution route.

## Trusted future operation

The trusted API is `export_layout(selection, output_directory)`. Its CLI is:

```sh
python3 -I -B export_layout.py \
  --selection /operator/selection.json \
  --selection-bytes SELECTED_SIZE --selection-sha256 SELECTED_SHA256 \
  --output /operator/new-private-export
```

This is an interface recipe, not an admitted authentic-data operation. Freeze
the selection outside participant control. Its exact keys are:

- `schema`: `neural068-protected-layout-export-selection-v1`.
- `pool`, `preparation`, `external_metadata_receipt`, `exporter`: absolute
  `{path, bytes, sha256}` descriptors. The exporter descriptor identifies the
  selected `export_layout.py` at its actual execution path.
- `original_root`: original files named `<asset_id>.nwb`.
- `prepared_root`: the existing `<run>/input.npz` and `<run>/target.npz` tree.
- `read_ceiling_bytes`, `output_ceiling_bytes`: explicit positive budgets.

The CLI authenticates the selection file before parsing it. The trusted API
assumes its caller already froze the selection. The receipt records its full
selection and the canonical selection digest; that canonical digest can differ
from the CLI's raw selection-file digest when formatting differs.

Use the exact retained pool/shared-preparation generation and the separately
selected G5 source-custody receipt recorded in `layout_custody_sources.json`.
G5 reconciled a content-pinned 40-asset snapshot. A published DANDI release is
not a prerequisite for that route, and the mutable draft must not silently
become a new frozen release. The 13 minival files share training run IDs but
have distinct payloads; none substitutes for a selected later-calibration
original. Dataset terms, current body identity and acquisition authority remain
separate. This component performs no network operation.

## What is read and bound

Each original or prepared container is opened through a regular-file
descriptor, rejecting symlink paths and files with multiple hard links. Exact size/SHA256 and stable file identity are checked before
and after metadata decoding. Python file-object reads reserve their budget
before I/O; the receipt reports reservations, including short-read/failure
reservations, rather than claiming physical OS I/O measurement.

The NWB reader lazily requires an existing `h5py` installation. It reads only
the declared source clock/header fields, `TrialNum` and genuinely Boolean
`eval_mask`. The header checks preserve the retained legacy zero-origin clock:
stored rate `0.02` is the declared interval, never converted to `1/rate`.
Source channel descriptions and arbitrary-unit metadata must match the
retained preparer. Soft links, external links, external-storage and virtual datasets are refused.
Kinematic/velocity shapes and attributes are inspected; their value arrays and
spike values are not decoded.

The standard-library NPZ reader opens only `time_s.npy`, `trial.npy` or
`eval_mask.npy`, with exact primitive little-endian float64/int64/uint8 shapes.
It rejects duplicate/unexpected members and object metadata arrays without
loading pickle. It does not open `velocity.npy` or `spikes.npy`; their contents
are not thereby validated. Prepared masks must contain only 0/1 and equal the
original Boolean bitmap at every row. Equal counts alone cannot pass. Clock
and trial vectors must also agree exactly.

The unchanged, byte-pinned scorer creates the layout. The exporter then checks
the legacy segments, complete suffix and each prefix's declared support. It
performs no fitting, normalization, metric calculation or target substitution.
Whole-file hashing **does read protected container bytes**, including containers
that hold velocity. No claim that target containers remained unopened is made.

## Private outputs and limits

The output directory must be new; it is created with mode0700. It contains
`layout.json`, complete `source_metadata.json`, and `EXPORT_CUSTODY.json`.
These are trusted-operator artifacts, not participant inputs or distributable
data. The custody receipt binds their byte hashes, original/prepared inputs,
selected code and metadata descriptors, row counts and read reservations.

The receipt is written to a pending file, flushed, then exclusively published
last. Receipt-write or directory-fsync failure removes this invocation's
receipt inode; earlier partial artifacts remain unqualified. This is not an
OS isolation or adversarial same-user race guarantee. Source descriptors and
self-consistent receipts do not establish trusted execution by themselves.

The exporter can establish observed mask/clock/trial equivalence and file
custody when later run on admitted inputs. It cannot establish the original
dataset's scientific identity, shared-preparer execution, undocumented
transforms, or equality of undecoded velocity targets. The existing
`target_loader` still needs separate authenticated target lineage. The
unchanged competent comparator, exposure/isolation, full runtime feasibility,
scientific qualification and native neural understanding remain open.
Retrospective legacy grading already preceded its observation receipt; this
export does not restore a first-time hidden evaluation. All corresponding
qualification flags remain false.

## Maintained controls and integration

From the composed repository root:

```sh
python3 -I -B benchmarks/neural/NEURAL-068/implementations/paired-session-v1/test_export_layout.py
```

Use Python3.11 with installed `h5py` and NumPy. The admitted local run used
h5py3.16.0 and NumPy2.4.6; no installation was performed. Do not add `-S` when
these dependencies are provided through the selected global site-packages.
Tests need the exact sibling exporter and existing scorer, with no private
dependency paths. Standard `tempfile` suffices; local admission set `TMPDIR`
to a fresh owned evidence directory. Keep thread limits at1 and ensure enough
owned temporary space for the declared cumulative 225280-byte fixture ceiling.

Eight new methods passed once. One physical generated HDF5/input/target-NPZ
fixture exercises actual file capture and production readers. The complete
14-run check uses real HDF5/NPZ decoding through an in-memory file facade,
followed by one real private export. It is not full14 production-filesystem
qualification or authentic-data validation. Negative export controls prohibit
publication even if an implementation guard regresses; tiny publication-failure
controls separately account for partial and deleted receipt bytes.

The sole integrator must add these four new task-local files, retain the exact
existing scorer, explicitly enroll this eight-method command and reconcile the
actual future target. The accepted private importer/operator require their own
selection; this package does not adopt them or change current source authority.
No prior passing suite or 84-context campaign was rerun, and no new finished
benchmark or empirical result is claimed.
