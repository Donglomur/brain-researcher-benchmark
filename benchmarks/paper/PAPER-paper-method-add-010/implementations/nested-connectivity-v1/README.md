# Conditional nested MEG connectivity evaluation

This component fits and evaluates a prospective **single-measure classifier** over
an explicitly supplied 246-measure feature table. It provides exhaustive nested
participant selection, complete prediction/support ledgers, and separate scoring.
It is the first owned evaluation component for PAPER-paper-method-add-010.

It does **not** implement the entire paper or the canonical
connectivity-versus-nuisance comparison. Authentic feature extraction, the nuisance
inputs, the exact historical 246-measure selection, and corrected-supplement
identity remain unresolved. Every result keeps scientific qualification and
whole-task completion false.

## Scientific scope and a concrete proposed design

[PROSPECTIVE_DESIGN.json](PROSPECTIVE_DESIGN.json) proposes one primary benchmark
endpoint: Category_Selective→Prefrontal_Cortex, irrelevant task condition, stimulus
onset [0, 1000 ms), face versus object. It proposes 10 outer/5 inner participant
folds, C=1 balanced L1 logistic models, training-only standardization, and
equal-participant balanced accuracy. Other endpoints are descriptive. This is a
prospective analysis proposal after the original results became public, not an
independent confirmatory scientific test on that same public cohort.

The [published roster](published_participants.txt) contains the 94 identifiers
from the pinned official repository; its exact bytes match the upstream Git
object. [PROSPECTIVE_FOLDS.json](PROSPECTIVE_FOLDS.json) gives deterministic proposed
folds derived without outcomes. `design.recommended_fold_plan` reproduces them
from all 94 identifiers. Source identity, biological aliases, authentic feature
membership and complete observations still require independent admission.

The endpoint concerns category decodability during consciously seen stimuli. It
does not establish consciousness detection, a necessary/sufficient neural
correlate, physiological causal direction, or adjudication between consciousness
theories. A directed feature pair is an orientation in the feature calculation.

Two estimands remain distinct:

* This component conditions on a supplied historical **246-measure domain**. The
  original domain was screened using the full cohort. Freezing that list does
  not retrospectively make feature eligibility nested or the public cohort unseen.
* A future **262-candidate**, independently preconfigured domain with training-fold
  eligibility would require a separate source/protocol identity. This component
  does not silently substitute that condition.

## What is implemented

`core.fit_predict_fold(features, training_labels, protocol, fold_id)` accepts
**only the exact outer-training label keys**. It evaluates every declared
measure/C candidate on inner participant-disjoint out-of-fold predictions, chooses
the declared metric's maximum, refits using all outer-training observations, and
predicts every outer-test observation. Exact score ties retain measure order and
then C order. Probability 1/2 chooses the first declared class. Ordered endpoint
classes are explicitly encoded as 0/1, independent of lexical class names.

Every scalar model uses balanced row-class weights and L1 logistic regression
with the `liblinear` solver. This preserves the original classifier family while
changing preprocessing/selection. Training row-class weights do not equalize
participants with unequal observation counts. Equal-participant weighting applies
to selection and reporting; a different training-weight policy would be a
separate protocol. All compared methods need the same declared weighting.

Mean and population standard deviation are fitted on each training partition.
Input magnitude scaling makes those calculations stable for large finite values.
Held-out examples never determine transform statistics, selected measures or C.
A constant training feature uses the exact balanced intercept-only solution:
probability 1/2. Missing/nonfinite feature values, incomplete support, numerical
range failures and nonconverged fits cause refusal, without omitting a candidate,
participant or fold. This is an explicit prospective policy, not inherited
historical imputation/QC.

`core.run_nested` computes all folds and `core.score_predictions` reports per-person
confusion matrices, class recall, accuracy, balanced accuracy and equal-person
aggregates, plus pooled accuracy for comparison. Balanced accuracy is undefined
when a participant lacks either class. If selected for optimization, that state
refuses evaluation; descriptive scoring reports null and identifies every affected
participant. There is no t test or confidence interval treating folds as
independent experimental replicates.

`run_nested` is an **operator-side reference convenience** holding all labels. It
is not a protected candidate harness. The single-fold API enforces a software
label boundary; process isolation, physical source provenance and private-reference
custody remain separate requirements.

## Required complete inputs

The strict JSON schemas reject unknown fields. The generated example below gives
a fully concrete valid instance. Authentic inputs must independently establish the
following, rather than merely copying the example's shape:

| Input | Required content |
| --- | --- |
| Protocol | Exact 246 ordered measure IDs and canonical participant IDs/alias mapping; explicit binary endpoints with directed region pair, relevance and time tags; a complete observation-ID/participant ledger per endpoint; every outer test and inner validation participant partition. |
| Estimator/selection policy | Explicit ordered positive C grid, seed, solver tolerance/iteration cap, one of participant-mean accuracy or balanced accuracy, deterministic ties, refusal for missing/nonconverged inputs and the constant-feature rule. |
| Source policy | Source-manifest identity, exact measure-domain hash, selected data version and optional held supplement hash. A hash is an identity commitment, not evidence of correct physical derivation or a verified publisher join. |
| Feature table | Every expected observation exactly once, canonicalizable participant alias, endpoint ID and all 246 finite scalar values in declared order. No target field. `sampling` must declare label-independent observations. |
| Labels | A separate observation-ID→class mapping; exactly outer-training keys for `fold`, complete keys for operator `evaluate`/`score`. |
| Execution limits | Explicit positive maximum observations, model-fit calls and ledger records. Full workload preflight refuses an inadequate budget before any fit; it does not truncate the scope. |

