# MARBLE Figure 5d endpoint

This component implements the published within-rat1 position-decoding endpoint:
32-dimensional embeddings, a uniform 36-neighbor cosine decoder, and mean
absolute position error over **all 2,000 query observations**, in metres. It
returns both population and sample standard deviations of absolute errors, with
their denominators named explicitly. Neither is labelled the publication's SD
until that convention is recovered. These deviations do not estimate uncertainty
across independent animals or independent time samples.

The existing `fit-closed-comparator` evaluates a separate four-rat clean/half-neuron
extension and drops the final row in each segment. It remains unchanged. The new
scorer neither truncates to 1,999 rows nor averages over rats or conditions, and
does not substitute median error for mean error.

The original support, preprocessing and checkpoint lineage remain unresolved.
There is consequently no authentic support JSON distributed here. A valid hash,
2,000 rows and matching identities establish numerical alignment, not a proven
join to the publication. Every result states this limitation. This component is
usable numerical evaluation software; it is not an admitted source reproduction
or a result exceeding the source paper. Both reproduction and exceeding the paper
remain first-class objectives requiring authentic source qualification and runs.

## Operator input

Use an externally frozen support JSON with exactly these fields:

```json
{
  "schema": "marble_figure5d_support_v1",
  "task_id": "PAPER-paper-method-034",
  "panel": "Figure 5d",
  "animal": "rat1",
  "unit": "m",
  "source_sha256": "<raw source SHA256>",
  "training_row_ids": ["<ordered source row identifiers>"],
  "query_row_ids": ["<exactly 2000 ordered source row identifiers>"]
}
```

Identifiers must be unique and disjoint across decoder training and queries.
The training count is deliberately not guessed from the later notebook; the
numerical kernel permits 36–10,000 training rows. This is an input bound, not a
new source-paper split. An independently admitted original protocol must fix the
actual identities and membership before either scientific objective is assessed.

Training JSON contains `row_ids`, a row-major `embedding` with exactly 32 columns,
and `position_m`. Query JSON contains only `row_ids` and `embedding`; supplying
labels in this object fails. Protected target JSON contains `row_ids` and
`position_m`. All four inputs must match the frozen support's order exactly.
No implicit reindexing, row dropping, unit conversion, averaging of independent
recordings, checkpoint deserialization or embedding training occurs.

Run `score.py --support SUPPORT.json --support-sha256 DIGEST --training TRAIN.json
--query QUERY.json --targets TARGETS.json` using the existing pinned numerical
environment. Inputs and output belong outside Git under the operator's evidence
root. The output includes aggregate scores, every consumed file's digest and byte
count, and NumPy/scikit-learn versions. It excludes positions, decoded predictions,
per-row errors and local input paths. The caller must isolate protected targets;
this standalone numerical tool is not a participant sandbox. The upstream
embedding-training access regime requires separate qualification.

## Sources and verification

The scientific source is [MARBLE Figure 5d and Methods, Linear maze experiments
in rats](https://pmc.ncbi.nlm.nih.gov/articles/PMC11903309/). The task's frozen
`improvement.v1.json`, metric/aggregation fields, and sibling
`paper-improvement-episode-v1/SOURCE_FINDINGS.md` preserve the inspected paper
claims and the unresolved paper/notebook discrepancies. The decoder uses the
same `KNeighborsRegressor(n_neighbors=36, metric="cosine")` as the existing
task-local `fit-closed-comparator/dependencies/score_core.py`; one execution thread
is explicit. Source revision:
`09491ec077bf153b7dece8518cc65ddaa20eb26d`.

`test_score.py` contains generated controls, including an independently calculated
last-row error where mean = 1 m, population SD = sqrt(1999) m and sample SD =
sqrt(2000) m. A 1,999-row or median substitute would produce zero. Other controls
exercise cosine versus Euclidean geometry, fixed neighbor count, query-label
rejection, reordered/overlapping identities, units, dimensions, nonfinite values,
JSON ambiguity and frozen-support tampering. Run only through the shared test pool.
These are software controls, not authentic data preparation or scientific evidence.

## Protected-target admission order

The CLI authenticates the frozen support before opening training or query files,
then validates their complete support and computes the fixed decoder prediction
before opening the protected target JSON. A malformed public operand or decoder
failure therefore cannot trigger target access through this entry point. The
decoder is called once, and the final report retains the same numerical endpoint
and input pins. The in-process `score` API is unchanged; its caller already holds
the target object and is responsible for custody. This ordering is not an OS
sandbox, a defense against a malicious decoder implementation, an exposure-history
certificate or evidence of historical scientific comparability.

Four additional generated controls exercise actual CLI read ordering, tampered
support, malformed/label-bearing public inputs, decoder failure and the complete
2,000-row result. The source and original-preprocessing consumer pins were advanced
together; prior `TESTING.json` receipts describe their historical source version.

## Complete three-method numerical panel

`panel.py` evaluates MARBLE, CEBRA-time and CEBRA-behaviour together. Its `methods`
JSON object must have exactly `marble`, `cebra-time` and `cebra-behaviour` keys.
Each value contains `training` and `query` objects in the formats above. All
methods must use the same frozen support, ordered row identities and training
positions. Different embeddings remain permitted. All three decoders finish
before the CLI opens the single protected-target file, and each decoder runs once.

```sh
python panel.py --support SUPPORT.json --support-sha256 DIGEST \
  --methods METHODS.json --targets TARGETS.json
```

The report retains each method's mean error and both explicitly named SDs over
all 2,000 observations. It also reports the mean paired error differences for
MARBLE minus each CEBRA comparator; negative values indicate lower MARBLE error
on the supplied support. It does not pool methods, average animals, omit the last
row or treat time bins as independent replicates. Input file digests and runtime
versions are retained; target positions, predictions, row errors and paths are
omitted from the report. The method input JSON has a 96 MiB byte limit.

The three methods and two descriptive contrasts follow cells 13 and 15 of the
[pinned official decoding notebook](https://github.com/Dynamics-of-Neural-Systems-Lab/MARBLE/blob/09491ec077bf153b7dece8518cc65ddaa20eb26d/examples/rat_hippocampus/decoding.ipynb).
Its plotting cell drops the final CEBRA row to match the released 1,999-row MARBLE
output; that plot cannot supply this component's required original 2,000-row
support. No Wilcoxon result, confidence interval, effect threshold or historical
contrast qualification is inferred from that cell. Complete Figure 5 reproduction
also needs the traces, representations, animal-pair consistency and robustness
companions specified in `reproduction.v1.json`. This numerical method panel does
not qualify those outputs or resolve the original-support and checkpoint gaps.

Run `python -B test_panel.py` in the existing numerical environment through the
shared test pool. The generated controls cover the full three-method panel,
independently calculated errors including the final row, shared training labels,
method completeness, row order, and target access only after all decoders finish.

## Finite numerical range

The ordinary mean and deviation reductions are preserved. If their intermediate
sum or squared deviations overflow, or a nonconstant error distribution produces
zero deviation by squared underflow, a bounded exact-input reduction supplies
the same finite mathematical statistics. This also preserves finite signed panel
means when their intermediate sum overflows. Source support, units and scientific
qualification are unchanged. Generated range controls include all2,000 rows.
