# Original-panel RSA comparison

`compare.py` adds the missing descriptive **candidate-versus-all-original-models**
comparison on the original BOLDMoments panel. The preserved shared scorer measures
reproduction error, while its prospective improvement evaluator requires new
participants/stimuli and a fixed-layer macro-average. Neither supplies this
original-panel comparison. This component leaves both predecessors unchanged.

The numerical input is already-computed signed per-participant Spearman RSA, not
brain arrays, videos, model weights or answers. It preserves the paper's rule:
average each layer over the ten participants, then select the first maximum
signed layer mean separately for each ROI. It does not average participant-wise
maxima, choose the largest absolute correlation, pool RDM entries as independent
observations, or average away the 17-ROI profile. Candidate architectures and
layer names may differ from the author's models.

The result contains 1,683 candidate/reference differences (99 conditions × 17
ROIs), a strongest-reference diagnostic per ROI, and all 5,695 reference
condition/ROI summaries, including every layer's ten participant values. The
335 conditions comprise the main 99 PCA models; 92 SRP and 92 unreduced controls;
51 training-video models; and the additional pretraining-only VideoMAE control.
The PCA main rows also supply the PCA arm of Figure 16. Test and training noise
ceilings remain separate profiles. There is no invented scalar across ROIs.

An undefined value (`null`) in any layer prevents that model/ROI selection. An
undefined main-reference result prevents selecting a strongest model from the
remaining subset. Other descriptive comparisons remain explicitly available;
the complete undefined inputs stay in the result. NaN, infinity, booleans and
out-of-range correlations are errors. Missing or reordered participants,
stimuli, models, layers or ROIs are errors. Omitting a companion condition is an
error. This is a validation boundary for supplied declarations, not independent
proof of complete feature extraction or authentic scientific observations.

## Inputs and invocation

Run with Python's standard library; no packages are installed or imported:

```text
python3 -I -B compare.py --protocol PROTOCOL.json --reference reference.json \
  --candidate candidate.json --output comparison.json
```

Output is exclusively created; an existing file is not overwritten. Keep real
input/output artifacts outside Git. The command's three input JSON files have a
64 MiB per-file limit. No data/model workload is authorized by this command.

`--protocol` is the existing pinned public metadata file in the repository:

```text
benchmarks/shared/four-programmes/_four_programmes_source_v1/originals/authoring/delivery-20261105/common/remaining-builds-wave38/hundred-models-complete-design/implementation-v1/successor-v2/source-donors/metadata/PROTOCOL.json
```

Its SHA-256 is
`59a43129bda8f20c4de74f1022609d09c3d7b8f1db275cc6b7df05057c7e9d1c`.
The tool derives source model membership/order, ROI order, ten subject IDs and
102 stimulus IDs from those exact bytes. This metadata explicitly says the
actual-video/derivative joins are pending; this component does not resolve them.

Both documents require `test_support`, containing exactly `subjects`, `stimuli`,
`repetitions`, `brain_rdms_sha256` and `video_inputs_sha256`. The first three
must match the pinned protocol; all five must match between candidate/reference.
The digests bind declared shared observation bundles. Both also require
`run_sha256`, identifying the full external run record, whose required scientific
contents include the input/preprocessing, exposure, checkpoint and reduction
provenance. Candidate additionally requires the external `freeze_sha256` record.
The component checks digest syntax/equality, **not authenticity or actual prior
freezing**. Its qualification fields always state those limits.

Reference fields:

- `schema`: `hundred_models_original_reference_v1`.
- `origin`: `published_author_outputs` or `reproduced_author_outputs` (kept distinct).
- `train_support`: the same five support fields, with independently supplied
  1,000 unique training stimulus IDs, three repetitions and the original ten
  participants. Training IDs must be disjoint from the 102 test IDs. They are
  never inferred from filename conventions.
- `noise_ceilings`: `test` and `train` lists, each containing all 17 ordered
  `{roi, lower, upper}` rows. Values are signed correlations or explicit nulls.
- `layer_catalog`: mapping each of the 335 condition IDs to its complete ordered
  evaluation-layer list. All conditions of one source model use the same list.
- `rsa`: all 335 × 17 ordered `{condition, roi, layers, values}` rows. `values`
  has one row per layer, with ten values in source participant order.

These RSA rows are the existing shared runtime's
`hundred_models_submission_v2.rsa` output shape. The native producer's separate
loading/graph catalog establishes the layer declaration; the runtime's panel
input/observation records supply support metadata. This comparator does not
import or execute that native runtime and does not manufacture those records.
The full retained reference record hash binds the supplied layer catalog and
companion values. It must be independently checked against authentic author
outputs before these differences can be interpreted empirically.

Candidate fields:

- `schema`: `hundred_models_original_candidate_v1`.
- `layers`: the candidate's complete, frozen ordered evaluation-layer list.
- `rsa`: 17 ordered `{roi, layers, values}` rows, with the same layer list for
  each ROI and ten values per layer. An ROI-specific layer subset is refused.

Input RSA must already use 1−Pearson model/brain dissimilarities and upper-triangle
Spearman alignment, with the original repetition averaging and preprocessing.
This module cannot infer those operations from a correlation value. Source graph,
checkpoint, historical reduction, native environment and observation provenance
remain external qualification requirements. Public-test exposure is unchanged.

## Qualification and verification

The output is descriptive. Participant differences are computed after selecting
layers using the whole cohort, so they are not independently selected
confirmatory observations. No confidence interval, multiplicity correction,
minimum effect, across-ROI win, unseen-test claim or SOTA claim is invented.
These still require the original contract's frozen inference/access policy and
authentic full-reference recovery. The task remains `source_unresolved`.

`test_compare.py` uses generated correlations only. It checks max-after-mean with
a participant-wise-max counterexample, signed/tied selection, undefined coverage,
the complete 99/92/51 plus auxiliary condition support, strongest-reference
comparison, companion retention, identity mismatch, and strict JSON/source pins.
Run it only through the shared two-slot test pool during this parallel wave.
See `HANDOFF.md` for actual execution evidence and costs.

Source definitions: the [paper](https://proceedings.iclr.cc/paper_files/paper/2025/file/6ceb6c2150bbf46fd75528a6cd6be793-Paper-Conference.pdf),
the [author driver at pinned revision 5e802ae](https://github.com/SergeantChris/hundred_models_brains/blob/5e802ae5e368a1a30940e6b175e47704a3061419/scripts/calc_alignment.py),
and the current task's `improvement.v1.json`. No network acquisition was needed.
