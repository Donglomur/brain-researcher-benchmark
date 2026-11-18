# SUNS2 nine-video scoring contract

This component scores the original TUnCaT spatial-instance segmentation endpoint on the exact nine videos in `suns2_benchmark.constants.VIDEO_IDS`. It compares candidate masks with the same author's saved masks, using the same ground-truth instances. It constructs an evaluable submission interface; it does not show that a candidate method has run, reproduced the paper, or improved a result.

## Trusted interface and coordinate convention

`score_panel(gt_by_id, author_by_id, candidate_by_id)` accepts three plain dictionaries with exactly those nine IDs. Values are plain NumPy arrays of finite binary values, shaped **50 × 50 × N in original MAT order `[column, row, neuron]`**. Movie coordinates `[time, row, column]` map to `Masks[column, row, neuron]`: movie row 7, column 13 maps to MAT `[13, 7, n]`. The two spatial lengths happen to agree, so shape checking cannot detect a transposition. The scorer never transposes spatial axes or reorders the original neuron axis.

Arrays are copied to Boolean values before scoring. Ground truth must be nonempty; predictions may have N = 0. A zero-area individual ROI is refused. N ≤ 512 and the zero-area restriction are explicit interface choices, not claims about original biological limits. Raw prediction duplicates remain present for original scoring. Array subclasses, object/complex arrays, fractional/nonfinite values, missing/extra videos, and malformed dimensions are refused with `ScoringError`.

## Original source metric

The primary recipe retains the source helper's Jaccard distances, threshold `distance > 0.5 → Inf`, and literal MATLAB Hungarian control flow. It retains every ground-truth and prediction instance and their order. The Python translation is not silently replaced with SciPy's finite-cost-2 assignment or a maximum-cardinality matcher. Generated counterexamples show that these algorithms can differ, and that permutation alone can change the source result.

For a nonempty prediction set with matches m, ground-truth count G, and prediction count P, recall is m/G and precision is m/P. The source floating expression `2*recall*precision/(recall+precision)` is reported. For m > 0 its exact count-derived value is 2m/(G+P).

The literal standalone helper explicitly returns recall, precision, and F1 = 0 when a prediction set is empty. This is preserved; the full original caller's empty-output path has not been tested. For nonempty predictions with zero matches, the literal F1 expression is undefined. The result records F1 as JSON `null` with status `literal_helper_nonempty_zero_match_NaN`; recall and precision remain zero. No video is dropped and the audit's zero is never substituted into the original metric. An undefined original video makes its complete-panel original mean and original improvement delta undefined.

Original arithmetic qualification is distinct from native MATLAB parity and from reproducing prediction generation. A separately admitted integrated saved-author control has now passed independent review: candidate-format intake and trusted grading matched all 27 released per-video original recall/precision/F1 values. Replaying the same author masks produced zero original and audit deltas on every one of the nine videos, with unchanged raw order and geometry. This qualifies the integrated intake and saved-output scoring control, not a method reproduction, training run, eligible AI trial, improvement, or finished benchmark. Native MATLAB execution parity remains unestablished.

The control measured the authentic author reference under both the original metric and the separately declared audit. Their exact equal-video means are both `741757236989669/1003523472340200`, displayed as `0.7391528523592015`; the stored release mean is `0.7391528523592014`. Three per-video original/audit floating F1 values differ in their last digit while retaining equal match counts and exact fractions. These arithmetic differences are not improvements, and agreement on these author outputs does not make the two metrics equivalent for arbitrary predictions. The accepted operator records are `CONTROL_CLOSURE.json` (SHA256 `6733aa2c` prefix) and `AUTHOR_CONTROL_SAVED_RESULT_REVIEW.json` (SHA256 `bab23412` prefix).

## Separately declared order-invariant audit

Audit name: `unique-prediction-geometry-max-cardinality-iou-half/v1`.

The audit removes exact duplicate binary prediction geometries from **both** candidate and author predictions and preserves **all ground-truth instances**, including any repeated ground-truth geometry. It uses a maximum-cardinality one-to-one matching on the IoU ≥ 0.5 graph. Eligibility is computed exactly with integer counts: `2 * intersection >= union`. Every admitted ROI has positive area, so union is positive. Audit F1 is 2m/(G + P_unique). Empty predictions and zero matches yield audit F1 = 0.

This symmetric deduplication and zero totalization are conservative declared extensions. They do not change the original score and do not claim equivalence to the original MATLAB metric. Audit order is canonical, and its match count is independent of neuron order. Matching correctness has generated exhaustive controls against an independent enumeration for all 512 Boolean 3 × 3 graphs, alongside rectangular/empty graphs and permutation controls.

Only exactly identical prediction geometries are deduplicated. Near-duplicate geometries remain distinct and can raise both matching metrics without establishing biological instance separation; this is one reason the outcome remains a descriptive panel result.

## Descriptive improvement rule

The complete same-nine-video outcome is true only when all four conditions hold:

1. Every author and candidate original per-video score is defined.
2. The candidate's equal-video original mean is strictly greater than the author's mean.
3. At least one video's **unordered set of exact prediction geometries** changes. Permutation-only and duplicate-only changes fail this condition.
4. The candidate's equal-video declared audit mean is strictly greater than the author's audit mean.

Both positive-delta gates use exact `Fraction` values derived from integer match/instance counts, then average over all nine videos. There is no floating epsilon, rounded-paper threshold, omitted-video shortcut, or positive floating reduction artifact that can confer improvement. Reports still show the ordinary source floating means, population SDs, per-video deltas, and the exact deltas. Exact rational numerators and denominators are decimal strings to prevent downstream JSON number precision loss.

