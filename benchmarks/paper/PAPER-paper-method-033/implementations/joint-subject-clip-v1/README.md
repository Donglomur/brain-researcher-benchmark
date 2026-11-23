# Joint-subject Table 1 CLIP feature evaluator

This adapter computes the **94.7% CLIP two-way endpoint** in the author-version
Table 1 from already extracted, paired features. It is distinct from the existing
Table 2 adaptation task and does not change its 48 required findings. A result
here is an unqualified feature score, not a reproduction or improvement decision.

For subjects 1, 2, 5 and 7, it requires a separate complete 982-image gallery,
computes each subject's score, and takes their arithmetic mean. It never
concatenates subjects into a 3,928-image identification gallery. Each subject must
declare the same stimulus set; order may differ between subjects, but target,
reconstruction and selection rows must match exactly within each subject.
Identifiers and declared pairing still require independent original-data validation.

## Exact numerical operation

The final features are OpenAI CLIP **ViT-L/14 encode_image** outputs cast with
.float().flatten(1).cpu().numpy(): float32, 768 features per image. The author
computes np.corrcoef(reals, preds), retains its real-by-predicted block, and
compares every predicted column's correlations strictly against its diagonal
match. Ties lose. The subject score is mean(integer success counts)/(982−1).
There is no final cosine conversion, feature L2 normalization, half-tie credit,
or cross-subject distractor pool.

The existing original-panel helper uses this same Pearson comparison, then
returns individual quotients. This adapter preserves the original scalar
mean-before-division order independently, without modifying the Table 2 helper.
Its file reader adapts that helper's bounded NPY-header/frombuffer pattern.

## Upstream work this adapter does not perform

Original reconstruction selection uses eight candidates and the actual target:
the Clipper hidden-token embedding is flattened, normalized, and compared with
each candidate after casting to the target dtype and normalization; the source
cosine helper divides by vector norms again. np.nanargmax chooses the first
maximum. These **selection embeddings are not the final pooled CLIP features**.

Supply eight source-computed finite cosine values and the selected index for each
case. The adapter verifies their first-maximum rule. It does not recompute
PyTorch token arithmetic, authenticate these scores, or prove the features came
from the selected image. Those require an operator extraction record binding the
frozen eight image candidates, chosen image, target, code/runtime and weights.
Nonfinite candidates are refused instead of silently skipped.

The pinned reconstruction returns best_picks but keeps the eight cosine scores
local (printed only in verbose mode). Ordinary saved _img.pt/_rec.pt pairs do not
supply selection_cosines; an operator must capture all eight source-computed
values during reconstruction.

For final metric extraction, the pinned eval.py:
- casts reconstructions to the original-image dtype, clamps to [0,1], and squeezes;
- replaces clip.load's returned preprocessing with Resize(224, BILINEAR) followed
  by Normalize(mean=[0.48145466,0.4578275,0.40821073],
  std=[0.26862954,0.26130258,0.27577711]);
- invokes encode_image and then casts/flattens as above.

No CenterCrop or extra normalization may be silently inserted. The historical
torchvision antialias/default behavior and complete native extraction environment
remain unqualified. This implementation does not load CLIP or diffusion models.
The author's generation protocol uses eight candidates, 20 steps, guidance 5 and
text/image ratio 0.5; a matching feature score alone does not establish that run.

## Input and command

The CLI takes a JSON object with schema mindbridge-table1-clip-features/v1 and
rows for the four subjects. Each row has exactly these fields:

| Field | Required value |
|---|---|
| subject | String "1", "2", "5", or "7" |
| target_ids, reconstruction_ids, selection_ids | Three equal lists of 982 unique stimulus IDs |
| target_features, selected_features | NPY descriptors for float32 arrays shaped (982,768) |
| selection_cosines | Descriptor for a float32/float64 array shaped (982,8) |
| selected_candidate_indices | Descriptor for an integer array shaped (982,) |

Every descriptor is {path, bytes, sha256}, relative to the manifest directory.
Payloads must be plain C-order numerical NPY v1/v2, at most 8 MiB each. Full bytes
are checked before bounded header parsing. Parent directories must be static and
operator-controlled; this is not an adversarial-filesystem isolation service.
The memory option admits conservative numerical workspace, not an enforced RSS cap.

Run from this implementation directory using an existing NumPy environment:

    python -I -B table1_clip.py /private/operator/manifest.json \
      --max-read-bytes 134217728 --max-working-bytes 268435456

