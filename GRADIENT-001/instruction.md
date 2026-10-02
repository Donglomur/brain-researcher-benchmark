# Connectivity gradients on a fixed movie cohort

Characterise the network organisation of connectivity gradients in the fixed
20-person released developmental movie cohort, using the Schaefer 400-parcel,
seven-network atlas and the four public configurations. This is a descriptive
method application, not a replication of the adult HCP cohort in
[Margulies et al. (2016)](https://doi.org/10.1073/pnas.1608282113), a population
inference, or a test with a required stable/unstable result.

The complete mathematical and serialization specifications are
`/app/method_contract.json` and `/app/output_schema.json`. Use the original files
under `/app/data/gradient`, authenticated by its `source_manifest.json`; do not
fetch replacement data or use historical reference outputs. Preserve all fixed
people, all 168 released frames, and all 400 source parcel IDs. Effective TR=2 s
and frame origin=0 are computational conventions, not independently established
movie-onset or slice-timing references.

## Computation

Use the exact participant order in the contract. It comes from the pinned Nilearn
loader and pandas ordering, not lexical IDs. The first/last-ten groups are
convenience subsets of that order, not randomized or independent replication
groups; their age composition can differ.

1. Transfer atlas labels to each native BOLD grid by the declared nearest
   identity-world mapping. Average calibrated voxel values in float64 using all
   assigned voxels and no implicit brain mask. The atlas's legacy FSL
   MNI152/MNI152NLin6Asym coordinates and the BOLD's MNI152NLin2009cAsym designation
   do not establish nonlinear inter-template registration: this is a disclosed
   operational mask approximation.
2. Demean and linearly detrend parcels and the 15 named nuisance columns;
   standardize nuisance columns, apply the pivoted QR projection, and retain
   residuals without final z-scoring. The band-pass arm applies the specified
   0.01–0.1 Hz fifth-order Butterworth SOS filter **after** regression, not joint
   data/confound filtering.
3. Apply the public numerical-resolution guard before Pearson FC. A parcel is
   active only when its residual centered L2 norm exceeds
   `1e-12 * sqrt(168) * max(1, original_raw_sample_SD)`. Both arms use the same
   original raw scale. This prevents projection roundoff becoming apparent
   signal; do not omit members, add epsilon to Pearson denominators, or replace
   undefined FC with zero. Preserve masks and scale/norm/threshold diagnostics.
4. Form four complete group-mean FCs: `nobp_all`, `bp_all`,
   `nobp_firstHalf`, and `nobp_secondHalf`. In every embedding keep exactly the
   largest **40 signed** entries per FC row among all 400 candidates including
   the diagonal; exact ties choose smaller source parcel ID. The diagonal is not
   forcibly retained. Use normalized-angle affinity and alpha=0.5.
5. Solve the real symmetric diffusion operator, retaining ten leading algebraic
   nontrivial modes and the eleventh eigenvalue as a boundary diagnostic. Use
   multiscale `lambda/(1-lambda)` coordinates. This explicitly corrects
   BrainSpace 0.1.20's symmetric eigensolver on a nonsymmetric row-normalized
   operator and its largest-magnitude selection, and replaces the floating
   expression that can retain 39 rather than 40 entries.
6. Give each raw coordinate its largest-absolute-entry sign. Align all 20
   no-band-pass embeddings by the specified ten-dimensional generalized
   Procrustes procedure initialized with raw `nobp_all`. Save every iteration's
   rotations, reference and distance. Residual-valid bases in unresolved
   eigenvalue blocks and certified nonunique optimal rotations are accepted;
   there is no hidden reference-basis gate.

Source-canonical means, cleaned series, FC, support and eigenvalues govern the
operator and diffusion scaling. Serialized receipts are not rethresholded to
create a different graph. Accepted certified eigenvectors and rotations govern
coordinates and summaries; rounded CSV values do not decide apex labels.

## Reporting and undefined results

Preserve the distinction between embedding each group-mean FC and averaging
aligned individual coordinates. An aligned coordinate is a multicomponent
rotation, not necessarily the individual's first eigenvector. Report all seven
network means for all five quantities, orientation signs, apex/bottom and the
descriptive leading-plane between/within ratio. Report all 190 signed
cross-person parcelwise correlations before/after alignment and each person's
complete 19-partner mean.

No apex identity, consistency gain, sign, between/within lower bound, or
stable/fragile narrative is required. The robustness Boolean reports whether all
four defined apex labels agree: true, false and null (incomplete support) are
valid. Undefined denominators, near-singular multiscale factors, unresolved
principal axes and unresolved retained-component boundaries use the public
null/status rules. Keep every member and dependency count. A completed run can
honestly contain undefined estimands.

Signed top-40 normalized-angle affinity is a BrainSpace-derived method choice,
not the exact original paper algorithm. The paper used adult HCP data, different
FC aggregation, residual-negative pruning and cosine similarity. Figures 1 and 3
supply context, not an expected answer for this movie cohort. Numerical
tolerances do not establish scientific stability near sparsity, sign, spectral
gap or apex ties.

## Outputs

Write these eight files to `${OUTPUT_DIR}` (default `/app/output`):

- `cohort.csv`: all 20 identities, frozen positions and subset membership.
- `parcels.csv`: all 20×400 source parcel/support records.
- `gradient_arrays.npz`: keyed source receipts, FCs, spectral certificates,
  Procrustes histories, displayed coordinates, masks and pairwise measurements.
- `configurations.csv`: all five quantities × seven networks.
- `per_subject.csv`: all 20 people, support/status and signed consistency.
- `results.json`: complete denominators and descriptive group summaries.
- `run_metadata.json`: exact public pins, source/header/support facts, software
  versions, numerical amendments and actual warnings.
- `findings.md`: measured results and limitations, acknowledging undefined
  support. There is no phrase-based grading.

Coherent keyed axis/row reorderings and harmless finite extras are allowed within
public bounds. Preserve enough spectral-array precision for the published
residual/orthogonality certificates. See the schema for exact fields, null/mask
rules and size limits.

Use a fresh output directory and protect source/code/contracts. On unsupported
source or numerical failure, exit nonzero and preserve `failure_report.json`
with a reason. Do not fabricate completion, silently retry changed settings, or
choose exclusions from outcomes. A `resource_pilot` is not a complete submission.
