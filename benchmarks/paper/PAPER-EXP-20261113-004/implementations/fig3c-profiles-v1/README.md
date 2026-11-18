# Figure 3c position-profile arithmetic

This owner-side component fills the Figure 3c arithmetic gap beside the existing Figure 3b scorer. It preserves all eleven mice, seven switch days, three cell classes and both cross-switch directions: 462 condition records. It also returns the 66 first/last-switch, train-before source-export rows. These are required companions, not additional improvement targets or benchmarks.

The [pinned author notebook](https://github.com/GiocomoLab/Sosa_et_al_2024/blob/adf0f9ed3defa22275d92fa0ed996f47008e05b3/notebooks/Fig3_Decoder.md), section “Z-score decode to the shuffle distribution,” defines 44 left-inclusive/right-exclusive position intervals, within-fold cosine means, equal-fold means and 100 shuffle-repeat means. Standardization uses population shuffle SD. Empty positions remain missing; a zero denominator can yield NaN or signed infinity. Values at positive pi are excluded by the source interval convention and counted explicitly.

The [author SEM helper](https://github.com/GiocomoLab/Sosa_et_al_2024/blob/adf0f9ed3defa22275d92fa0ed996f47008e05b3/src/reward_relative/utilities.py) divides the NaN-ignoring population SD by the square root of the full mouse-axis length minus one. This component preserves that denominator even with missing mouse values. It does not replace it with a finite-count-adjusted inference rule.

## Owner input and output

The input object has exactly `schema`, `source_commit`, `preparation_sha256`, `fold_receipt_sha256`, and `rows`. The schema is `reward-relative-fig3c-input-v1`; commit and complete cohort identities are fixed in the implementation. Each condition contains `animal`, `day`, `cell_type`, `model`, ten `folds` and 100 `shuffles`, each with ten folds. A fold contains ordered `sample_ids`, `actual` and `predicted` radian arrays. JSON null denotes source NaN. Actual infinite angles, duplicate samples/conditions, changed shuffle targets, differing population support and overlapping before/after support are rejected.

Source missingness is retained in every position, fold and repeat. Output values are `{value: number, state: "finite"}` or `{value: null, state: "nan" | "positive_infinity" | "negative_infinity"}`. Occupancy, valid-prediction, fold and repeat counts remain visible. Nothing clips, rewards or silently omits undefined standardization. `profile_row` is a partial arithmetic API; only `score_panel` enforces the complete declared cohort.

```sh
python3 -B fig3c_profiles.py --panel /owner/fig3c-input.json --output /owner/fig3c-result.json
python3 -B -m unittest discover -s tests -p 'test_*.py'
```

Output creation is exclusive. Inputs, true positions, author predictions and results stay in operator custody. This is not a participant-delivery interface. Identity hashes do not authenticate source observations or execution. The CLI materializes the JSON input/output; authentic scale, memory and runtime are unmeasured. No pickle, author function, model or source-data pipeline is executed.

## Limits

Current-commit arithmetic is not historical source authentication, reference equivalence, improved decoding, biological reproduction or scientific readiness. Floating-point reduction order is not asserted bitwise equivalent to NumPy; historical/runtime numerical tolerance and missingness admission remain unresolved. Full Figure 3b inputs and controls remain independently required. Z-scores and shuffle results cannot become improvement rewards.

The notebook names `20241117-1507` as its paper-result timestamp while loading `20250405-1059` in the inspected version. This is a concrete artifact search clue, not proof that either retained result file is authentic or equivalent. No source result artifact was opened for construction.
