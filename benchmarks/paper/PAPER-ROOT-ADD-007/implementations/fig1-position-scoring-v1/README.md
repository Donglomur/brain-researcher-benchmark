# Recovered Figure 1 position scoring

This component scores frozen author and candidate predictions on the exact **recovered notebook branch**: trial-grouped direct decoding, prefix-matched cross decoding, modal-prediction-filtered RMSE, and 50 cross-arm cell-shuffle controls. Reproduction and same-task improvement are distinct first-class outcomes: outputs retain reproduction discrepancies and improvement deltas separately, with neither decision admitted yet. It does not fit a decoder, import author code, prepare native data, or establish that this saved notebook state generated the published Figure 1D.

The [source recovery and limitations](../../docs/fig1-position-source-recovery-v1.md) are part of this interface. The preceding recurrence evaluator remains unchanged. The older programme already contains a literal author-decoder caller; this component supplies an independent, strict prediction scorer without duplicating that caller.

Use an existing Python environment with NumPy:

```sh
python3 position_score.py operator-reference.json candidate.json --output scores.json
```

Keep the reference, predictions and generated scores outside Git. The CLI reads JSON only and records both input file hashes. A reference's `kind` discloses its origin; it does **not** authenticate its conversion or remove qualification holds.

The reference has exactly these top-level fields:

```json
{
  "schema_version": 1,
  "kind": "operator_prepared",
  "phase": "learned",
  "mice": {
    "478": {
      "arms": {
        "L": {"frame_ids": ["..."], "trial_groups": [0], "positions": [0.2]},
        "R": {"frame_ids": ["..."], "trial_groups": [0], "positions": [0.2]}
      },
      "author": {},
      "shuffle_ids": {}
    }
  }
}
```

This is an abbreviated shape, not an executable or complete example: **all four** filename identities `478`, `481`, `483`, `485` and at least two trial groups per arm are mandatory. `generated_control` is the other allowed kind. Every position is finite in the source normalized range [0,1]. Frame identities must be unique within each complete arm array and ordered exactly as in the native source. Trial groups are the original `trial_idx_mask` values; inventing session/trial composite labels would change the split. The operator must retain native session identities and verify pooling upstream. This scorer cannot infer native completeness from a declared packet.

Each mouse's `author` and the candidate's `mice[mouse]` map contain exactly six conditions, in the source RMSE naming convention:

| Condition | Rate-map arm | Spike and true-position arm | Assessed frames |
|---|---|---|---|
| `L` | L | L | Source 20% trial-group test set |
| `R` | R | R | Source 20% trial-group test set |
| `L from R` | R | L | First min(L length, R length) frames |
| `R from L` | L | R | First min(L length, R length) frames |
| `L from R Shuffled` | R | L | Same cross-arm prefix, 50 draws |
| `R from L Shuffled` | L | R | Same cross-arm prefix, 50 draws |

For each nonshuffled condition the value is `{"frame_ids": [...], "positions": [...]}`. IDs must equal the computed evaluation IDs in order. For each shuffled condition it is a list of **50** such records, each also containing `shuffle_id`. `shuffle_ids[condition]` in the operator reference holds exactly 50 distinct frozen draw identities, shared by author and candidate. Those IDs bind predictions to a declared paired input; authentic cell permutations and actual candidate use remain execution-provenance requirements. The source did not seed `random.sample`; do not claim recovery of its original draws from these IDs.

The candidate document is exactly `{"schema_version": 1, "access_condition": "paper_and_data", "mice": {...}}`. The other access condition is `paper_data_and_author_code`; report the two conditions separately against the same frozen reference and matched observations. This field records a declaration, not verified access provenance. No target positions, masks, source summaries or cohort declarations are accepted from the candidate. Candidate methods may change architecture; the scorer does not require copying the author decoder.

`source_split` reproduces the source `GroupShuffleSplit(n_splits=1, test_size=.2, random_state=42)` using sorted unique group labels and NumPy's legacy `RandomState`. It selects ceil(20% of groups), preserving source frame order and group membership. It does not use position values to choose test frames. The native sklearn/NumPy versions and exact trial labels still need binding for native calibration.

Each prediction vector is scored three ways:

1. `source_modal_filtered_rmse`: remove every frame whose prediction equals the most frequent prediction; modal ties choose the smallest value, matching numeric SciPy mode semantics. This is the recovered source metric. Each method can retain different frames.
2. `full_bin_rmse`: use every assessment frame. This is a separately named coverage control, not a replacement source metric.
3. `author_support_rmse`: use the author's nonmodal frames for both methods. This is a separately named paired-support diagnostic.

Every draw reports total, retained, excluded, author-retained and common-retained counts. It separately reports prediction RMSE and maximum absolute deviation from the author output for reproduction assessment. Per-mouse metric deltas record candidate minus author for improvement assessment. Neither a reproduction tolerance nor a superiority margin is invented. Constant predictions leave no source-scored frames and return JSON `null`, never zero. Undefined draws invalidate the corresponding 50-draw mean and four-mouse mean rather than being dropped. The source reduction averages 50 shuffle RMSEs within each mouse, then gives each of the four mice equal weight; population standard deviation uses `ddof=0`. All six conditions stay separate. There is no invented grand mean, frame-level confidence interval, or outcome decision.

The source cross-arm posterior keys point the opposite way from the RMSE keys. Outputs record both literal keys plus explicit map/observation arms. The implementation normalizes the old SciPy `mode` return shape; it does not reproduce an incidental scalar-indexing crash in newer SciPy.

Tests are generated software controls. They cover hand-frozen grouped splits, asymmetric arm prefixes, hand-calculated errors, a counterexample where source RMSE improves while full-frame error worsens, undefined constant predictions, six-condition/four-mouse reductions, all 50 controls, identities and malformed JSON. Follow the shared test pool protocol for execution.
