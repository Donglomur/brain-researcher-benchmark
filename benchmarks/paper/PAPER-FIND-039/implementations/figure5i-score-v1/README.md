# Figure 5i position-decoding score component

This independently written component computes the current task's circular
decoding endpoint from predictions. The older `initial-evaluator-v1` covers
Figure 2. Reproduction and improvement are separate benchmark outcomes; this
component supplies neither a qualified reproduction nor a superiority decision.
No data, author scores, fitted model, or original fold realization is bundled here.

For each of the original 61 sessions, compute the mean cosine angular error
within each test fold, then average the ten fold scores equally. Average those
session scores separately over 34 young and 27 aged sessions. Unequal fold
lengths must not turn this into an observation-weighted mean. All three arms
(candidate, author replay, spike-shuffle control) retain their full session and
fold vectors. The report preserves candidate-minus-author differences and
mouse identities; it supplies no pooled scalar, significance test, or paper-win
decision.

## Source

[Herber et al., Methods: Position decoding analysis](https://pmc.ncbi.nlm.nih.gov/articles/PMC12494969/)
defines the score and ten repetitions. The immutable
[Figure 5 notebook](https://raw.githubusercontent.com/GiocomoLab/Herber2024/1a9dd3040c9f77662caf26a34c9452403579087a/Figure%205.ipynb)
at revision `1a9dd3040c9f77662caf26a34c9452403579087a` supplies these exact
implementation locators:

- Cell `2663112c`, `CircularRegression.score`: mean cosine difference. Its
  docstring's “1 minus” wording disagrees with its executable return; this
  component uses the executable return, which also agrees with the paper.
- Cell containing `train_vs_test_blocks`: ten `array_split` test blocks in the
  supplied downsampled observation order, random training selection without
  replacement from the complement, size `int(n * 0.9)`.
- Cell `f8f3b4f0`: more than ten `spatialcell99` cells, non-single-map
  classification, optimal `SilN == 2` define `2map` eligibility.
- Spatial-cell fitting: both-map/random-selection scores are the fifth row of
  `spatialscores` and `spatialshuffscores`.
- Cell `d2f71db7`: `mean(..., axis=1)[-1]` selects that row after averaging
  repetitions. Cell `13202cdc` prints 34 young and 27 aged sessions.

The notebook's printed stratum means are published-output evidence, not a
reproduced author vector. Original stochastic training/downsampling indices,
classification, score files and exact cohort remain unbound.

## Operator interface

Use only an independently admitted original reference. Calling this program
with invented or newly drawn references cannot establish original-cohort or
original-split recovery. Receipt strings are binding metadata, not signatures
or proof of their contents. Keep empirical references, predictions and reports
outside public source control. This command is an operator scoring component;
it is not a participant sandbox and provides no target-access isolation.

```text
python3 -B score.py REFERENCE.json CANDIDATE.json AUTHOR.json SHUFFLE.json REPORT.json
```

The reference is JSON with these fields:

```text
schema: "figure5i-reference/v1"
task_id: "PAPER-FIND-039"
source_revision: "1a9dd3040c9f77662caf26a34c9452403579087a"
condition: "spatial_cells_both_maps"
cohort_receipt_sha256, preprocessing_receipt_sha256, split_receipt_sha256
sessions: [
  {mouse_id, session_id, age_group: "young" | "aged",
   optimal_k: 2, source_onemap: false,
   spatial_cell_ids: [unique strings; count > 10],
   downsampled_observation_ids: [unique strings in ORIGINAL ds_all order],
   folds: [{repeat: 0..9, test_observation_ids, train_observation_ids,
            target_radians: [finite numbers in test observation order]}]}
]
```

All identities are strings so nanosecond-derived identifiers and large integer
keys are not rounded by JSON clients. The program validates unique identities,
all 61 sessions, age consistency within mice, cell/map eligibility declarations,
an explicit boolean `source_onemap: false`, all ten fold IDs, the source test partition, train/test disjointness, exact
training size and target coverage. It cannot validate the scientific truth of
those declarations. For Figure 5i, `ds_all` is both the train and test pool;
cross-map Figure 5j/k scores are outside this interface.

Each prediction packet has schema `figure5i-predictions/v1`, a
`reference_sha256` computed by `reference_digest(reference)`, and `sessions`.
Each session has `mouse_id`, `session_id`, and ten `folds` containing `repeat`,
`test_observation_ids`, and `predicted_radians`. Session/fold list ordering may
vary; test-observation order must match. Angles use radians, including equivalent
wrapped angles. Non-finite values, missing observations and incomplete panels
are errors rather than silently dropped rows.

The reference records the original real-arm training indices. The author and
candidate must use those same indices under an upstream replay protocol. The
source shuffle decoder independently draws training membership from the same
eligible complement; its own realized training membership belongs in the
split receipt. All three arms use the same test identities. This scorer sees
predictions only and cannot verify model inputs, training access or shuffle
generation.

## Validation and limits

The package's standard-library unittest suite uses only generated 61-session
fixtures. It checks angular geometry/wrapping, unequal-fold weighting, session
weighting and separate strata, complete coverage, training leakage, source
partition/order, digest rebinding, companion arms and the JSON CLI. Execute it
only through the wave's shared test pool during parallel construction.

No native preparation, fitting, inference, real score, effect threshold,
mouse-clustered uncertainty calculation, original-score recovery, rights
qualification or protected participant route is established. The benchmark
remains source unresolved. A qualified original reference and author replay
are prerequisites for scientific evaluation; this component does not make
them ready by accepting structurally valid input.
