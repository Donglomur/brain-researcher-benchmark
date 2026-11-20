# Source predictive-likelihood replay

This component recovers and executes the **author's per-cell Poisson likelihood**, preserving the existing prospective evaluator as a separate analysis. It provides an operator-only MATLAB export bridge and a dependency-free Python replay/comparison scorer. No neural data, author fits, new model runs or scientific improvement are supplied.

For author predictions `mu` (expected spike **counts per source bin**) and counts `y`, the original score is

```text
LL = sum_bins(-mu + y * log(mu) - lgamma(y + 1))
cv2NegLnL = -LL
```

There is no division by bins, trials, spikes or exposure, and the factorial term is included. `mu` is already `exp(XW)`; interpreting it as Hz and multiplying by bin duration would change the source score. The native bin size is retained verbatim; this does not resolve the paper's 25-ms versus converter-default 50-ms discrepancy. No cross-cell reduction is defined here because no original scalar population predictive score has been recovered.

## Source findings

These findings come from previously cached author code, verified against the existing provenance pins. No new downloads were needed. See [source-recovery.json](source-recovery.json) for hashes and precise locators.

* `CategorizedModel.poissonLogLikelihood`, lines 97–100, defines the exact score above. `xvalRegularizationPath`, lines 152–174, constructs held-out predictions before evaluating this sum. This narrows the current contract's uncertainty about **per-model normalization**, without recovering any authentic numerical baseline.
* Hierarchical models represent partitions of a cell's source trials. `jointPrediction`, lines 545–580, assembles their predictions at original global bin positions. The replay requires complete, disjoint support and matches the native joint score. It never averages category scores.
* `specialize`, lines 448–452, copies a progenitor's entire `fitInfo` into a child with insufficient trials or no effective split. Therefore a leaf's stored `cv2NegLnL` can refer to its **parent's larger support**. Summing these stored fields is unsound. The exporter records whether a leaf's `fitInfo` exactly equals its progenitor's; the replay recomputes every leaf score from the corresponding target/prediction rows. A stored-score mismatch is accepted only with this equality evidence and is visibly reported. Equality is a diagnostic, not proof of historical fit provenance.
* `regress`, lines 496–524, creates two local CV assignments. Lines 529–541 save `fitInfo`, weights and predictions, but never assign the local `cvTrainSel` to the object property. The property starts empty. Loading a saved fit therefore does not by itself recover the original folds. The `cvpartition` created at line 499 is unused by the scoring path.
* The `cv1NegLnL` field set at line 507 is replaced when line 516 overwrites `fitInfo` with a fresh result from `fitRegularizationPath`. Retaining `bestIndex`, `cvW` and `cv2NegLnL` does not restore the omitted selection scores or folds.
* The source uses response-derived five-trial baseline smoothing before CV and selects hierarchy specializations using their CV likelihoods. These are the source information/selection conditions; the resulting score is not a newly untouched final evaluation. This component neither removes those inputs nor invents a new split.

## Operator path

Authentic execution remains pending a separately coordinated native protocol. The bridge is an implementation for that future path and has **not been executed in MATLAB**. It requires a clean MATLAB process with the pinned author class and its original loading dependencies on the path. It verifies the resolved `CategorizedModel.m` SHA256, loads explicit existing `fitSingleCellGLM` saves, and calls their native `jointPrediction` and likelihood methods. It does not fit models, regenerate CV folds, search for data, or read historical solver targets.

```matlab
export_dentate_scores({'operator-owned-fit.mat'}, '/private/evidence/author-export.json')
```

The export contains target spike counts and predictions. Keep it outside Git and outside the participant interface. It preserves every source fit entry, including source experiment structs for unfitted cells. An empty/unfinished model or final hierarchy fails rather than being silently dropped. The supplied fit files need separate provenance and complete-cohort reconciliation; a matching class hash does not authenticate the scientific data or their historical generation.

```sh
python3 replay.py --author-export /private/evidence/author-export.json \
  --output /private/evidence/replay-report.json
```

The report preserves cell/animal identities, actual trial/bin counts and bin sizes, unmodified source exclusions, native score reconciliation, and leaf diagnostics. It contains no targets or prediction arrays, but remains operator evidence until approved for release. Existing output files and source inputs are not overwritten.

The JSON export uses `schema: dentate-author-score-export-v1`, the pinned `source_commit` and `source_class_sha256`, and a `cells` array. Each fitted cell includes source-selected trial indices, original trial numbers, the one-based selected-trial index of every bin, original counts, unspecialized predictions and `cv2NegLnL`, and final hierarchy leaves with their full source-bin indices, trial indices, counts and predictions. The MATLAB exporter defines all exact field names; generated software fixtures in [tests/test_replay.py](tests/test_replay.py) illustrate the format without authentic observations.

Positive integral JSON indices are accepted as either `1` or `1.0` and
normalized to Python integers for indexing. Fractional, nonpositive, boolean,
nonfinite and duplicate indices remain invalid. Normalization does not mutate
the export or change its source-support commitment.

Optional candidate means can be scored on exactly the same supplied support:

```sh
python3 replay.py --author-export /private/evidence/author-export.json \
  --candidate /private/evidence/candidate-means.json \
  --output /private/evidence/comparison.json
```

The candidate file has `schema: dentate-candidate-means-v1` and a `cells` array. Each cell supplies `monkey`, `cell_id`, `source_support_sha256` from the replay report, and parallel `bin_indices`/`prediction_means` arrays. All source fitted cells and bins must appear exactly once. The scorer aligns predictions by explicit bin identity and returns per-cell `candidate_minus_source_hierarchical_nats`. This is a numeric paired comparison only: no candidate information boundary, original fold identity, training provenance, uncertainty, useful-effect threshold or improvement claim is admitted by this interface. The support hash binds identities and bin layout, not historical provenance. The CLI separately hashes the complete author export and candidate file for the operator receipt.

## Validation and remaining work

All 16 generated controls passed in shared-pool run `paper04-dentate-score-replay-02` (0.074055 child CPU seconds; 27,688,960 bytes child peak RSS). The first pool attempt was busy and launched no test process. These are software-control costs, not authentic source runtime measurements.

The Python tests use generated counts and independently calculated Poisson probabilities. They cover the factorial constant and unnormalized sum, unequal trial lengths and nonconsecutive category partitions, inherited parent scores, missing/overlapping support, altered targets, wrong native scores, malformed predictions, original-five-fold declarations, duplicate identities/JSON keys and candidate pairing. Numerical replay uses Python's `math.isclose` with absolute tolerance `1e-8` and relative tolerance `1e-10` to accommodate arithmetic reductions; these are not scientific-effect thresholds. Positive finite means are required because the literal source expression produces NaN for `0 * log(0)`.

Remaining scientific gaps are authentic archive/fit acquisition, complete eligible DN cell/trial mapping, converter/run settings, original fold retention, native MATLAB/SPAMS qualification, original numeric baseline, population aggregation, comparison information conditions and dependence-aware uncertainty. No source/cohort data were opened in this construction. The original task and improvement contract remain unchanged and source-unresolved. Proposed integration wording is in [integration-proposal.md](integration-proposal.md).

The endpoint and MATLAB field semantics are attributed to Sue Ann Koay and the ErasmusAttn_2020 authors, revision `130f5e64f86bd63980f70bb839c02cd264782aef`, licensed under CC BY 4.0. The replay/export code is a new implementation; author source and data are not bundled.
