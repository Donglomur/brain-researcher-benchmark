# Original ERP companion design preparation

This component adds the eight unconditional ERP analyses and three ERP-choice round parameterizations missing from the adjacent conditional-only preparer. It prepares inputs and matrices; it fits no model and produces no scientific score. The task's improvement-ineligible status is unchanged.

The [version-pinned author analysis](https://github.com/jpheffne/2025_epe_eeg/blob/4f5767df1516e0ec3c234d51ba36e4b741eb60e8/analysis/eeg_epe_ms.Rmd) defines three PE-specific FRN models, three P3a models and two P3b models. There is no P3b arousal-only model. Each retains its own baseline/nuisance variables and participant random-effects structure. The ERP-choice model has four ERP-by-round interactions, with original rounds and the two source recenterings at rounds 1 and 5.

After separate admission of authentic input preparation:

```sh
python3 prepare.py --source-dir /external/author/data/clean --output-dir /external/fresh-erp-companions
```

The command authenticates the unchanged neighboring helper and public input contract, then reuses their exact eight-table authentication and original positional join. It requires the complete 41-person, 180-trial source panel. Every model independently applies the source first valence-missingness filter and complete cases over all required variables. It does not reuse the conditional models' 6,403-row mask for the unconditional or choice analyses. Unknown authentic retained counts are recorded only after a run.

Each model emits original source strings and behavioral identities, a fixed-effect matrix, and a within-participant random-coefficient block. The latter is not a fully expanded sparse random-effects matrix: `sub` supplies the group key. Choice recentering affects the design columns while leaving the saved original rows unchanged. Source order and output hashes are recorded in a receipt. No trial sorting, pooling, imputation, scaling, invented P3b model, cohort subset or predictive split is introduced.

The receipt also records `participant_support` for every model and every original
participant, including a participant with zero retained rows. Each entry gives
the source-row count and three disjoint lists of original one-based source rows:
excluded by the first valence-missingness filter, excluded by that model's
complete-case rule after the first filter, and retained. Together they cover the
complete source panel. These lists expose participant-dependent exclusions that
aggregate retained counts and retained-only CSVs cannot show directly. They do
not change a model's mask, force a participant with no usable rows into a fit, or
establish independent ERP-to-behavior trial linkage. The existing `participants`
field continues to count participants with at least one retained row; it is not
the length of the complete `participant_support` audit.

The official source was inspected through the browser at its immutable revision; this package does not claim a newly authenticated raw author-code body. Actual R model-frame/design parity, source package defaults, convergence and fitted outputs still need independent verification. Positional ERP-to-behavior linkage remains an assumption; this does not reconstruct continuous EEG or establish complete paper reproduction. Conditional models and both contrast inference conventions remain separate. Larger coefficients, smaller p-values and better reconstruction error are not same-task performance improvements.

`test_prepare.py` exercises generated support/missingness cases, complete per-participant source-row partitions including zero-retained participants, asymmetric random-effect designs, recentering invariance, invalid identities/coding, derived overflow and complete output identity. Run it through the existing project test pool. No authentic source table or model was run during construction.