A positive unique-geometry audit gain does not attribute the entire original-score delta solely to geometry changes. Source ordering or duplicate effects may coexist with geometry changes, including effects on other videos in the panel. The separate reported metrics support the stated descriptive outcome, not a causal decomposition of the original gain.

This is a descriptive increase on a fixed exposed panel. A positive result does not establish population generalization, meaningful biological or clinical benefit, current global SOTA, authenticated execution, or benchmark readiness. The result magnitude remains visible; no ungrounded effect-size margin is invented. The authentic author-reference audit is now qualified by the separate admitted control and review described above, not by generated construction checks. Generic scoring API flags remain conservative: that external qualification does not authenticate arbitrary candidate generation or execution isolation.

## Candidate files

The submission directory contains exactly `submission.json` and a `masks` directory with exactly one `<video_id>.mat` for each expected ID. `submission.json` has exactly these fields:

```json
{
  "schema": "suns2-candidate-submission/v1",
  "condition": "paper_data",
  "procedure_digest": "<64 lower-case hexadecimal SHA256 characters>",
  "cases": [
    {
      "video_id": "<one expected video ID>",
      "path": "masks/<same video ID>.mat",
      "sha256": "<64 lower-case hexadecimal SHA256 characters>",
      "bytes": 256
    }
  ]
}
```

The illustrative array must contain exactly nine case records. Each `bytes` value must equal the actual MAT file length (at least 128 bytes), replacing the illustrative 256. The condition is exactly `paper_data` or `paper_data_official_code`. The trusted caller supplies the expected condition and a procedure digest frozen before hidden-fold scoring. Matching this declared digest authenticates the declaration, not the assertion that the procedure produced the files.

`load_candidate_submission(directory, expected_condition, expected_procedure_digest)` returns `(masks_by_video_id, verified_metadata)`. It validates the full ID/file census before reading any mask body, checks exact source size and SHA256, uses componentwise no-follow POSIX directory-relative reads, refuses aliases/symlinks/hardlinks/nonregular entries, and checks identities before and after intake. Unexpected entries, paths, fields, duplicate JSON keys, and nonfinite JSON constants are refused. Public refusal type: `CandidateSubmissionError`.

Each MAT contains exactly one dense, real numeric or logical MAT5 variable named `Masks`, with original axes preserved. It has no subsystem references or additional variables. HDF5/v7.3, cells, structs, sparse matrices, objects, complex arrays, unsupported flags, trailing records, and invalid/trailing compressed streams are refused. A structural/type/dimension/expansion preflight runs before existing SciPy readers. Logical storage is checked as canonical uint8 raw 0/1 before any Boolean conversion. Loaded binary masks become read-only Boolean arrays, retaining duplicates and neuron order. No pickle, participant Python, external references, or model code is executed.

Limits: manifest 65,536 bytes; each MAT source and expanded stream 16,777,216 bytes; exactly 50 × 50 × N with 0 ≤ N ≤ 512, at most 1,280,000 mask elements per file. Files are processed one at a time; nine canonical Boolean outputs are retained. These are resource/interface limits. Scoring has a 55-second cooperative internal deadline; the caller must additionally own the outer process deadline, memory/thread policy, and private reference isolation.

`load_trusted_mask(path, expected_variable, expected_sha256, expected_bytes)` applies the same bounded reader to an independently authorized operator reference and returns `(readonly_bool_array, metadata)`. Only `Masks` and `FinalMasks` are allowed. The trusted caller must select and pin the reference specification outside the participant submission root. Candidate manifest fields never select reference files. The public exception remains `CandidateSubmissionError`.

## Result schema and outcome separation

The scorer returns JSON-safe `suns2-nine-video-panel-score/v1`, with status `scored_complete_panel` or `scored_with_undefined_original`. It includes all nine `cases`, `original_summary`, `declared_audit_summary`, `descriptive_outcome`, `qualification`, and `limits`. `descriptive_outcome` contains the Boolean `same_panel_geometry_improvement`, each criterion, `original_mean_delta_exact`, `audit_mean_delta_exact`, and geometry-changed IDs. Undefined original results are visible and never considered a successful improvement.

Replaying saved author outputs can qualify scoring arithmetic. It cannot qualify recreation of the method. Candidate recreation and improvement also require the external execution/procedure/fold-isolation contract. Paper+data and paper+data+official-code are separate assistance conditions; neither condition silently grants released weights or author outputs.

## Source identities

The literal matcher was retained unchanged from the reviewed numeric component; its SHA256 is `58c028e7621f17c6284872315a6b8639ff2b4b0aa571186195499745e6ef16d6`.

| Original retained v1.1 source | SHA256 |
| --- | --- |
| `ANE/eval_func/Hungarian.m` | `1d83ec20881144f6ad3839ccc0ea00bcd4a805eae3d67c0a18713e37fa516241` |
| `ANE/eval_func/GetPerformance_Jaccard_2.m` | `70ee04a24d4d04648ce3e84e84826c385212c07cb19ed5603a028d5239c14ca2` |
| `ANE/eval_func/JaccardDist_2.m` | `8d7afd9dbaff6aac3194d8788cffdd8422ca89a9a0d43f4fac166520f4f07a86` |

These source bindings and generated controls justify the declared translation. They do not convert it into verified native MATLAB execution or an unqualified original-method reproduction.
