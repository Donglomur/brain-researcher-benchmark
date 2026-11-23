# Original manual ROI conversion and segmentation scoring

`source_panel.py` provides two operator commands for the original ten-video
segmentation endpoint. The converter authenticates all ten MATLAB files against
the Git blob identities in author revision
`305a4827929b2c6e82e44c5c69b2ea9d410e20a4`, recorded in `roi_sources.json`.
The existing local author archive members match those exact tree identities;
their byte lengths and SHA256 hashes are also recorded. Filenames alone do not
establish this identity.

The code loads the original `seg` variable with SciPy and moves its ROI axis from
`row,column,ROI` to `ROI,row,column`. It preserves every ROI, overlapping mask
pixel and row/column orientation. It performs no crop, transpose of spatial axes,
resize, threshold selection, connected-component splitting or deduplication.
Every nonempty binary ROI remains on the complete 488×488 field. This operation
converts the author masks; it does not authenticate their mapping to an Allen
movie or resolve the meaning of the filename frame labels 18501–23500.

Run from this directory with NumPy and SciPy available. Inputs, outputs and
manifests in these examples are **external operator-owned paths**, never public
repository content or candidate inputs:

```sh
python source_panel.py convert-rois \
  --source-root /external/author-source \
  --output-dir /external/protected/deepcaimx-reference
python source_panel.py score-segmentation \
  --source-root /external/author-source \
  --reference /external/protected/deepcaimx-reference/reference.json \
  --prediction /external/predictions/prediction.json \
  --output /external/operator-results/segmentation.json
```

The source root contains `Manually Labelled ROIs/ABO/*.mat`. The converter checks
all ten file identities before creating the output directory and refuses an
existing directory. It writes boolean NPY masks one recording at a time and
`reference.json` last. A failed conversion may leave an incomplete directory;
absence of `reference.json` means conversion did not complete. The scorer checks
the original MAT bytes again and compares their direct conversion to the cached
masks. Changing the cache and updating its self-declared hash therefore does not
replace the authenticated reference.

The scorer captures each manifest once, parses that snapshot and reports its
SHA256. Each mask file is likewise captured once, authenticated and decoded
from the captured NPY bytes. A pathname replacement after capture, or later
in-place mutation, cannot change the arrays being scored. These checks bind
content; they do not establish process isolation, provenance of predictions,
or historical lack of target exposure. Snapshot decoding retains the NPY bytes
alongside its decoded array temporarily, so memory admission must include one
additional complete mask-file payload; masks are no longer memory-mapped.

`prediction.json` describes one method, including an author-baseline-only run.
No fabricated candidate, trace or runtime field is required. Each `mask_file` is
a standalone NPY array with shape `[ROI,488,488]`, binary values and one nonempty
mask per declared ROI. An empty prediction array with shape `[0,488,488]` is a
valid failed detection result. The exact ten recording IDs and depths are
required. Use this structure, with all ten rows:

```json
{
  "schema": "deepcaimx-segmentation-predictions/v1",
  "task_id": "PAPER-paper-method-013",
  "frame_labels_inclusive": [18501, 23500],
  "image_shape": [488, 488],
  "coordinate_system": "zero_based_row_column",
  "policy_id": "deepcaimx-assembled-prospective-v1",
  "method_id": "frozen-method-name",
  "implementation_identity": "code and checkpoint identity",
  "reference_manifest_sha256": "SHA256 of the operator reference manifest",
  "recordings": [
    {
      "recording_id": "501271265",
      "depth_um": 175,
      "mask_file": "501271265.masks.npy",
      "mask_sha256": "SHA256 of that NPY file"
    }
  ]
}
```

The scorer imports the preserved `initial-evaluator-v1/evaluator.py` kernels.
Each manual ROI selects its highest-overlap prediction with strict IoU > 0.5;
exactly 0.5 fails. An equal maximum selects the first declared prediction, a
documented prospective tie rule. Multiple manual ROIs selecting the same
prediction still fail closed because historical conflict handling is unresolved.
Precision, recall and F1 are computed per video. The primary summary is the
arithmetic **mean of ten video F1 values**, not pooled ROI-count F1. Both population
SD (`ddof=0`) and sample SD (`ddof=1`) are labeled because the paper's exact SD
implementation is not authenticated. The published mean 0.847 and SD 0.037 remain
separate reported comparators, never substituted for a rerun.

This command measures segmentation only. Physical movie identity, source frame
mapping, checkpoint equivalence, native tiling/assembly, trace accuracy, runtime,
exposure controls and an improvement decision remain separate requirements. A
score alone cannot establish source-paper reproduction or improvement. The
manual targets are public upstream; local operator separation does not make
them historically unexposed.

Generated controls exercise the actual MAT parser, source-byte authentication,
complete-panel conversion/scoring, strict threshold, overlapping masks, empty
predictions, ambiguous matching, macro-versus-pooled aggregation and changed
reference refusal:

```sh
python -m unittest discover -s tests -p 'test_source_panel.py' -v
python -m unittest discover -s tests -p 'test_snapshot_binding.py' -v
```

The tests patch production source pins with explicitly invented byte identities.
They are software checks and do not score authentic data or a model.

Snapshot controls use small invented arrays to test file replacement, post-load
mutation, mismatched hashes and exact manifest identities. They do not read
authentic manual targets or run a movie-to-mask model.
