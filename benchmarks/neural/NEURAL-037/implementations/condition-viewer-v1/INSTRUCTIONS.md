# Predict a withheld condition's complete calcium-response mean

Use the supplied viewer to predict the recorded condition-mean trajectory for
every requested ROI in a withheld ABC or CBA condition. This is an exploratory,
viewer-mediated reconstruction task on six released acquisitions. The inputs
are averages of recorded trials, not raw trials. This route uses restricted
viewer actions; it is not a no-tools condition.

There are twelve separate context sessions: each of the six acquisitions is
queried once for ABC and once for CBA. A context supplies eleven training
conditions across the six acquisitions: the query acquisition's opposite order,
and both orders from each of the other five acquisitions. The withheld condition
is not available. The same ROI key aligns across orders within one acquisition
only. Never treat matching row numbers in different acquisitions as matched
cells, or treat the ABC and CBA trial axes as paired trials.

Each context starts with fresh state. Do not carry observations, predictions,
notes, conversation memory or learned state between contexts. A query condition
in one context is a training condition in another, so sharing information would
expose its answer. Use only the current session's supplied observations. Do not
retrieve source files, published response arrays, evaluator data or previous
answers.

## Read the observations

Each training row contains the mean and finite-observation count at every native
frame. A mean averages finite samples over all 50 released trials at that
cell/frame. A count of zero means no available observation. Its numeric mean-zero
placeholder is not a measured zero; the plotted gap must remain a gap in your
interpretation. Do not infer a response from an unavailable measurement.

Acquisitions 1-4 have 240 frames per row; acquisitions 5-6 have 200. Preserve their
original order. Physical timestamps, stimulation onset and fluorescence units
have not been established. Use the supplied numeric scale and frame indices;
do not convert them into milliseconds, assume an onset, or interpret a chosen
window as an isolated evoked response. Complete traces can include baseline and
stimulation-associated artifacts.

The original ROI counts are 251, 203, 139, 114, 257 and 168. All rows remain in
scope, including rows whose source response is wholly unavailable. Query target
values and their availability mask are not supplied. You must predict every
requested frame, rather than choose which positions to answer.

## Permitted actions

Send each action as one newline-terminated ASCII JSON object with an `action`
field naming the action below. The entire object, including this field and the
terminating newline, must fit within 8,192 ASCII bytes.

- `describe` gives the current context, query acquisition/order, complete query
  ROI list, frame count and authorized training-condition/ROI identifiers.
- `observe` takes a `training_condition` identifier of the form
  `acquisition_N_ORDER` and a `cell_key`. It returns that complete training row as
  a PNG plus its exact mean and count arrays. All eleven training conditions
  remain available; there is no selected subset of cells or frames. The context
  permits at most twice the total number of authorized training rows in
  observation calls, allowing every available row to be inspected twice.
- `submit` takes an object with exactly `action`, `cell_key` and `values`, with
  `action` set to `submit`. Supply the requested query cell key once, with one
  finite numeric prediction for every native
  frame: 240 or 200 values as declared for that query. Booleans, missing values,
  NaN and infinities are invalid. The complete serialized row must fit within
  8,192 ASCII bytes, including the action field and newline. Do not add commentary
  or other fields to this object.
- `finish` completes the context only after every required query ROI row has
  been submitted. Partial rows or a subset of ROIs do not complete it.
- `abstain` takes `action` and a nonempty `reason` of at most 256 characters and
  explicitly declines the whole context. An abstention is retained;
  it does not create a favorable score on the contexts you did answer.

Only these fixed actions are available. Do not run custom code, numerical
analysis tools, fitted predictors or external tools. There is no copy-row or
autofill action: you choose and supply the prediction values. Viewing a training
row does not automatically submit it as a prediction.

The complete twelve-context task requires 2,264 query rows containing 509,360
numeric prediction slots. Every row is required, even when some target positions
will later prove unavailable. The external output budget reserves 8,192 tokens
per row, or 18,546,688 tokens over the complete panel. That token reservation is
distinct from the 8,192-byte row limit and is not evidence that a model can
complete this task within its input, image, context, output or latency limits.
This is a large exploratory output obligation; complete-session feasibility has
not been established.

## Fixed evaluation

Lower normalized error is better. For each query cell, the scorer averages
squared error over the target frames with recorded observations. A cell with no
observed target frames has a null error and an explicit absence reason; it still
requires a complete prediction row. You cannot choose the evaluation mask.

Each context uses a training-only scale from its visible same-acquisition,
opposite-order condition. The scale is the square root of the equal-cell mean
of within-cell population temporal variances, using each training cell's
observed frames. Query values do not define the scale. The scorer averages
normalized cell squared errors equally over observed target cells, then takes
the square root. The primary statistic is the equal-weight mean of all twelve
context normalized RMSEs. It is not a pooled frame/cell error. A missing context
or abstention yields no complete-panel primary score.

Results describe these six acquisitions; they do not establish six independent
animals, population uncertainty, unseen-animal transfer or reproduction of the
source paper's findings. Dense condition-mean reconstruction may measure
numerical trajectory reconstruction rather than neural understanding. No model
performance or scientific admission has been established for this viewer route.
