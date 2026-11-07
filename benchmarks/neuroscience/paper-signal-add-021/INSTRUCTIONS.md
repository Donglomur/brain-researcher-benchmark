# Reconstruct the processed-table behavioral result

Reconstruct the participant-level initial-error summaries for *Perturbing human V1 degrades the fidelity of visual working memory* from the exact released `behavioralData_allsubs.csv`. This is the bounded behavioral numerical component of **PAPER-paper-signal-add-021**. Do not infer completion of the raw gaze, EEG or whole-paper analyses.

Use only the files declared by `public_assets.json`. The table remains at its existing local path; no waveform or dataset copy is required. The public [paper](https://doi.org/10.1038/s41467-025-57882-8) supplies context. The machine-readable [PUBLIC_CONTRACT.json](PUBLIC_CONTRACT.json) defines all identities, masks, field names and equations.

Write one UTF-8 JSON file of at most 200,000 bytes containing:

1. All 135 participant-condition means and trial counts: 15 fixed participants × seven plotting cells plus two split No-TMS controls.
2. Nine equal-participant group means, sample SDs and SEs.
3. Five explicitly paired spatial comparisons, with conventional paired t, signed d_z, two-sided Student-t p and unadjusted 95% intervals.
4. Six separately named timing/provenance comparisons. Keep these distinct from the five spatial comparisons.

Use all declared processed observations without new filtering, imputation or participant exclusion. Within each participant, pool No-TMS observations for the plotting cell, but use location-matched No-TMS for the two declared spatial comparisons. Across participants, assign equal weights regardless of trial count. Source day codes distinguish the conditions; they do not independently prove actual chronological visit order.

Order may vary, but identities must be complete and unique. All numeric values must be finite JSON scalars; no strings, Boolean numbers, NaN or infinity. Explicit zero difference variance requires null t/d_z/p/interval with the declared undefined status. Do not replace undefined inference with zero p-values.

The scorer returns continuous cell-mean error and separate count, aggregation, contrast and consistency errors. Lower numeric error is better. There is no scientific-success threshold or reward for larger effects or smaller p-values. Correct cell means with incorrect uncertainty remain distinguishable; an internally consistent null result remains a valid, potentially inaccurate submission.

This contract uses a disclosed conventional paired-t/d_z reconstruction. Historical permutation p-values and the unresolved published d convention are not exact targets. A discrepancy should not be concealed by substituting paper numbers. No code style, author implementation, source function, image pixel match or bitwise floating-point equality is required.

Only the submitted JSON is scored; this interface does not execute your program or prove that you used the input data. Do not access operator reference files, result reports, qualification fixtures or other task data. This local package has workspace/runtime dependencies and is not a rights-cleared portable release.