The output is JSON on stdout. All scientific qualification, original membership,
native extraction, historical-checkpoint and full48 fields remain false; numerical
scores do not automatically assert reproduction, improvement, or SOTA.

Run the generated checks with:

    OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -I -B test_table1_clip.py

These use generated features only: hand-calculated transpose/tie cases,
a frozen exact author numerical-tail reference, one complete synthetic gallery,
pairing/subject completeness, invalid features, and bounded hashed NPY controls.
They do not exercise a real image encoder.

## Primary evidence and remaining barriers

- [Author paper v1](https://arxiv.org/html/2404.07850v1), Table 1 and supplementary
  implementation details: four-subject 94.7 aggregate. No authenticated
  subject-7-only joint-model score is available as a standalone published anchor.
- [Pinned eval.py](https://github.com/littlepure2333/MindBridge/blob/2a3943ff5b619db6f85f16a5e7ff1331d25def55/src/eval.py),
  SHA256 bde3c051c6f1c3be47c7075986ba2854a16561ff8702b3cbbf412edfcdf5c180.
- [Pinned utils.py](https://github.com/littlepure2333/MindBridge/blob/2a3943ff5b619db6f85f16a5e7ff1331d25def55/src/utils.py),
  SHA256 cdf5f71c5a0c8d30b3dc3deb16e43f0b019f7abbda524bff4825c2c840021a99.
- [Official joint1257 checkpoint candidate](https://huggingface.co/littlepure2333/MindBridge/tree/1f2d5151fd96b42c6381146c21455402971e2432):
  endpoint-appropriate release; exact historical weight/result equivalence is
  unproven. The released inference script still names the separate125 model.

The other three authentic subject galleries, appropriate checkpoint-key loading,
generation dependencies/weights, frozen candidate outputs, verified extraction
and protected comparison remain upstream requirements. The prepared subject7
TEST projection alone cannot reproduce Table1's four-subject average. This
adapter also does not resolve Table2's calibration/checkpoint requirements.

## Compare candidate and reference on the same Table 1 inputs

`table1_compare.py` computes a paired **descriptive** difference between two
complete feature manifests accepted by the evaluator above. It requires all four
subjects and all 982 images per subject in both arms. Within each subject, the
ordered stimulus identities and the actual float32 target-feature values must
match exactly across arms. A matching filename or claimed digest alone does not
establish this equality. Different orders across subjects remain supported, but
reorder a candidate/reference pair together before freezing its manifests.

Each arm independently supplies its eight selection cosines and chosen index.
The comparison applies the same first-maximum validation and the original
predicted-column Pearson calculation in each arm. It averages the four subject
scores separately, then subtracts the reference mean from the candidate mean.
`delta_percentage_points` is 100 times that difference. It does not replace the
original scalar operation with an average of per-image fractions or a pooled
3,928-image gallery.

    python -I -B table1_compare.py /private/reference/manifest.json \
      /private/candidate/manifest.json --max-read-bytes 134217728 \
      --max-working-bytes 268435456

The read limit is shared across both arms' NPY payloads; the output separately
reports bounded manifest bytes and their hashes. The 160-MiB minimum numerical
workspace allowance is conservative admission, not an enforced process RSS cap.
The single-arm evaluator and its source arithmetic remain unchanged.

By default, output contains four subject summaries and the aggregate difference.
`--include-image-counts` additionally emits each subject's ordered stimulus IDs,
reference/candidate success counts and integer count differences. These are
operator-private evaluation outputs; keep authentic per-image results outside
public source releases. Every count uses that subject's full 981 distractors.

A positive difference is a higher feature score for these supplied panels. It is
not an automatic paper-improvement or SOTA decision. The subjects share the same
982 images, and each image's score depends on its distractor gallery: treating
3,928 subject-image rows as independent repetitions would give misleading
uncertainty. This component supplies no confidence interval, superiority rule or
accepted reproduction tolerance. Original membership, native extraction,
selected-image binding, checkpoint provenance, matched information/compute,
submission freezes and protected evaluation still need independent qualification.
Table 1's other metrics and the separate Table 2 full-48 comparison remain outside
this CLIP component.

Run the added generated checks with an existing NumPy environment:

    OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -I -B test_table1_compare.py

The checks exercise the complete four-subject gallery with analytically counted
strict-tie cases and unequal subject changes, mismatch refusals, each arm's
selection, optional private vectors, manifest identity and the shared read limit.
Generated control scores establish software behavior only.
