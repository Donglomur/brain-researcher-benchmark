# Original ephys row scorer

This additive owner component computes the source paper's full **13 sessions × 3 source contexts × 3 test contexts** circular time-error table from complete prediction rows. It fills the gap between fresh native decoder outputs and the existing table-only Figure 6f summarizer. It preserves the original within-session trial folds and source session identities. It does not apply the historical leave-one-mouse-out split or mouse-macro loss.

The current task remains source-unresolved. No authentic recording, native feature preparation, author LDA run or candidate run was performed for this component. It provides executable scoring and generated software controls, not a qualified benchmark or a paper-improvement result. The existing `initial-evaluator-v1` and canonical definitions are preserved.

## What is scored

The pinned source producer constructs `Y` with index `trial, type, result, time_bin`; its source-order unique trials are divided into ten contiguous `np.array_split` folds. For each split, the three source-context decoders predict every test row. The consumer converts bin indices to seconds with a factor of 0.5 and minimizes squared distance to true time and its ±20-second images.

This component retains every prediction row and averages its error within each session, source context and test context. It then calculates the mean of the three diagonal cells, the mean of the six off-diagonal cells, and their signed/absolute difference per session. The diagonal/off-diagonal reduction equally weights context pairs after the row averages; it does not pool differently sized contexts or equally weight trial means. If a native trial has multiple recorded result groups, all their original rows contribute. No result group is silently discarded.

The original producer also emits `all`, its decoder trained on all contexts. Complete optional `all` columns are accepted as separate diagnostics and excluded from the 117-cell endpoint. A complete three-context prediction is sufficient for this component. Missing source-context predictions, extra contexts, duplicate/missing rows, changed source fold identities, float/boolean classes, and partial `all` columns refuse. Query folds may lack some test contexts; training folds must support all three requested decoders. Fewer than ten trials or missing 40-bin source groups refuse rather than fabricate support.

Figure 6f's between/within biological gap is retained as a diagnostic. The scorer does not treat this gap, the published group t/P value, or a lower aggregate across-context loss as a paper-win rule. The output's primary object is the complete original error vector. `compare` reports all 117 baseline-minus-candidate cells without a scalar threshold, sign test or claimed significance. A positive cell denotes a lower candidate error for that cell.

## Owner interface

Python 3.10+ standard library suffices for scoring. `export_index_rows(native_index)` and `export_prediction_rows(native_frame)` accept native pandas-compatible objects but import no scientific packages. They export objects already produced by a separately approved source preparation/run; they do not load HDF/pickle files, prepare neural features or fit models.

`owner-index.json` must be generated from the **independently frozen native feature `Y.index`**, never reconstructed from the candidate's submitted prediction rows:

```json
{
  "schema": "structured-original-index/v1",
  "source_commit": "8c62c1cfe91644e3030a35d3ebb45e3bee94c3c8",
  "evidence_kind": "owner_source_index",
  "sessions": [
    {
      "session_id": "M2_2202025_g0",
      "feature_sha256": "<SHA256 of the frozen native feature artifact>",
      "rows": [
        {"trial": 42, "type": "LS", "result": "correct", "time_bin": 0}
      ]
    }
  ]
}
```

This abbreviated example is not admissible: all thirteen sessions and every original index row are required. Preserve the full native row order; the first occurrence of each trial defines the original fold ordering. `evidence_kind` is `generated_engineering_control` for generated fixtures and `owner_source_index` for an operator export. The latter is a provenance claim requiring independent evidence, not an authentication result. A feature SHA256 binds bytes without proving their source or inclusion policy. Source numeric trial/result identifiers can be finite JSON numbers; strings are also preserved. Nonfinite identifiers and missing values refuse.

`predictions.json` has schema `structured-original-predictions/v1`, the canonical `digest(owner_index)` as `owner_index_sha256`, a `run_receipt_sha256`, and all thirteen sessions. Each session has `session_id` and `rows`; each row contains the same four index fields plus its original integer `split` and `predictions`, a mapping of `LS`, `SL`, `SS` to integer bins `0..39`, optionally also `all`. Prediction row order may change; coverage and identity must not. The run receipt is an external provenance binding, not proof of fresh LDA execution, training-data isolation or resource compliance.

```sh
python3 scorer.py owner-index.json predictions.json score.json
python3 scorer.py owner-index.json candidate.json comparison.json --baseline fresh-author.json
```

All three JSON inputs, exported rows and results are trusted-owner artifacts containing target identities and must remain outside Git and participant access. Output creation is exclusive and mode `0600`. This CLI is not a candidate sandbox. JSON parsing rejects duplicate keys and nonfinite constants. `context_pair_mse_seconds2` has the session/source/test mapping expected by the previous evaluator's `summarize_reproduction`; its separate authenticated roster and SciPy requirements still apply if that diagnostic is used.

## Evidence and limits

The [provenance record](provenance.json) pins the inspected producer, consumer, paper text and current contract. No source file or authentic input is redistributed. Producer and consumer were inspected from pre-existing local caches; no download or installation was performed.

The feature index cannot establish behavior-trial completeness: an all-unit-zero-event trial can disappear before native `Y` construction. Authentic behavior/unit joins, inclusion/exclusion accounting, original trial order and all thirteen recordings still require admission. A maliciously reconstructed or truncated owner index is not made authentic by rehashing it. Independently freeze and authenticate the source index before receiving candidate predictions.

Native pandas/SciPy/sklearn preparation and LDA parity, fresh original error baselines, file-scoped rights, paper-only 1-second versus ephys 0.5-second method interpretation, actual training-access enforcement, mouse-level uncertainty and a justified original-score improvement decision rule remain unresolved. This component uses the explicitly pinned ephys code's 0.5-second route. It does not establish comprehension from the paper alone. The Figure 6h caption's six-session confusion-matrix example is not substituted for the thirteen-session Figure 6f panel.

Tests under `tests/` are generated controls: exact circular loss over all 1,600 bin pairs; the complete 117-cell reduction; unequal context and result-group row counts; original source-order folds; query-fold sparsity; optional `all` exclusion; paired full-table deltas; and missing/duplicate/mismatched data plus strict private output handling. They must be run through the project's reviewed lightweight test pool. Passing these controls establishes software behavior only.