All declared participants must have observations for every declared endpoint.
Every outer-test participant occurs exactly once; inner validation exhaustively
partitions that outer training population. Aliases cannot split one declared
biological identity across folds. These are checks on supplied records, not proof
that the aliases or observations match real acquisition.

Known-category averages are rejected by the prospective input schema. Merely
changing the sampling declaration cannot make them label-independent: physical
provenance remains unverified in every output. Features start **after FC
extraction**; this package does not reconstruct them from regional time series.

`source_version` admits the canonical `zenodo:15315238` identity or explicitly
`generated` construction inputs. It rejects a silent v2 substitution. The
source-manifest hash must be shared by the table and protocol. The actual archive,
feature extraction and observation join have not been acquired or qualified here.

## Generated example and source controls

The following example uses four invented people, eight invented observations and
246 invented feature IDs. Its selected feature was deliberately constructed to
separate the two labels. It is an engineering check, not a neuroscience result or
a reduced paper reproduction. It evaluates the complete support of that generated
protocol; it does not assert the authentic 94-person contract is complete.

From this implementation directory, with Python 3.11 and the dependencies below:

```sh
python3 -B make_generated_example.py /tmp/meg-generated-example
# The generator prints the exact protocol-file SHA-256. Supply that printed value:
python3 -B run.py preflight \
  --protocol /tmp/meg-generated-example/protocol.json \
  --protocol-sha256 PRINTED_PROTOCOL_SHA256 \
  --features /tmp/meg-generated-example/features.json \
  --max-input-bytes 1000000 --max-output-bytes 100000 \
  --output /tmp/meg-generated-example/preflight.json
python3 -B run.py evaluate --operator-offline-reference \
  --protocol /tmp/meg-generated-example/protocol.json \
  --protocol-sha256 PRINTED_PROTOCOL_SHA256 \
  --features /tmp/meg-generated-example/features.json \
  --labels /tmp/meg-generated-example/labels.json \
  --max-input-bytes 1000000 --max-output-bytes 4000000 \
  --output /tmp/meg-generated-example/result.json
```

`fold` additionally takes `--fold-id` and outer-training-only labels. `score` takes
`--predictions` containing the prediction mapping from the result. Output paths
must be new; existing inputs/results are never overwritten. Complete serialized
outputs are published with an exclusive hard link from a same-directory temporary
file. The wrapper compiles the exact sibling `core.py` bytes and reports their
SHA-256; it never executes a stale cached core bytecode file. Use a reviewed release
and its current source descriptor to verify that identity before trusted use.

The example's preflight is 2,956 fit calls, 3,968 ledger records and eight
observations. Constant-feature fits are cheap; the estimate deliberately counts
them. These counts and byte caps are logical limits, not measured physical I/O,
RSS, solver scratch memory, wall time or immutable-publication guarantees. The
Python JSON structure and output serialization are held in memory. Authentic
execution needs independent resource admission; the supplied budget is not one.

From the repository root:

```sh
python3 -B -m unittest discover -s tests/construction -p test_meg_nested.py -v
```

Local validation uses NumPy 2.4.6, SciPy 1.17.1, scikit-learn 1.9.1 and its
installed dependencies. Pure-L1 `l1_ratio=1.0` follows the
[scikit-learn 1.9 API](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html).
No runtime downloads, upstream code execution, authentic model campaign or
dependency installation are performed by this package.

## Source evidence and remaining comparison requirements

[PROVENANCE.json](PROVENANCE.json) records exact inspected source identities.
The [pinned author classifier](https://raw.githubusercontent.com/anniegbryant/MEG_functional_connectivity/cab648bbe2eab7093f9ab7b9a5fcddabf28e60a0/classification/fit_pyspi_classifiers.py)
and [normalizer](https://raw.githubusercontent.com/anniegbryant/MEG_functional_connectivity/cab648bbe2eab7093f9ab7b9a5fcddabf28e60a0/classification/mixed_sigmoid_normalisation.py)
motivate the explicit historical/prospective distinction. The inspected metadata
table lists 284 measures; it is not the required post-QC 246-measure roster. The
[published paper](https://doi.org/10.1093/nc/niag029) and
[correction](https://academic.oup.com/nc/article/2026/1/niag071/8916853) do not by
themselves authenticate a selected supplementary PDF.

The canonical comparison still requires matched local-amplitude or power nuisance
features, a fixed Spearman anchor with verified domain membership, and defined
source-mixing robustness controls. The canonical record does not specify nuisance
frequency bands, spatial/time aggregation or per-observation feature schema.
Authenticated, aligned label-independent FC/nuisance observations are also absent.
Inventing nuisance features from the FC columns would not solve those gaps.

The [canonical task](../../task.json) remains unchanged. Full paper agreement,
competent reference performance, leakage/exposure qualification, data/code rights,
protected candidate execution and the complete scientific comparison remain held.
