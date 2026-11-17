# Original language input and prediction integration

This additive component connects the original C1–D1 observations and prediction
requests to the existing `original-figure3-v1` reader/reducer. It requires all14
sessions from eight people, all16 output fields per session,40 time lags and33
supplied PCA layers. It also supplies Figure3e's separate population-weight join.
It adds no task IDs or scientific readiness claim.

## Source inputs and preparation

`source-bindings.json` binds the released archive sizes/publisher MD5s, original
session geometry and196 selected entries:168 numerical inputs,14 cleaned CSVs,
and14 `self_FR_aligned2word.npy` files. The numerical input headers were previously
recovered; their bodies and the14 weight headers were not authenticated in this
construction. These source headers and ZIP directories are metadata evidence,
not a completed data preparation. `analysis.zip` is listed for the separate
original-result comparator; this producer reads only data, DNN and transcription.

`ArchiveInputs` verifies whole local archive size/MD5, records SHA256 and checks
every selected central-directory entry before reading scientific members. It
then verifies full member CRC and SHA, shape, float64 dtype and exact NPY extent.
There is no pickle load, PCA refit, language-model inference or full-archive
extraction. Arrays are held one session at a time. Declared resource limits are
logical admission checks; the caller must enforce OS process/RAM/time limits.

The original CSV order, word timing and qid are retained. Features are written
into100-ms bins using integer-truncated intervals; gaps receive the source
component mean. A qid≥99990 still writes features but does not replace a prior
overlapping qid. Speaker column0 is used even where the source has two columns.
Population firing rates are averaged before centered three-bin smoothing;
per-unit rates are smoothed independently, with zero endpoints. There is no
z-scoring despite the original `normalize_mean` filenames.

The preparation-only CLI reads complete source inputs and writes a bounded
receipt with their identities and prepared-response digests. It fits no model:

```sh
python3 workflow.py --data-archive /operator/data_processed.zip \
  --dnn-archive /operator/DNN.zip --transcription-archive /operator/transcription.zip \
  --logical-read-limit 2300000000 --working-limit 1073741824 \
  --output-limit 4194304 --output /operator/new-preparation
```

Those paths are examples. An actual run requires separately admitted original
payloads and finite resource allocation. The conservative source array working
estimate is four times the complete session's numeric member bytes plus64MiB;
it is not a measured peak-RSS guarantee. Input authentication reads and expanded
member reads are charged, including EOF probes. ZIP seek/decompression internals
are not claimed as exact physical disk I/O.

## Prediction and original result route

`prediction.iter_jobs` yields all4209 field/layer/lag jobs per session. Negative
lags shift neural responses; positive lags shift embeddings and qids, retaining
the source's zero-qid boundary rows and unshifted speaker mask. The source
time-shuffle resets legacy NumPy seed20 after smoothing. Sentence-swap uses
Python seed20, sorted-qid groups and same-length choices with replacement;
it is not a permutation. Only word2vec and sem_syn apply the first-PC NaN
exclusion, preserving the corresponding CSV subset. The random-token,
sentence-swap and five context-length controls use−1000ms; lexical controls use
−300,−200,−100ms.

`predict_job` gives an operator-supplied callable `(train_x, train_y, query_x,
context)` one held-qid fold at a time. Query targets are absent from that call.
Complete predictions are reassembled in original time-row order and evaluated
with the authors' pooled `np.corrcoef`, preserving undefined NaN correlations.
Foldwise correlation averaging and missing-prediction substitution are refused.
This in-process API is **not a candidate sandbox** or proof of hidden-target
custody. Separate participant execution controls are still necessary.

`source_ridge_predictor()` explicitly constructs the original
`Ridge(alpha=0.01)` adapter, using default intercept/solver. It refuses numerical
libraries other than NumPy1.24.3, scikit-learn1.2.2 and SciPy1.10.1. No fitting
occurs at import or during preparation. The authors' broader environment also
records Python3.11.3/pandas2.0.1; no historical end-to-end parity run is claimed.

`workflow.produce_panel(reader, predictor, output, max_requests=...)` connects
all14 sessions to all224 literal original NPY filenames and passes the full panel
to the hash-pinned existing reducer. Request counts and output bytes require
explicit caller allocations. It binds each source input, support sequence,
target and prediction product through an ordered digest trace. The default sink
does not retain raw predictions; an independently auditable campaign still needs
budgeted prediction retention and externally authenticated execution. The lower
level `compute_session(..., sink=...)` exposes every full observation product for
that purpose. A failed campaign may leave exclusive partial output files, but
the final result receipt is written only after the complete panel succeeds.

## Population weights and scientific scope

Figure3e weights are each original `self_FR_aligned2word.npy` first-axis count,
divided by their sum. The producer verifies the numeric `(neuron,word,80)` header,
word-count join and entire member extent/CRC/SHA without interpreting its values.
It does not substitute the567 `fr_matrix` columns. `summarize_with_weights` adds
the weighted40×33 map and its own maximum-normalized map, leaving Figure3b's
fixed zero-based layer5/time17–19 and equal14-session mean unchanged.

The579 selectivity rows,567 continuous firing-rate columns and native word-aligned
counts remain separately identified. Matching counts cannot authenticate unit
identity. Figure3f's `trans_ind` join remains unresolved and is not newly made a
primary gate. There is no invented reproduction tolerance, improvement margin,
best-time search or claim that a larger source effect establishes improvement.

## Construction controls and limits

```sh
python3 -I -B test_original_inputs.py -v
```

The28 generated controls exercise source alignment, sentinel overlap, source
shuffles, complete4209-job construction and a real deterministic-callback
prediction pass, numeric/member/resource refusals, native population-weight
distinction, and all224 output files through the existing reader. The full14
session writer test substitutes generated per-session correlation arrays; it is
not14 scientific fits. No estimator is trained and no original source data is
scored by these controls. Initial fixture failures are preserved externally.

Remaining gates include complete authentic source intake/preparation, historical
reference execution, protected candidate custody and retained predictions,
source-result/identity reconciliation, and scientific comparison acceptance.
This component does not establish reproduction, improvement or a finished
benchmark by itself.
