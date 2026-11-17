# UMBRAE original endpoint vector

`endpoint_vector.py` adds an executable paired comparison to the reviewed first-box scorer. Its primary output is the original **S1/S2/S5/S7 All-category REC accuracy vector**, in percent. It never collapses these endpoints into a paper-win scalar. The original scorer and historical evidence are preserved.

The [current improvement contract](../../improvement.v1.json) identifies a concrete gap: the original implementation provides per-subject scores but pools the paired uncertainty comparison. This version computes a separate percentage-point contrast for each subject against the official-baseline, neural-free and shuffled-neural arms, retaining the original first-box, strict IoU > 0.5, query denominator, complete population and exposure checks. The secondary salience/IoU summaries and individual query rows remain available. The 982 shared-image/5,829-box original population remains required by the `paper_population` input profile; generated controls cannot authenticate those identities.

## Operator use

Python 3.10+ standard library, no installation. Use the same operator-side contract, annotations and image-order inputs documented by [v1](../../docs/initial-evaluator-v1.md):

```sh
python3 endpoint_vector.py --contract CONTRACT.json --annotations ANNOTATIONS.json --image-order ORDER.json --output NEW_RESULT.json --draws 1000 --seed 0
```

The caller must enforce candidate/reference isolation. Coordinates, predictions and detailed results are private operator artifacts, not public repository files. No data acquisition, model loading, inference or training occurs in this component. Output creation is exclusive. The implementation checks the predecessor scorer's reviewed SHA-256 before loading it.

## Numerical semantics

For each subject and comparator, the difference is 100 times the difference in correct query counts divided by the full common number of image/category queries. A missing prediction already contributes an incorrect query through v1; it never changes the denominator. The complete query key set must match across all 16 subject/arm combinations. Duplicate queries reject rather than being overwritten. Images with multiple categories contribute multiple queries; they are not averaged to an image score.

A bootstrap draw samples the shared image list with replacement exactly once. That image multiplicity applies jointly to every subject, every arm, and every category query. Thus shared-stimulus dependence is retained. The resampled denominator is the selected query count, not the number of selected images. The 12 contrasts (four subjects times three comparators) form one declared family. For each draw, take the maximum absolute deviation of the resampled difference vector from the observed difference vector. The nearest-rank empirical confidence quantile of these maxima gives a common radius for an approximate simultaneous band; bounds are intersected with [-100,100] percentage points. The default confidence is 0.95; `--draws 0` omits uncertainty.

Empty-query images stay in the sampling frame. If any draw has zero queries, its difference is undefined. The report counts such draws and emits no interval, avoiding silently conditioning on the nonempty resamples. An identical-arm zero-width band is an empirical property of this bootstrap and does not establish that true uncertainty is zero.

This is a **prospective diagnostic**, not the author's analysis, a finite-sample coverage guarantee, or an adopted improvement decision. Native parity, a justified effect margin, sufficient resamples and a prospectively accepted uncertainty protocol remain necessary before a paper-win claim. The output does not issue pass/fail or superiority. It reports the documentary v2 Table 2 baseline (18.93/18.27/18.19/16.74 percent) separately from the input arm's computed scores; the latter's name does not attest author execution. No new-subject inference is supported.

## Evidence and verification

[Source pins](SOURCE_PINS.json) retain immutable author revisions and local dependency identities. The prior exact source audit was reused; no source downloads, annotations, fMRI, tensors, predictions, weights or private historical solver targets were accessed for this revision. The new tests use generated boxes only. An independently hand-enumerated two-image case exercises unequal query counts, joint resampling and the 12-contrast max-deviation radius. Further controls cover a losing subject hidden by a favorable pooled mean, first-box scorer integration, strict threshold, identical arms, zero-query draws, all subjects/arms, key multiplicity, order invariance, invalid inputs and the actual CLI.

Run tests through the project's coordinated two-slot lightweight test pool. Native baseline/candidate execution and scientific qualification remain absent. Registration status remains design-ready; this component does not make the benchmark improvement-ready.
