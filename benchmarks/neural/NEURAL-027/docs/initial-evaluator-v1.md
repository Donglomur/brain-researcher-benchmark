# Visual stimulus decoding across learning phases: initial evaluator

This package implements the source-frame-to-score construction path for **NEURAL-027**: trial-local position packets, an animal-disjoint pre-reward reference, a matched movement/position control, strict prediction scoring, and paired mouse uncertainty. It is a **prospective engineering reference**, not a reproduced author decoder or a scientifically admitted benchmark. Scientific qualification remains **unknown**. The canonical specification and its historical admission flags are unchanged.

## Source basis and deliberate protocol choices

The frozen task is `task.json`, SHA256 `9ce2efe878eb9bebd03cf54aebf383cf2d2a032db7f5c552decb9cacda1304a9`. The [primary paper](https://doi.org/10.1038/s41586-025-09180-y), author repository commit `ba64ac697f5d9914926baac79399e80707a5f3a6`, and [Figshare version 2](https://doi.org/10.25378/janelia.28811129.v2) establish the source interfaces. The v2 metadata describes 297 assets totaling 452,233,500,962 bytes; that is an asset inventory, not an animal count. No asset payload was downloaded or loaded for this construction.

Pinned `utils.py` establishes source `spks` chunks concatenated along neurons, behavior vectors truncated to the neural frame count, positive `ft_move` and corridor-frame selection, and the mapping from source `UniqWalls` through `stim_id`. It also establishes the anatomical groups V1 (area 8), mHV (0,1,2,9), lHV (5,6), and aHV (3,4). Canonical stimulus indices are 0 circle1, 1 circle2, 2 leaf1, 3 leaf2, 4 leaf3, 5 leaf1_swap1, 6 leaf1_swap2. Source WallID values are not those canonical indices. String wall names and finite integral numeric wall IDs are both preserved exactly; a mapping is never inferred from their spelling or order.

The author `Get_coding_direction` is a scientific figure analysis, not this prediction task. Its global cumulative-position interpolation permits extrapolation and its normalization uses all trials. This package therefore makes explicitly prospective choices:

- A predeclared normalized position grid uses **means of moving corridor frames within each individual trial**. No interpolation, extrapolation, previous-trial append, or feature normalization using query data occurs. Every retained trial must cover every declared bin; exclusions and behavior-tail truncation are reported. Bins are left-closed/right-open, except the final right edge is included.
- Position is `ft_Pos / Corridor_Length`. The notebook documents `ft_Pos`; the author interpolation explicitly divides *cumulative* position by corridor length. Same-unit, within-trial `ft_Pos` interpretation must be verified on the admitted payload; the package rejects selected positions outside [0,1]. This adapter does not claim author preprocessing equivalence.
- Four regional population means provide a declared anatomical calibration across animals. All four regions must be present and each neuron must align with its supplied `iarea` value. This avoids claiming that individual cells are registered across sessions. The biological adequacy of regional pooling for this question remains an admission decision.
- The operator freezes the stimulus subset, grid, selected sessions, all animal assignments, phase semantics, and an explicit attestation that training phases precede reward learning. Training and evaluation animals and phase labels must be disjoint. Every selected date/block preserves its original `mname`; sessions are never promoted into independent mice. Unselected sessions cannot be inferred from the provided manifest, so authentic complete-cohort verification remains held.
- Classes must be available in every retained mouse/phase, but their counts need not match. The fixed class set is the same across arms and phases. Class counts, exclusions, and future selection adequacy require scientific review; the code does not relabel missing classes or silently reduce the denominator.

The choices above are an executable proposed construction protocol. They are not historical source policies, a scientific admission criterion, or an outcome-selected best configuration.

## Input and execution

Python 3.11+ and NumPy are required; no installation is performed by this package. All input is operator-side. The Python API `construct_session` accepts decoded author `spks` chunks, per-neuron `iarea`, and the source behavior fields. The CLI accepts a non-pickled numeric/string NPZ export for each selected session, named `{mname}_{datexp}_{blk}.npz`. It requires exactly these keys:

| Key | Shape / meaning |
| --- | --- |
| `spks` | neurons × frames, concatenated calcium-derived activity; not electrode spikes |
| `iarea` | one source cortical area ID per neuron |
| `ft_WallID`, `ft_trInd`, `ft_move`, `ft_Pos`, `ft_CorrSpc` | frame vectors, each at least as long as `spks`; tails are audited |
| `Corridor_Length` | positive scalar in the same units as `ft_Pos` |
| `UniqWalls`, `stim_id` | equal-length one-to-one source-to-canonical stimulus mapping |

The original author NPY dictionaries require trusted pickle loading. This package does not deserialize them or silently authorize them; exporting and verifying the numeric bridge is an unresolved native intake step. Safe NPZ input hashes are recorded, but such hashes alone do not prove equality to original source payloads.

A plan has the following fields; values shown are **illustrative**, not a source cohort or an admitted protocol:

```json
{
  "schema_version": 1,
  "classes": [0, 2],
  "position_edges": [0.0, 0.2, 0.4, 0.6],
  "calibration": "source_anatomical_area_mean_v1",
  "pre_reward_training_attestation": true,
  "train_mice": ["train_mouse"],
  "evaluation_mice": ["evaluation_mouse"],
  "train_phases": ["before"],
  "evaluation_phases": ["reward_free_after"],
  "phase_semantics": {
    "before": "Operator-verified pre-reward source experiment",
    "reward_free_after": "Operator-verified post reward-free exposure experiment"
  },
  "sessions": [
    {"session_id": "train_mouse_date_block", "mname": "train_mouse", "datexp": "date", "blk": "block", "phase": "before"},
    {"session_id": "evaluation_mouse_date_block", "mname": "evaluation_mouse", "datexp": "date", "blk": "block", "phase": "reward_free_after"}
  ]
}
```

From the implementation directory:

```sh
python3 evaluator.py --plan /absolute/path/plan.json --session-dir /absolute/path/numeric-exports --output-dir /absolute/path/results
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

The CLI writes `report.json`, `predictions.json`, and `public_query.json`. The report is operator-private: it includes outcomes and source grouping metadata. The public query contains only opaque item IDs, four neural values, and the two matched control values (movement and position). It excludes source WallID, canonical targets, phase, animal/date/block, licking, reward, and future values. The supplied reference receives training targets only through `fit`; `predict` rejects additional query fields. This process is not an OS-level confidentiality boundary; an actual agent harness must isolate private preparation/scoring artifacts and freeze resources and access before evaluation.

## Reference and endpoints

Both arms use the same frozen diagonal-Gaussian classifier with uniform class priors. Training weights give each mouse and class equal total weight. Mean, scale, class centroids, and pooled within-class diagonal variances are fitted solely on training packets. Constant scales become 1 and standardized variances have a fixed floor of 0.1. The floor and recipe are prospective fixed choices; there is no validation or test-set tuning. Neural features are four anatomical means; the comparator uses only mean framewise movement and mean normalized position. Prediction uses a stable softmax of diagonal Gaussian scores.

For each exposure phase, the scorer averages packet log loss within each mouse and then averages those mouse means. Balanced accuracy is the mean of class recalls within each mouse, then the mean across mice. Every trial has the same bin count, so equal packet weighting also gives equal retained-trial weight within a mouse/phase. Multiple sessions of one mouse are pooled within that mouse, not given additional biological weight. No summary averages unlike phases or uses pooled-trial uncertainty.

Probability columns follow the sorted plan class order. Exact expected-ID coverage is required; duplicate/missing/extra IDs, invalid dimensions, nonfinite values, out-of-range probabilities, and row sums differing from 1 by more than 1e-8 are rejected. `argmax` ties select the first sorted class. Log loss clips true-class probabilities at 1e-15; zero-probability counts are reported. Constant probabilities are valid null predictions and explicitly flagged, not disguised as competent results.

The report gives paired neural-minus-control differences and 95% percentile intervals from 2,000 seeded bootstrap resamples of mice **within each phase**, applying the same resample to both arms. Each mouse/phase binds expected item IDs and labels by SHA256; separate arms must match these bindings, class order, and counts before comparison. A single-mouse phase is descriptive and has no population interval. These intervals are engineering outputs, not an admission threshold or evidence of calibrated coverage on this source. Cross-phase causal or independent-cohort comparisons are not inferred.

## Validation and remaining gates

Generated controls cover source stimulus remapping, neural chunk concatenation, fixed-bin boundaries, exclusion of incomplete trials without borrowing neighboring frames, behavior tails, missing regions, nonfinite values, source ID inconsistencies, population coverage, animal/phase leakage, class availability, query-label exclusion, training-only normalization, biological-unit weighting, strict probability validation, null predictions, paired bootstrap, and the safe NPZ CLI. Independent source and final code reviewers check this implementation; review results and exact final pins are maintained in the construction evidence handoff. The tests establish engineering behavior only.

The source population, authentic array alignment, position units, cross-session calibration, complete selected cohort, original/safe-export equality, trusted native extraction, rights, access/resource budget, reference competence, scientific admission criteria, protected evaluation, and independent authentic replication remain unresolved. The notebook's documented 3.17 Hz is not adopted as an exact timing guarantee; the canonical task remains frame/position aligned. Source code is GPLv3 and Figshare v2 metadata reports CC BY 4.0; this original implementation vendors no source code, and the operator must confirm applicable payload/redistribution terms. The task shares a source family with PAPER-FIND-REP-007; its packets and results do not establish a second independent cohort.
