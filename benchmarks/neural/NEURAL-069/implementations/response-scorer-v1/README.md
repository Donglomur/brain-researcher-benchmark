# Complete response scoring for NEURAL-069

This component makes the current participant × ROI response-correlation endpoint executable. It accepts the full 10-participant, 8-ROI, 102-query-video panel, authenticates ordered video and native coordinate metadata, validates all 80 candidate arrays before opening targets, and reports every cell plus equal-ROI/equal-participant aggregates. It does not run candidate code, supply a participant packet, or establish scientific performance.

The scorer was recovered from local historical source, with a consequential weighting distinction made explicit. The historical `private/metrics.py` pooled voxels within V1, MT and STS, then equally weighted those **three families**. The current `understanding.v1.json` instead specifies coordinate means within each ROI, then **eight equal ROIs**, then ten equal participants. These can produce different values on the same predictions. `score.py` reports the current `participant_macro_roi_macro_voxel_pearson` as primary and the historical `participant_macro_family_macro_voxel_pearson` as a separately named companion. No historical score or canonical definition is changed. The companion recovers only the historical point estimator; it does not claim parity with the historical report's bootstrap intervals.

`io_contract.py` is an unchanged recovered source file. The selected numerical functions in `numerical_core.py` are verbatim recovered definitions; `SOURCE_PINS.json` records the original file hashes and source revisions. The new outer loader requires an externally supplied operator binding hash and an explicit packet location. It never discovers a historical private packet or defaults to one.

## Operator use

Use an existing NumPy environment (historical dependency pin: `numpy==2.2.6`). No dependency installation or data acquisition is performed. With a separately authenticated prepared packet and a sealed submission:

```sh
python3 -I -B score.py \
  --packet /operator/immutable-prepared-packet \
  --binding-sha256 OPERATOR_VERIFIED_SHA256 \
  --submission /sealed-candidate/submission.json \
  --output /fresh-output/report.json
```

The packet must contain `private/DATA_BINDING.json` using the recovered `boldmoments-private-binding-v1` layout. That binding must pin a `boldmoments-public-roster-v1` roster and all 80 targets. The roster specifies `sub-01` through `sub-10`, source ROI order `lV1v,rV1v,lV1d,rV1d,lMT,rMT,lSTS,rSTS`, train IDs `vid0001`–`vid1000`, query IDs `vid1001`–`vid1102`, three training repeats and ten query repeats, and sorted distinct coordinate triples for each cell. Repetition counts describe the already prepared arithmetic response means; this scorer does not recompute the projection.

The submission has exactly `task_id`, `roster_sha256` and ordered `predictions` fields. Each prediction record has `id,path,bytes,sha256`; `path` is a safe `.npy` basename. Arrays are primitive C-order float32/float64, finite, shape `(102,V)` in the authenticated roster order. Identity is bound by the roster hash; the scorer cannot establish that a candidate semantically used the correct video row merely from numeric values.

The operator must own the immutable packet root and obtain its expected binding hash independently of the candidate. Seal candidate output before scoring. This artifact scorer is not an execution sandbox, does not freeze a candidate program, and cannot protect a mutable root controlled by an adversary. Never mount the packet's private subtree into a participant runtime.

## Endpoint and limitations

Pearson is computed across query-video means per native coordinate; negative values remain negative. Exactly constant prediction on varying truth receives zero. A constant target or numerically unavailable coordinate propagates an undefined ROI, participant and complete primary; there is no available-case fallback. Missing/nonfinite candidate output is an invalid submission, while target or metadata faults are operator errors. A valid panel with undefined required metric support receives `undefined_required_support` and no numeric score.

Raw mean squared error is reported separately in squared prepared-response units, using the same ROI and participant weights. It is not noise-ceiling normalized and cannot be read as raw BOLD amplitude error. Unrepresentable squared errors are explicitly unavailable. No uncertainty interval is manufactured: paired participant/shared-video-family resampling and independently qualified static/motion comparator predictions remain to be supplied under a frozen scientific protocol.

The recovered preparation source selects Version B MNI152 response means. That differs from the Version A main-paper analysis. Its upstream joint GLMsingle and availability masks include released query trials; author PCA features standardize query covariates separately. The existing panel therefore remains public-development, fixed-derivative encoding, with transductive feature preprocessing. Source pins record this historical choice; array values, actual trial-coordinate joins and a newly prepared packet were not inspected in this revision. The external binding hash authenticates bytes supplied later by the operator, not scientific correctness by itself.

No authentic arrays or historical private targets were read, no data were downloaded, and no model was run for this component. The generated tests check numerical weighting, full-panel identity and malformed-output boundaries only. This does not deliver direct observation, typed viewer, tool-assisted investigation or frozen-program execution; those access-mode distinctions and their missing delivery remain unchanged.

## Paired complete-panel comparison

`compare.py` compares two sealed submissions against the same externally authenticated packet. Both complete 80-array submissions must pass the existing inert-file, roster, coordinate-shape and finite-value checks before any target array is opened. Targets are loaded once and the unchanged current scorer evaluates both captured panels. The report includes both full analyses, all 80 first-minus-second cell differences, ten equal-ROI participant differences, and their equal-participant mean. Undefined support on either side blocks the complete paired endpoint; invalid output is not removed or silently treated as an available case. The historical family-weighted companion remains separately named.

```sh
python3 -I -B compare.py \
  --packet /operator/immutable-prepared-packet \
  --binding-sha256 OPERATOR_VERIFIED_SHA256 \
  --first /sealed-method/submission.json \
  --second /sealed-comparator/submission.json \
  --output /fresh-output/comparison.json
```

Positive difference means the first submission has higher current-primary response correlation. This is an artifact comparison, not evidence that the inputs, compute entitlement, access conditions or method selection were matched. The operator must establish those separately before interpreting it as a direct-observation versus tool/program comparison or a dynamic versus static/motion contrast. The shared roster authenticates declared output identities, not semantic row use or absence of source exposure. It supplies no new uncertainty interval: eight ROIs remain repeated measures within each person, and shared video-family resampling remains unresolved. The public-development and Version B/transductive derivative limits above continue to apply.

Run the affected generated controls with `python3 -I -B test_comparison.py`. They cover a complete paired panel, independent current-versus-historical weighting, reversed direction, refusal of malformed second submissions before target access, both-side failure reporting, final-cell undefined support, operator target failures, and the CLI's exclusive report output. These generated checks do not run a model, read authentic arrays, enforce an access-mode runtime or establish empirical neural understanding.
