# Original feature-decoding component

This component implements the source paper's leave-one-unfamiliar-face-out input
schedule, complete prediction assembly, and face-vector correlation metric for
facial-feature decoding (Fig. 2d).
It advances a source endpoint identified by the current improvement contract;
it does not change that contract, replace the historical geometry implementation,
or select a scalar paper-win endpoint.

The same original split is useful for both first-class paper outcomes: reproducing
the published decoding findings and exceeding source-paper decoding performance.
Those outcomes require separate scores. Later participant delivery should retain
paired paper-and-data and paper-data-and-author-code conditions; the current
component neither admits those episodes nor fabricates unavailable author code.

For each of the 1,000 unfamiliar faces, `FeatureDecodingInput.fold` returns the
other 999 unfamiliar faces as training observations and the omitted face plus
all 36 familiar faces as query observations. Responses are supplied for one
already-prepared original time window. The caller supplies complete explicit
face identities and feature coordinate order. Only unfamiliar feature targets
are accepted by the input component; familiar feature targets belong to the
separate scoring operator.

`assemble_predictions` accepts all 1,000 fold predictions, aligns them by face
identity even when workers return arbitrary order, and preserves familiar
predictions as `[fold, familiar face, feature]`. Missing folds, duplicate folds,
misassigned held-out faces, missing familiar queries, unequal feature dimensions,
and nonfinite values fail. No partial result is promoted to a score. It does not
average 36,000 familiar predictions as if they were independent faces.

`score_feature_correlations` computes Pearson correlation across the feature
coordinates of each actual/decoded face-vector pair. It retains 1,000 unfamiliar
scores and 1,000 × 36 familiar scores, including explicit undefined states for
constant vectors. It returns neither a panel mean nor an SEM. Correlation is
higher-is-better; reproducing the original curves and exceeding their performance
remain separate future evaluations.

The implementation uses Python's standard library. A typical operator flow is:

```python
roster = FaceRoster(unfamiliar_ids, familiar_ids)
inputs = FeatureDecodingInput(roster, response_rows, unfamiliar_feature_rows)
for packet in inputs.folds():
    # Fit the predeclared method using training_responses/training_features.
    # Predict features for query_responses and return FoldPrediction.
    ...
complete = assemble_predictions(roster, returned_predictions, feature_count)
# Operator-side only, after predictions are frozen:
per_face = score_feature_correlations(roster, complete, actual_feature_rows)
```

The current component receives prepared numeric inputs rather than opening an
archive. It never infers source identities from array positions, generates a new
face split, imputes missing responses, normalizes features, subsets neurons, or
fits a decoder. Familiar target exclusion is an API property, not an adversarial
security boundary. All unfamiliar targets become available across the original
LOOCV folds; no prospective unseen-face generalization claim follows from this
source protocol.

## Source basis and remaining qualification

The [published article](https://pmc.ncbi.nlm.nih.gov/articles/PMC11111405/), Fig. 2d
and its caption, evaluates time-dependent linear facial-feature decoding and ten
stimulus-identity-shuffled control repetitions. The [supplementary methods](https://static-content.springer.com/esm/art%3A10.1038%2Fs41586-024-07349-5/MediaObjects/41586_2024_7349_MOESM1_ESM.pdf),
“Face feature decoding and reconstruction”, supplies the 999/1,000-fold rule and
the separate familiar-face queries. Its additional legend for Fig. 2d specifies
correlation between actual and decoded feature vectors and 50-ms windows stepped
10 ms. The paper's Fig. 4g MSE endpoint and the old axis-cosine reconstruction are
different measurements. Exact source identities and hashes are in
`SOURCE_EVIDENCE.json`.

The complete original panel-specific neuron/face roster, actual source feature
coordinates and exact scaling population, temporal boundary convention, published
numerical baseline, original decoder implementation, panel reducer, and shuffle mapping
still need binding before scientific qualification. A caller cannot establish
these facts merely by supplying arrays of the expected dimensions. The historical
AM134/PR72/TP197 geometry roster is not automatically a verified decoding roster.
The supplement itself lists PR76 for Fig. 3a, whereas main Fig. 2c lists PR72;
neither is silently imported as the Fig. 2d roster. It also describes eight novel
screening faces in addition to the thousand-face set and a second stimulus set
with different repetition structure. Archive row positions cannot identify the
required 1,000/36 face roster without a verified join. The supplement says feature
dimensions are scaled by their standard deviation; the historical geometry
implementation's full-matrix RMS scaling is not automatically decoder parity.
All ten shuffled controls must remain part of any later full Fig. 2d comparison.
This module does not reconstruct their unavailable original draws.

No authentic data preparation, decoder fitting, author parity, candidate trial,
paper improvement, independent-animal inference, or current-SOTA claim is made.
Status remains **source-unresolved; executable supplied-input decoding component**.

`test_decoding.py` contains generated software controls for the complete 1,000-fold
schedule, identity/order preservation, query-target omission, complete-output
enforcement, invalid-value refusal, analytical correlation counterexamples, and
preservation of familiar-fold dependence. These controls do not establish paper
performance. Run them only through the shared generated-test pool during the
parallel build.
