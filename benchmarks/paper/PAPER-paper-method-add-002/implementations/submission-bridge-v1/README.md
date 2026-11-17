# Native result submission and paired numerical comparison

This adapter closes the transport gap between `source-producer-v1.source_result_family` and the existing source endpoint evaluator. A submitted analysis exports granular predictions and native component arrays. The operator freezes that packet, recomputes every metric against its own prepared targets, and compares it with a separately frozen reference packet. Submitted scores and target arrays are discarded.

This is source construction, with generated controls only. The previously prepared original bank contains all 511 trials, 182 neurons and 150 bins. No authentic model, decoder, candidate or scoring run was performed for this adapter. Neither reference provenance nor successful reproduction/improvement follows from the existence of a packet.

## Required inputs and preserved routes

The operator plan binds the prepared-bank manifest, an externally frozen evaluation profile, the explicit `source_code_ridge1` or `paper_ols0` recipe, component routes and any authenticated reconstruction-cell roster. Its exact fields are validated by `validate_plan`. An evaluation-profile hash is a join key: the operator still must supply and enforce the actual information-access, fitting and resource protocol. A candidate-declared hash is not proof of compliance.

Each full packet requires:

- Eight single-trial model/partial routes, each with complete straight and curved predictions and test indices: raw, trial NMF12, neuron NMF12, mixed trial-only, CP/TCA12, LFADS, mixed full and mixed time-only. The canonical mixed finding uses trial-only, never the full or time-only companion. LFADS cannot be silently omitted.
- The separate raw condition-average control, with all 20 repeats, both orientations, actual angle labels and complete training/testing row indices. This is not the five-fold route.
- Supplied mixed component vectors/slices, peak and condition ordering, source-index-group correlations, target projections, and preparatory subspace coordinates/axes/classes. Arrays retain their supplied order and scale; the adapter performs no gauge transformation or matching.
- One full `[511,182,150]` reconstruction prediction for every externally frozen cell, with source result/rank/seed, training-mask digest and trim setting in the plan. Empty reconstruction cells explicitly mean that the original roster remains unresolved. They do not make the full paper panel complete.

The 14 canonical decoding summaries and four mixed companion summaries remain separate. Reconstruction RMSE and MSE remain separate from decoding. No grand score or new component metric is introduced.

Single-trial positions have shape `[20,5,80,53,2]` for straight reaches and `[20,5,80,49,2]` for curved reaches. The source schedule is preserved, including the curved training-only remainder. R² uses the original within-trial temporal centering and preserves negative values. Zero-variance targets are rejected. Source bin ranges remain neural `55:-15`, movement `65:-5`; displacement targets are per-bin changes without physical-time scaling.

Condition averages use the inherited source RNG state and cumulative two-half permutations. Straight halves have 132 training and 133 test trials; the middle trial is tested in both orientations and trained in neither. Curved halves are 123/123. The operator derives condition membership, group counts, target means and true initial positions from its own bank. Every source label must occur in each half. With 12 labels, each stratum has 480 condition scores, distinct from the 5,300/4,900 single-trial occurrences.

The source ridge alpha1 and paper-described OLS alpha0 remain distinct plans. Source92/90 index regions versus paper90/92 counts, source indices versus paper physical windows, source target-projection route versus paper cross-validation, and default LDA axes versus paper orthogonalization remain unresolved source distinctions. The source target projection route is in-sample; its name does not authenticate the paper's target-projection analysis.

## Export and compare

The Python API consumes the actual dictionary returned by the existing producer. It does not execute an analysis callback:

```python
receipt = bridge.write_packet(
    family, fresh_private_packet,
    plan=frozen_operator_plan,
    declaration=analysis_declaration,
    reconstruction_predictions=predictions_by_frozen_cell_id,
)
```

Declarations distinguish `operator_reference` from `submission`, and historical published outputs from fresh source calibration, unqualified reference, or candidate. Candidate access is explicitly `paper_data` or `paper_data_author_code`. Code/config hashes and the reference identity remain declarations requiring external authentication. A fresh source calibration is not relabelled as a historical paper score.

`Packet(path, expected_manifest_sha256, plan)` binds the complete payload census, exact array shapes/dtypes and file hashes. Arrays are numeric NPY files in bounded gzip envelopes; objects, extra files, aliases, symlinks, changed payloads and differing schedules are refused. `get` hashes the exact compressed byte buffer it parses, so replacement after packet admission does not bypass the content pin. This is artifact validation, not a sandbox for candidate execution.

After separately admitted fitting and operator freezing, the comparison CLI is:

```sh
python bridge.py \
  --plan OPERATOR_PLAN.json --bank PRIVATE_PREPARED_BANK \
  --reference PRIVATE_REFERENCE_PACKET --reference-sha256 FROZEN_REFERENCE_MANIFEST_SHA256 \
  --candidate PRIVATE_CANDIDATE_PACKET --candidate-sha256 FROZEN_CANDIDATE_MANIFEST_SHA256 \
  --mask-directory PRIVATE_FROZEN_MASKS \
  --summary NEW_SUMMARY.json --private-details NEW_DETAILS.npz
```

The mask directory contains exactly `CELL_ID.npy` for each plan cell. Masks are operator inputs checked against a shape-aware binary content digest; the adapter never generates, repairs or selects a mask. Omit `--mask-directory` only when the plan explicitly has no authenticated reconstruction cells. The original bank and masks must remain operator-private and immutable during comparison. The authenticated prepared-bank manifest for the prior admitted preparation is `752eda0d1bc094a98364f1a7445572cea0d9df7e67bb88d1f0712f69e4b76b60`.

The JSON reports per-finding signed/absolute reproduction differences and directional improvement deltas. Higher R² and lower reconstruction RMSE have explicit directions. Reproduction, improvement and joint-family decisions remain `unavailable`: no source-supported equivalence margin, meaningful effect, valid paired uncertainty rule or complete scientific comparison protocol has yet been qualified. Repeated folds are dependent, not independent animals. Positive deltas alone establish neither a paper win nor current SOTA.

Raw and raw condition-average entries retain their canonical reproduction summaries, but their comparison role is `fixed_control` and their improvement claim role is `diagnostic_only`. Under a fixed data/decoder recipe, a difference in these controls identifies unresolved computation or provenance, not a scientific gain. The adapter does not impose bitwise equality or invent a numerical equivalence margin for independent executions.

## What remains unfinished

The adapter verifies native component algebra (peaks, source condition ordering/classes, correlations from supplied slices, and coordinates from supplied axes), using a numerical floating-point check rather than a scientific matching tolerance. It does not authenticate the fitted axes, historical factor identity, nonnegative gauge equivalence, model-derived predictions, native scientific findings or honest/permitted fitting. Target-projection outputs are retained without introducing a new metric.

The producer currently does not retain decoder coefficients/fit receipts, predicted displacement traces or neural condition means. Position-level metric completeness therefore remains distinct from full computation verification. The original LFADS outputs, historical fits/seeds/gauges, original reconstruction masks/rank roster, qualified reference and complete protected paired execution remain separate missing requirements. Current code supplies an executable comparison mechanism once authentic outputs are separately available; it does not claim those outputs exist.

All source files and authentic preparation receipts from the accepted producer remain unchanged. Ordinary validation is generated-only and requires NumPy and SciPy through the pinned producer; it does not load the original dataset or an LLM.
