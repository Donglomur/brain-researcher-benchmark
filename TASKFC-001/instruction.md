# Canonical-response sensitivity of task-state connectivity

Quantify how adding canonical task-response regressors changes whole-run
functional connectivity between two fixed occipital regions in the ten-person
language-localizer demo. Report both estimates and their signed within-person
Fisher-z difference. An increase, decrease or negligible change is a valid result.

This is a paper-derived **method-sensitivity exercise**, not a reproduction of
Cole et al. (2019), [Methods 2.7 and Figure 4](https://doi.org/10.1016/j.neuroimage.2018.12.054).
That paper motivates checking task-response confounding; its simulated ground
truth, flexible-response correction, condition-specific analysis and empirical
cohort are not implemented here. Neither of our two estimates identifies true,
intrinsic or causal coupling, and their difference does not prove that task
confounding has been removed.

## Inputs and public contract

All inputs are already available offline at `/app/data/taskfc`. Use exactly
`sub-01` through `sub-10`, one released preprocessed run per person, all 229
frames. The checksum-pinned release contains their BOLD, original events,
six-column motion tables, sidecars and provenance. Do not fetch replacements,
impute missing source data or execute the archive's inert `access_data.py`.

Read these public specifications before implementing the analysis:

- `/app/source_manifest.json`: exact original paths, identities and provenance.
- `/app/method_contract.json`: spatial, temporal, numerical and inferential rules.
- `/app/output_schema.json`: complete artifact keys, types, tolerances and limits.
- `/app/SOURCE_NOTICE.md`: attribution, release lineage and source-notice caveats.

The computational contract is explicit, not a hidden estimator challenge:

1. Extract float64 means from native-grid voxel centers within 8 mm of
   `(-30,-90,-6)` and `(30,-90,-6)`, named `L_lateral_occipital` and
   `R_lateral_occipital`. Use the original selected affine in millimeters,
   squared distance `<=64`, no mask, smoothing, resampling or nearest-voxel rescue.
2. Use every frame with operational time `1.5*frame_index+0.75` seconds.
   Headers and sidecars establish TR=1.5 s. The half-TR origin is a declared
   computational convention, not verified acquisition/slice-time alignment.
3. Fit two nested whole-run models. `nuisance_only` contains an intercept,
   six cosine drift columns at the specified 0.01-Hz cutoff and all six motion
   columns in order `X,Y,Z,RotX,RotY,RotZ`. `glover_task_residual` adds separate
   `language` and `string` Glover-HRF columns from every original event. Use the
   public HRF discretization (oversampling 50, minimum onset -24 s), not FIR,
   derivatives, extra filtering, whitening or singular-value regularization.
4. Use the public rank-aware SVD projection and numerical activity rule.
   Rank deficiency and inactive residuals are legitimate outcomes. Preserve
   all people and finite primitive arrays; use the prescribed null/status
   representation when a correlation is undefined.
5. For each model, compute signed Pearson correlations and equal-person
   Fisher-z group means. Clip only the Fisher transform input to +/-0.999.
   Report the signed paired change `z_nuisance-z_glover`, its sample SD,
   standard error, two-sided paired-t summary and 95% t interval. With zero
   standard error, report a point interval and null t/p. A group quantity
   requires complete support from all ten people; do not silently average a
   reduced cohort.

Equivalent implementations are welcome within the public numerical tolerances.
The verifier reconstructs raw means, designs and residual support from the
original sources. Submitted raw/design arrays are receipts, not inputs for
refitting rounded designs. Accepted source-bound residuals are the single
downstream basis for all correlations and group arithmetic; rounded CSV/JSON
scalars are not fed into another estimator. No expected effect, sign, ordering,
significance, cross-person variability or prose keyword is a grading condition.

## Deliverables

Write these seven files to `${OUTPUT_DIR}` (default `/app/output`):

- `cohort.csv`: ten literal participant/run identities, frame counts, clocks
  and source-derived sphere support counts/digests.
- `events.csv`: all 240 original rows with source indices, original tokens
  and interpreted onset/duration/modulation; do not deduplicate this ledger.
- `model_arrays.npz`: complete keyed frame, participant, ROI, model and design
  axes; raw ROI means, design receipts, model inclusion masks and both residuals.
- `connectivity.csv`: both signed person-level estimates, Fisher transforms,
  paired changes and explicit support statuses.
- `connectivity_summary.json`: complete-cohort model means and paired inference.
- `run_metadata.json`: source/contract hashes, original headers/columns,
  operational clock, canonical rank/support diagnostics and actual software.
- `findings.md`: a short interpretation of the measured sensitivity and its
  limitations. Do not claim this establishes true coupling or replicates the
  paper's result.

The schema specifies the exact fields. Coherent row/axis permutations, declared
rounding and harmless bounded extra fields are allowed. Literal identities must
not be digit-normalized; all required counts/keys/statuses must be correct.
No pickle/object arrays, NaN/Infinity placeholders or omitted undefined people.

## Completion and failures

Reward is binary: 1 only when the complete source-bound submission passes the
declared checks, otherwise 0. There is no proportional/partial-result scoring.

Use a fresh output directory or preserve existing outputs. If an input or
computation precondition fails, exit nonzero and write a nonempty
`failure_report.json` with status `failed_precondition` and a factual reason.
Any such marker overrides otherwise complete or stale success files. Do not
fabricate successful measurements, overwrite protected inputs or hide a failure
by dropping a person. Authoring pilots are not completed benchmark submissions.
