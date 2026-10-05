# Drifting-grating selectivity in one Allen two-photon field

Estimate the fraction of released cell/ROI traces whose two-point orientation
selectivity index (OSI) or direction selectivity index (DSI) exceeds 0.5. Use
Allen experiment **501271265**, VISp, `three_session_A`. Choose and declare either
`same_trials` or `repeated_split_mean_ratio`; both are valid task answers.

This is a **single-field descriptive method case**, not the responsive-neuron
population result in [de Vries et al. (2020), Figure 3 and Response metrics
methods](https://doi.org/10.1038/s41593-019-0550-9). That analysis uses detected
calcium events and a responsiveness criterion. Here the input is released dF/F,
the denominator is every source cell, and the split analysis is a custom
sensitivity endpoint. Neither method establishes unbiased biological prevalence;
their difference does not identify the amount of selection bias.

## Offline source

The original released session is `/app/source/501271265.nwb`; its size, SHA256,
lineage and terms are in `/app/source/source_manifest.json`. Do not download data.
This is processed dF/F, not raw microscope movies. Upstream motion correction,
segmentation and fluorescence processing are outside the task. Eye tracking was
flagged failed. The legacy dF/F dataset has `unit="frame"`; use its documented
DfOverF meaning without rescaling, rather than interpreting the response as a
frame count.

Read the documented NWB paths with h5py or an equivalent reader:

- `/processing/brain_observatory_pipeline/DfOverF/imaging_plane_1/data` and
  `timestamps` (cells × frames, paired with the stored cell order).
- `/processing/brain_observatory_pipeline/ImageSegmentation/cell_specimen_ids`
  and `roi_ids`. Do not sort identifiers independently of trace rows.
- `/stimulus/presentation/drifting_gratings_stimulus/{data,features,frame_duration}`.
  Read feature names instead of assuming column positions.

The source contains 215 cells and 628 presentations, including 30 blanks.
The nonblank grid is eight directions and temporal frequencies 1, 2, 4, 8, 15 Hz.
Two conditions have 14 rather than 15 presentations; do not invent missing trials.

## Public numerical contract

`/app/method_contract.json` specifies the full method, required output columns,
status vocabulary and numerical tolerances. The principal rules are:

1. Retain each presentation's original NWB row index as `source_row_id`. Assign
   zero-based `trial_index` after sorting by `(start,end,source_row_id)`. Retain
   blanks in the presentation and response receipts; exclude them from tuning.
   A blank has positive `blank_sweep` or missing direction/frequency.
2. Compute each cell's mean dF/F using float64 accumulation over the explicit
   custom **half-open `[start,end)`** frame slice. Reject invalid bounds or
   nonfinite values; do not repair intervals, subtract another baseline, rectify,
   clip or smooth. This is not the SDK's trial-normalized corrected-fluorescence
   response or its fixed 60-frame window.
3. Average trial responses equally within each nonblank direction/frequency
   condition. Choose the largest selection-set mean; exact ties choose lowest
   direction, then lowest frequency. Missing conditions are not zero responses.
4. At that selected temporal frequency, take the measurement-set responses at
   the preferred direction, its two orthogonal directions and its opposite:
   `R_orth=(R_pref+90 + R_pref-90)/2`, `R_null=R_pref+180`, with angles modulo 360.
   Calculate `OSI=(R_pref-R_orth)/(R_pref+R_orth)` and
   `DSI=(R_pref-R_null)/(R_pref+R_null)`.
5. Preserve signed responses and all finite ratios, including values outside
   [-1,1]. Exactly zero denominator or missing requisite support makes that
   metric explicitly undefined. Do not use an epsilon cutoff or replace missing
   values with zero. Small denominators may make estimates unstable.

For **same_trials**, use all nonblank trials for both selection and measurement;
report one estimate per cell (`replicate=0`, `all` → `all`). Selection and
measurement reuse the same observations, so describe it as an in-sample index.

For **repeated_split_mean_ratio**, initialize `numpy.random.default_rng(0)` once.
Make 50 consecutive `rng.random(628)<0.5` masks over all chronological rows,
**including blanks**. A is the mask and B its complement. In replicate 1–50,
select on A and measure on B, then select on B and measure on A. Average each
cell's defined OSI ratios and its defined DSI ratios separately over these 100
estimates. Report both valid-count denominators. This removes direct selection
trial reuse but does not make the ratio/threshold estimator unbiased.

For either method, apply `OSI>0.5 OR DSI>0.5` **once to the final cell metrics**.
Divide the number flagged by all 215 source cells, including cells with no valid
ratios. Report undefined counts separately; not flagged does not mean biologically
untuned. For the split method also report the mean and population SD (`ddof=0`)
of the 50 paired-direction fractions as separate descriptive quantities. They
are not the primary endpoint, independent replication or a confidence interval.

## Outputs

Write eight files to `${OUTPUT_DIR}` (default `/app/output`). Exact column/JSON
field names are published in `method_contract.json`; row and column order are
flexible, but source-key coverage must be complete and unique.

- `presentations.csv`: all source presentation IDs, chronological indices, bounds,
  directions/frequencies, blank flags and tuning membership.
- `trial_responses.csv`: every cell × every presentation, including blanks.
- `condition_means.csv`: every cell × all 40 nonblank conditions, with trial counts.
- `estimates.csv`: every cell's chosen condition, selection mean and count,
  requisite measurement counts/responses, ratio denominators, indices and statuses.
- `per_neuron.csv`: all cell/ROI identities, final indices, valid-estimate counts,
  undefined statuses and threshold flags.
- `results.json`: declared method, numerator, all-cell denominator, fraction and
  defined/undefined counts; separate split summaries when applicable.
- `run_metadata.json`: source/manifest/contract hashes, source counts and identity,
  declared method, complete method contract and software versions.
- `findings.md`: a short account of the measured result and its limitations.

Metadata field types and values are part of the public contract:

- `status` is the string `"ok"` for a successful complete analysis; `task_id` is
  `"ALLEN2P-001"`. `method` is one of the two published method strings and must
  match `results.json`.
- `source_manifest_sha256`, `source_nwb_sha256`, and `method_contract_sha256`
  are SHA-256 strings for the supplied manifest, original NWB, and unchanged
  method-contract file respectively. `source_sha256` may be either that same
  NWB digest string or the exact one-entry object
  `{"501271265.nwb": "<NWB SHA-256>"}`. These encodings mean the same single
  source; wrong filenames, extra sources, or conflicting hash values fail.
- `ophys_experiment_id` is the source integer ID; `targeted_structure` and
  `session_type` are the original source strings. All `n_*` fields are exact
  integer source/support counts, not booleans. `directions_deg` and
  `temporal_frequencies_hz` are ascending arrays of the source numeric values.
- `method_contract` is the complete supplied JSON object, with its nested
  settings and types unchanged and no invented settings. `software_versions`
  is a nonempty object mapping software names to nonempty version strings for
  the actual implementation; an alternative implementation's versions need
  not match the oracle stack. Extra top-level metadata fields are permitted.

Keep sufficient numeric precision. Undefined CSV numeric cells must be empty;
undefined JSON numbers must be `null`, never NaN/Infinity. Count/status/identity
checks are exact; numeric tolerances are public. Scoring checks original-data
lineage and arithmetic, not particular words, rank similarity, a preferred
fraction range, or which method gives the lower answer. Reward is binary: all
verifier checks must pass; no proportional-scoring promise.

If source identity, bounds, support or finite-response preconditions fail, exit
nonzero and write parseable `results.json` and `run_metadata.json` with
`status="failed_precondition"` and a nonempty `reason`, plus `findings.md`.
