# Movie-fMRI system segregation

Estimate system segregation for a fixed 40-person movie-fMRI sample, then
summarize the cohort and the adult-minus-child contrast. This is a
paper-derived **method adaptation**, not a reproduction of a published
developmental finding. No effect direction or significance is required.

## Sources

All inputs are already in `/app/data/netseg/`; run offline. Its
`source_manifest.json` lists exact filenames, source versions, sizes and SHA256
digests. Use the unchanged BOLD images, full confound TSVs, phenotype table and
Schaefer-2018 100-parcel/7-network atlas. Preserve source identities in your
outputs. Do not fetch another version or substitute a reduced-confound cache.

Use exactly the 31 children `sub-pixar001` through `sub-pixar031` and nine adults
`sub-pixar123` through `sub-pixar131`. Read their groups and ages from the
original `participants.tsv`. The other 115 source-table participants are outside
this fixed task, not new QC exclusions. Retain all 40 selected people, all 168
source frames per person, and all 100 atlas parcels. Do not select people,
frames or parcels to improve a result.

The resource originates from [Richardson et al. (2018)](https://doi.org/10.1038/s41467-018-03399-2),
but these later fMRIPrep/4-mm derivatives are not the paper's original analysis.
The `provenance/` directory contains the processing README and use notices.
The OSF CC-BY-4.0 declaration and Nilearn noncommercial-research notice are
both retained; this task does not settle their precedence or movie rights.

## Public estimation contract

`/app/method_contract.json` provides the exact schemas, numerical rules and
tolerances below. Equivalent mathematical implementations are acceptable.

1. Decode NIfTI scaling and compute in float64. The int8 stored codes are not
   the scaled signal. Transfer the original 1-mm atlas to each BOLD grid using
   nearest-neighbor sampling in identity world coordinates and zero background;
   do not resample BOLD. Use numeric parcel IDs and their original LUT network
   labels. Report native and transferred voxel support. This is an explicit
   FSLMNI152/NLin6-to-NLin2009c template approximation, **not** a verified
   nonlinear registration. The BOLD headers omit spatial and temporal units;
   interpret the spatial coordinates using the upstream 4-mm processing
   description, and do not interpret their temporal zoom of 1 as a measured
   one-second TR. No frequency filter is requested.
2. Average all grid voxels carrying each parcel label. Add no new mask,
   smoothing, global-signal regressor, censoring or temporal band-pass filter.
   Reject nonfinite input, absent parcels or incompatible source geometry;
   do not silently drop support or replace invalid signal with zero.
3. From each full confound TSV select, in order, `trans_x`, `trans_y`, `trans_z`,
   `rot_x`, `rot_y`, `rot_z`, `framewise_displacement`, `a_comp_cor_00` through
   `a_comp_cor_05`, `csf`, `white_matter`. All selected released values are finite.
   Reject missing/nonfinite values; no imputation or row deletion is needed.
4. Demean and remove the centered linear frame-index trend from both parcel
   signals and selected confounds. Center and population-SD standardize each
   detrended confound; an SD below float64 epsilon uses divisor 1. Remove its
   pivoted-QR column span, retaining columns whose absolute diagonal of R is
   greater than `100 * eps64`. Recenter residual signals and divide by their
   sample SD (`ddof=1`). Each residual SD must exceed
   `1e-12 * max(1, raw_parcel_sample_SD)`; otherwise report a source/numerical
   precondition failure. No silent parcel/person omission is allowed.
5. Compute Pearson correlations from the cleaned series. For each of the
   4,950 unique undirected off-diagonal parcel pairs, retain Pearson r and
   `z = arctanh(clip(r, -0.999999, 0.999999))`. The primary edge is `max(z, 0)`.
   Diagonal entries never count. The seven-network partition comes from the LUT.
6. Let W be the mean primary edge over **all** within-network pairs, and B the
   mean over **all** between-network pairs. Report `S = (W - B) / W`. Negative
   edges become zero but remain in the denominator: excluding those pairs is
   a different conditional metric. Pool pairs across networks; do not average
   network means equally. If W is exactly zero, S is undefined, represented by
   the documented null/status fields—not an epsilon floor or invented value.
7. Summarize the 40 participants and each age group. Report adult mean minus
   child mean, with standard error
   `sqrt(sample_variance_adult / 9 + sample_variance_child / 31)` and normal-Wald
   95% interval `difference ± 1.96 * SE`. If any selected participant has an
   undefined S, the affected full-group/cohort summary and any dependent
   contrast are null. Report counts; do not silently use a defined subset.

Chan et al.'s [system-segregation method](https://doi.org/10.1073/pnas.1415122111)
motivates the zero-clipped metric; the present pooled Schaefer7/movie sample
differs from the original study. Signed or negative-pair-excluded sensitivities
may be reported separately, but cannot replace the primary endpoint.

## Deliverables

Write to `${OUTPUT_DIR}` (default `/app/output`) using the field/axis schemas
in `/app/method_contract.json`:

- `participants.csv`: all exact IDs, original phenotype rows/groups/ages,
  manifest-bound BOLD/confound paths, frame/grid identities and cleaning/support
  diagnostics. Their hashes belong in the complete metadata source-hash map.
- `parcels.csv`: each parcel's original label, hemisphere/network, and native
  and transferred voxel counts on the shared grid.
- `connectivity.npz`: explicit participant/frame/parcel/edge axes; raw parcel
  means, standardized cleaned series, and complete Pearson/Fisher/positive-edge
  arrays. Use numeric or string arrays, never pickle/object arrays.
- `segregation.csv`: each participant's complete-pair counts, sums, means,
  primary segregation and status.
- `cohort_results.json`: recomputable cohort/group summaries and contrast.
- `run_metadata.json`: success status, complete source hashes, source/method
  manifest hashes, geometry/processing declarations, software versions and
  observed diagnostics. Additional honest metadata is welcome.
- `findings.md`: a concise interpretation with the convenience-sample,
  shared-movie, template-transfer and cross-sectional limitations. Its wording,
  result direction and significance are not keyword-graded.

The participant—not an edge or frame—is the independent unit. The children
span roughly 3.52–4.86 years and adults 19–39; a difference does not establish
within-person development, a lifespan trajectory, causation or clinical value.

## Numerical acceptance and failures

Source raw means are checked with `atol=1e-5, rtol=1e-7`; standardized cleaned
series with `atol=2e-6, rtol=2e-6`. These are source-bound receipts: accepted
rounded raw means are not re-cleaned as a new source signal. All downstream
quantities are recomputed from the accepted cleaned series, and checked with
`atol=1e-6, rtol=2e-6`; integer identities, counts and support are exact.
The saved Fisher/positive-z upper magnitude limit allows this same numerical
tolerance for serialization (including float32 rounding); nonnegative fields
must remain nonnegative, and all fields still face their own-derived comparison.
Coherent participant/frame/parcel/edge ordering changes are allowed. There is
no secret outcome vector, expected mean, effect sign or significance cutoff.

Scoring is binary: all required source, support and arithmetic checks must
pass for reward 1; otherwise reward 0. There is no proportional partial credit.
On a failed precondition, exit nonzero and write a nonempty explanatory
`failure_receipt.json`; it marks the attempt unsuccessful even if older or
partial success artifacts exist. Never overwrite a previous attempt's evidence.
