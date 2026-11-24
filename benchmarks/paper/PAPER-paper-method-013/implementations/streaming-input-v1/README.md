# Streaming movie inputs and released full-model outputs

This component turns an explicitly mapped local movie into the released model's
`[1,400,64,64,1]` input, one tile at a time. It also separates the released
segmentation fields and trace outputs correctly. It does not run a model, derive
a binary segmentation threshold, merge tiles, or establish reproduction of the
paper. The original ten-recording task and its scorer are unchanged.

## Complete input support without a full tile cache

`model_input(dataset, mapping, tile_index)` reads one source slab from a
time × row × column uint16 dataset. The caller supplies the raw frame start and
512-to-488 crop origin explicitly; neither is inferred from filenames or a
center-crop convention. A declaration is not independent authentication of the
original paper transformation.

The implementation follows the pinned MATLAB tailor's ordering and arithmetic:
row advances first, then column, then time; spatial stride is 53 pixels;
float32 conversion and zero padding precede per-tile min/max normalization.
The temporal tile size is explicitly set to the paper's 400 frames rather than
the generic tailor's 100-frame default. A 488×488×5000 interval produces
9×9×13 = 1,053 tiles. Only the final temporal block needs padding: 200 observed
frames and 200 zero frames. Normalizing the observed part before padding would
change that block and is not done here. A constant padded tile is refused because
the source normalization divides by zero; no substitute input is invented.

`iter_model_inputs(dataset, mapping)` streams all 1,053 tiles.
`iter_panel_inputs(open_recording, mappings)` first requires declarations for all
ten original recording IDs, then streams their 10,530 tiles in the fixed source
roster order, with one source context open at a time. The callback is an
operator-owned context manager yielding the selected dataset. Neither iterator
retains the tile bank. A consumer must finish collection and independently verify
coverage; beginning an iterator is not proof of a complete run.

## Local HDF command

The command exports one tile and a JSON receipt inside an uncompressed NPZ:

```sh
python streaming.py \
  --movie-hdf5 /external/movies/ophys_experiment_501271265.h5 \
  --mapping /external/reviewed-mappings/501271265.json \
  --tile-index 0 \
  --output /external/inputs/501271265.tile-0000.npz
```

NumPy and h5py must already be installed in the execution environment. The input
must have a local hard-linked `data` dataset with the official uint16 shape and
unfiltered `(1,512,512)` HDF chunks. External/virtual storage and links are
refused. Inputs are opened as ordinary files and checked for file-state changes;
the command neither authenticates whole-file content nor claims an untouched
holdout. Existing outputs are refused. A failed output write removes its own
incomplete file.

The mapping format is below. The `null` values intentionally make this template
non-executable: supply independently supported values, not guessed defaults.

```json
{
  "schema": "deepcaimx-explicit-movie-mapping/v1",
  "task_id": "PAPER-paper-method-013",
  "recording_id": "501271265",
  "source_shape": [null, 512, 512],
  "frame_start_zero_based": null,
  "crop_row_start": null,
  "crop_column_start": null,
  "mapping_evidence": "Location and identity of the reviewed transformation evidence"
}
```

The actual shape is checked against `source_shape`. Every crop must contain the
complete 488×488 field and the declared interval must contain all 5,000 frames.
The mapping file is bounded to 64 KiB, strictly parsed, and its SHA256 is retained
with the exact declaration. The receipt explicitly reports source-content and
mapping authentication as unestablished by this component.

One model input is 6,553,600 bytes. The logical observed slab is at most
3,276,800 uint16 bytes, but HDF reads can touch 400 complete 512×512 source chunks
(209,715,200 bytes), plus chunk-index metadata. Repeated overlapping tiles can
reread chunks. This source component is not a disk-transfer, CPU, or study-budget
supervisor; authentic preparation requires a separately admitted operator budget.
No movies or full tile bank were acquired or generated during construction.

## Released output decoding

`decode_outputs(segmentation, traces, tile_index)` validates float32 arrays with
the released shapes `[1,416,64,64,1]` and `[1,396,8]`. It retains:

- raw footprint fields from segmentation slices 400–407;
- morphological footprint fields from slices 408–415;
- unmodified model traces and separately named demo display-normalized traces;
- trace frame indices and a mask marking temporal padding.

The first 400 segmentation slices are attention fields. Morphological fields are
continuous, not authenticated binary ROI masks; the decoder applies no threshold.
The demo's trace normalization uses the maximum over all eight channels jointly,
then zeros display traces for all-zero morphological fields. Raw traces remain
unchanged. Nonfinite or negative outputs are refused before that operation.

The released temporal output covers tile offsets 2 through 397, with 396 samples.
For the last temporal block only offsets 2 through 199 lie inside the original
5,000-frame interval. No boundary samples are interpolated, filled, or relabeled.
The 50 missing original frame positions across the 13 blocks remain a temporal
assembly limitation, not valid complete-movie trace coverage.

## Evidence and remaining work

[PROVENANCE.json](PROVENANCE.json) records the inspected source identities.
The three original notebook bodies are now authenticated; their literal,
output-free code exports and static syntax findings are described in
[notebook source authentication](NOTEBOOK_SOURCES.md). This closes the earlier
notebook-body provenance gap while preserving its failed retrieval history.
No notebook cell, model or training recipe was executed or repaired.
The numeric controls use generated data and lightweight mock readers/models.
They establish code behavior, not native TensorFlow execution or paper results.

Original raw frame/crop mapping, paper-equivalent N=15/P=9 weights, historical
cross-tile matching/merge details, binarization and full trace/runtime companions
remain unresolved. The released full artifact has eight output channels and
396-sample traces; successful use of this adapter would not resolve its
equivalence to the paper. Existing source-panel scoring remains separate.

```sh
python -m unittest discover -s tests -p 'test_streaming.py' -v
```
