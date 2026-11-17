# Processed ERP input preparation

This implementation prepares the original eight processed tables for the three registered conditional REML analyses. It replaces no historical artifacts and fits no models. It has no dependency on the missing historical `authoring` directory, private numerical references, containers, network access, or third-party Python packages.

The input identities, complete schema, model formulas, and expected cohort are read from the adjacent [public contract](../registered-runtime/public_contract.json). That contract pins the author repository at revision `4f5767df1516e0ec3c234d51ba36e4b741eb60e8`. The original study and analysis are available from the [paper](https://www.nature.com/articles/s41467-025-63135-5) and [author RMarkdown](https://github.com/jpheffne/2025_epe_eeg/blob/4f5767df1516e0ec3c234d51ba36e4b741eb60e8/analysis/eeg_epe_ms.Rmd).

After obtaining the complete, exact pinned public input files under an approved source-preparation protocol:

```sh
python3 prepare.py --source-dir /external/author/data/clean --output-dir /external/fresh-prepared-erp
```

The command authenticates each of the eight files against the contract's byte counts and SHA-256 hashes before parsing that file. It appends ERP columns to behavior by source row order, assigns the original one-based `source_row` before exclusions, and checks uniqueness of `(sub, trialGlobal)`. It applies the missing-valence-PE filter, then complete cases independently over every variable in each model's fixed and random effects. Retained numeric values must be finite. Scaled values are copied as their original CSV strings; the command neither rescales them nor changes categorical participant values.

The frozen contract expects 7,380 source rows from 41 participants and 6,403 retained rows per model. `FRN.csv`, `P3a.csv`, and `P3b.csv` each contain the identities and that model's required columns. The receipt records per-model exclusions, ordered identity hashes, source and output hashes, and the precise formulas. It contains no participant rows, numerical estimates, or absolute paths. The output directory must be fresh and outside both the repository and source directory.

These identity checks protect source order from accidental sorting or file substitution. They cannot establish independent ERP-to-behavior correspondence: the author's ERP CSVs lack trial keys, and the positional linkage remains assumed. The command does not regenerate ERP amplitudes from continuous EEG.

Generated controls exercise row-order tampering, model-specific missingness including a random-effect covariate, first-filter precedence, nonfinite retained values, duplicate/missing behavioral identities, truncated/ragged tables, cohort loss, formula changes, output preservation, and source-directory protection. Run `test_prepare.py` through the project test pool. These checks are software evidence; no authentic inputs have been prepared by this implementation and no author model has been refitted.

Reproduction is a first-class outcome, but this is one preparation component, not a complete reproduced finding or paired participant experiment. The original coefficient/contrast estimands have no monotone “better” direction. Matching coefficients, achieving stronger significance, or creating a new held-out choice-prediction split does not establish improvement on this registered endpoint.
