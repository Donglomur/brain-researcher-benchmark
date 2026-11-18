# SUNS2 TUnCaT: recreate and improve the original paper endpoint

This private construction package defines one paper task on all nine original TUnCaT videos from [the SUNS2-ANE paper in Communications Biology (2024)](https://doi.org/10.1038/s42003-024-06668-7). It asks a candidate to generate neuron-instance masks from the permitted original data, first as a recreation attempt and then with an improved method. The comparison uses the paper's Figure 5c spatial segmentation endpoint: an equal-video mean of nine F1 scores at IoU ≥ 0.5. Neurons and frames are not independent benchmark cases.

The full-precision saved author reference is **0.7391528523592014** mean F1. Its reconstructed value is 0.7391528523592015, with population SD 0.043528657992317046; the mean difference is floating reduction precision. All 27 released recall/precision/F1 values were reproduced from the author's saved masks. This qualifies the reference arithmetic, not a fresh training reproduction. The displayed paper value 0.7392 is rounded.

The integrated saved-author submission control has now passed on all nine videos: all 27 original metrics match, and every replay delta is zero. The complete current-v3 input archive is also authenticated and all nine original movies have passed a full bounded readability scan. Independent saved-result review accepted the complete current input bank and its readability scope. No AI candidate has run, no improvement has been achieved, and this is not a newly registered or submission-ready benchmark. Paper delivery, official-code material completion and a qualified protected execution boundary remain separate requirements.

## Candidate task and assistance

Each recreation or improvement attempt freezes one procedure before any held-fold feedback. Execute it in nine fresh fold states, with the original held video changing each time. Every fold permits all nine movie files (eight training videos and the held prediction input) and exactly eight training-mask files. The held label stays with the evaluator. State, outputs and labels cannot carry from another fold: those other folds contain labels for the current test video.

| Condition | Permitted assistance |
| --- | --- |
| `paper_data` | The paper, original movies and active-fold training masks. |
| `paper_data_official_code` | The same information plus the explicitly selected, pinned official source-code allowlist. |

The selected code condition uses final-paper v1.2.0, commit `128eb4738e026b89a341a6013e7bd7b6dc7c3216`. Complete retained v1.1 subtrees lack the TUnCaT-specific wrappers needed here. The paper-cited v1.1.0 remains historical provenance; it is not interchangeable with v1.2.0 or proof of the exact historical producer. A code manifest must pin the selected version and complete method-supporting allowlist. Released weights are not automatically part of this condition: they need a separately named condition and authenticated fold lineage. Author predictions, evaluator masks, eval.mat and GT-derived output folders are never default participant inputs.

The source training implementation reads held labels in a validation path. Inspected fixed-epoch/final-save logic showed no observed validation-driven selection. Removing that exposure is an explicit protected-execution adaptation until parity is established. The global temporal template is also quarantined until its source role/provenance is qualified. Neither issue is resolved merely by writing a manifest.

## Coordinate contract

Raw movies use `[time, row, col]`. Original MAT masks and the source scorer use **`[col, row, instance]`**. Therefore `movie[t, r, c]` corresponds to `Masks[c, r, n]`. The author source converts its MAT masks with `transpose(2, 1, 0)` to form `[instance, row, col]` arrays. Both image dimensions happen to be 50, so shape checks alone cannot detect an axis swap.

`coordinates.py` provides explicit reversible views. The projector does not transpose protected files. An asymmetric generated control places a movie event at row 7, col 13 and its MAT mask at `[13, 7, 0]`; the untransposed interpretation fails that join.

## What the candidate submits

Each attempt supplies one `submission.json` and exactly nine `masks/<video_id>.mat` files. The manifest binds the assistance condition and frozen procedure digest. Each MAT v5 file has exactly the numeric logical `Masks` variable, shape `[50,50,N]`, using the original axes. The loader validates exact IDs, file census, hashes, sizes and bounded numeric structure; objects, arbitrary code, extra fields, aliases and path escapes are refused. The declared limit N ≤ 512 is an interface/resource bound, not an original-paper biological limit. Empty whole predictions are permitted; zero-area individual masks are rejected at the interface.

The two attempts can be submitted as separate directories. Any recreation score must be labeled separately from how predictions were generated. Replaying the saved author masks only verifies scoring; matching a score alone does not prove method or training reproduction. Candidate mask files and a matching procedure digest do not establish that the declared procedure generated them.

## Original score and improvement audit

The original primary score preserves the literal source matching algorithm, prediction order and multiplicity. Report all nine recall/precision/F1 values, the mean and each paired F1 delta. Empty predictions return zero through the inspected original helper; a nonempty zero-match case has undefined F1 from 0/0. Undefined values remain visible, and no video is dropped or silently replaced with an audit score. Full native-caller empty-path parity and native MATLAB execution remain unqualified.

Original matching has generated order-sensitive counterexamples. The separately named audit removes **exact duplicate prediction geometries** from both author and candidate, retains every GT instance, and takes maximum-cardinality one-to-one matches at IoU ≥ 0.5. It uses exact integer intersections/unions. Its F1 is `2*m/(G+P_unique)`, with empty/no-match prediction scores explicitly totalized to zero. This is a conservative extension, not the paper's scorer.

A **descriptive improvement on the same nine-video panel** requires all of:

- The original mean F1 increases, comparing exact count-derived rational means where the original score is defined.
- The unordered set of prediction geometries changes independently of ordering or exact duplicates.
- The separately declared audit mean also increases against the same author's outputs.

There is no arbitrary clinical margin. Floating tolerance is used only to check reproduction arithmetic, never as a scientific effect threshold. Exact duplicate-plus-token-geometry gains are rejected. A positive audit gain does not attribute the entire original-score delta solely to geometry: ordering or duplication effects may coexist, including on other videos. Near-duplicate masks remain distinct under this audit; positive results still do not demonstrate biologically distinct cells, population generalization or current global SOTA. Those claims require additional scientific evidence.

The authentic symmetric audit of the author reference was explicitly executed and independently reviewed. It found no exact duplicate author predictions and the same per-video match counts as the original primary. Both exact mean F1 values equal `741757236989669 / 1003523472340200`; the displayed means are 0.7391528523592015. Three per-video last-digit float differences arise from the different arithmetic expressions, while their exact fractions agree. This qualifies the saved reference and grading path; it does not reproduce training or establish an eligible assistance-condition attempt. Generic scorer flags remain conservative because the external admission and review are operator evidence, not facts inferred by the scorer.

## Trusted interfaces and present limits

`fold_inputs.py` freezes procedure/material/code identities and emits a participant manifest plus an operator-only read-only bind specification. It makes no movie copies or mounts. A specification does not enforce process isolation; a real protected runtime must implement and qualify the boundary before end-to-end agent claims.

`candidate_io.py` admits all nine candidate artifacts. `grade.py` takes an independently pinned operator reference specification, assistance condition and procedure digest; it admits the complete submission before decoding protected references. It checks all 27 original author metrics and the mean against the retained reference before returning a report. It executes no participant code and does not attest candidate production, native admission or benchmark readiness.

From the trusted source directory, the grading entry point is:

```sh
python -B -m suns2_benchmark.grade \
  --reference-spec /protected/operator-reference.json \
  --reference-spec-sha256 OPERATOR_SUPPLIED_DIGEST \
  --submission /frozen/candidate-submission \
  --condition paper_data \
  --procedure-digest COORDINATOR_FROZEN_DIGEST \
  --output /protected/new-report.json
```

Those are placeholder paths, not an execution request. Authentic decoding/scoring remains subject to the separately admitted native protocol. Keep operator specs, author masks and held labels outside candidate mounts. A public task also needs a pinned paper artifact and qualified source-code allowlist; the projector assumes their task-level delivery rather than silently supplying a PDF or a complete GitHub checkout.

All source data and published answers are already public. Protected execution prevents in-run leakage; it cannot establish that a model has never encountered these cases. Report this as an exposed development panel.

Component source attribution and the verbatim upstream license are retained in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and [LICENSES/SUNS2-upstream-GPL-2.0.txt](LICENSES/SUNS2-upstream-GPL-2.0.txt). Preserve the explicit component attribution exception when integrating this package.
