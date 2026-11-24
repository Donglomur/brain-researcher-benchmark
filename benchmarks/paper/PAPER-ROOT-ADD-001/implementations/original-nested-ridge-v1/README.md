# Sentence-group nested Ridge candidate

This operator candidate changes only Ridge alpha for the selected original
Figure 3b task: one population response, 30 supplied feature components, fixed
layer and lag selections, and the existing outer held-sentence split.

The public API is `candidate.py::predict(train_x, train_y, query_x, context)`.
The existing provider supplies `context.train_qid` and `context.held_qid`;
unused context metadata is ignored. Inputs must be finite ordinary float64
arrays with shapes `(N,30)`, `(N,1)` and `(M,30)`, with N and M positive. Training
sentence IDs must be aligned finite exact integers with magnitude below 2**53;
negative values remain valid. The outer held sentence must be absent from
training. Invalid mathematical operands are refused without deleting rows.

## Method

The alpha grid is `(0.001, 0.01, 0.1, 1.0, 10.0)`. Sort the unique training
sentence IDs and assign group rank modulo three. With at least three training
groups, each alpha receives exactly three inner fits. Each fit excludes every
row belonging to its validation sentence groups. Validation predictions are
stitched into original training-row order and evaluated with one pooled NumPy
Pearson correlation. Query data and query labels do not enter selection; the
selector helper receives no query operand.

Select the largest finite correlation. Scores within absolute 1e-12 of that
maximum are tied: prefer the original alpha 0.01 when tied, otherwise the
smaller alpha. Undefined correlations cannot beat finite scores. If all scores
are undefined, or there are fewer than three training groups, use 0.01. Refit
once on all outer-training rows, then predict all query rows. Numerical fitting
errors and invalid predictions fail explicitly rather than invoking another
fallback. Ridge options other than alpha retain the library defaults. There is
no scaling, feature/layer search, purge, row subsampling, alternative scorer or
outer-split change.

The public prediction shape is `(M,1)`. Ridge may return an ordinary float64
single-output array shaped `(rows,)` or `(rows,1)`. The exact vector case is
converted with `value[:, None]`; the column case is returned unchanged. Both
require the exact row count and finite values. Arbitrary reshaping, extra
columns, different dtypes and nonfinite values remain invalid. A generated
scikit-learn 1.9.1 diagnostic observed the vector shape despite fitting a
single-column target. This normalization changes shape only, not Ridge values,
options, model selection or data splits.

## Runtime and evidence limits

NumPy and scikit-learn provide the numerical implementation. The paired operator
harness supplies the pinned runtime; this candidate does not alter the author
reference's historical-version checks. Authentic comparison requires the same
pinned historical runtime. Diagnostics using a modern stack must state that
stack and cannot establish historical numerical equivalence or full-task
feasibility. Source compilation and generated diagnostics do not establish
reproduction, improvement, statistical significance, SOTA or native execution
qualification. An original-data comparative run remains required.

An eligible request has at most 16 Ridge fits: five alphas times three inner
folds plus one outer refit. Each 5,685-request candidate arm has at most 90,960
fits; two arms plus the 5,685-fit author reference total at most 187,605 fits.
These counts do not establish an adequate wall-time or RAM allocation. Matrix
copies, fits and stitched predictions require separate resource admission and
caller-enforced limits.

## Existing implementation distinction

The older `language-programme/vendor/operator/baseline.py` (3,190 bytes, SHA256
`dcc93c2101a55265cabc6bae88522f537759fb0d48d2168ed5cdf900436a0d78`)
belongs to the 70-episode/all-unit route and includes scaling, feature/layer
search, purge and larger-alpha tie preference. That inspected implementation is
different from this selected Figure 3b API and method. This distinction does not
claim a global search for every alternative implementation. Existing transport,
author reference, collection, outer split and scoring remain unchanged.

## Using the existing task route

Package the exact `candidate.py` as the candidate programme for the existing
`original-author-pairing-v1` route. Freeze separate candidate-tree manifests for
`paper_data` and `paper_data_author_code`; keep the literal
`executed_author_reference` programme unchanged. Each role retains all 42 jobs
and 5,685 held-sentence requests, with independent executions and the existing
complete prediction, closure and scoring checks. This component adds no provider,
runner, scorer or alternative endpoint. Using the same operator-authored programme
in both information conditions does not measure an AI information advantage.

Run the small generated controls with `python test_nested_ridge.py` from this
component. The observed diagnostic environment was Python 3.11.6, NumPy 2.4.6,
SciPy 1.17.1 and scikit-learn 1.9.1. Six checks passed after an exact single-output
shape correction; the initial failing diagnostic was retained separately. These
checks use generated arrays and an independent centered normal-equation oracle.
They do not execute the native provider or original data, and do not qualify the
author's NumPy 1.24.3 / scikit-learn 1.2.2 / SciPy 1.10.1 runtime.

Including alpha 0.01 in the search does not guarantee equal or better outer
held-sentence performance: inner selection can worsen generalization. Grouping
training sentences also does not undo supplied whole-session PCA or centered
response smoothing. Original preprocessing and timing limitations remain.

## Measured original-task follow-up

The unchanged candidate completed the [24 November trusted full Figure 3b comparison](../../docs/provenance/trusted-figure3b-nested-ridge-20261124/README.md): 42 cells, 14 sessions, eight people, 5,685 requests and 90,960 fresh fits on the historical numerical stack. It was non-improving: equal-session mean correlation 0.0449898090 versus fresh fixed-alpha reference 0.0451207116 (paired delta -0.0001309025). All outcome directions and negative results are retained. This is one operator candidate arm, not an AI information-condition comparison, participant-provider qualification or SOTA. The earlier generated-control history above is unchanged.
