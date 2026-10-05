# FODCROSS-001: declared fODF-estimator sensitivity on Sherbrooke data

## Scientific scope

This is a paper-derived **method / easy-control** comparison on one public
Sherbrooke in-vivo diffusion acquisition. The conceptual method source is
[Jeurissen et al. (2014)](https://doi.org/10.1016/j.neuroimage.2014.07.061),
*Multi-tissue constrained spherical deconvolution for improved analysis of
multi-shell diffusion MRI data*, with single-tissue CSD from Tournier et al.
(2007). The source scan is not established as the original paper's cohort;
the fixed voxel slab and peak-count summaries are task-defined measurements,
not the paper's population crossing-fibre prevalence.

Compare the declared MSMT-CSD, b=1000 SSST-CSD and b=3500 SSST-CSD recipes on
one identical FA-defined ROI. At least two recipes are required, and any one
submitted recipe may supply the headline. No recipe is treated as anatomical
ground truth. Differences combine acquisition-shell and model assumptions;
they do not by themselves isolate a causal partial-volume mechanism.

The prior mixed-shell `csd_all` comparator is removed: fitting a single-shell
response model to mixed shells is not a valid single-shell comparison.
Earlier numerical targets, mandatory MSMT preference, prescribed differences
and “un-fabricable” claims are withdrawn.

## Source and public contract

Use the original public CC0 image and b-values from
[UW ResearchWorks 1773/38475](https://digital.lib.washington.edu/handle/1773/38475),
with DIPY's corrected b-vectors. The correction is versioned in
[DIPY PR 3847](https://github.com/dipy/dipy/pull/3847): the historical UW b-vector
file must not be silently substituted for the corrected dependency version.
The manifest records original versus corrected lineage, immutable/pinned source
identities, published MD5 and verified SHA256/byte sizes. Sources are downloaded
during image build and available offline at runtime. No synthetic scan or host
cache is substituted.

The public contract states the low-b tensor ROI, fixed voxel box, response
selection and estimation, SH bases/spheres, solver and peak definitions.
Response masks are operational diffusion-based heuristics, not independently
validated tissue segmentations. The NIfTI spatial-unit field is unknown; no
resampling or physical-distance operation is performed.

## Verifier and validation design

Every submitted estimator must have exactly the complete fixed ROI with unique
integer coordinates and peak counts from 0 to 3. Bind each map to its declared
recipe; bind the primary map to the declared primary estimator. Recompute
crossing counts/fractions and mean peaks from every submitted table. Do not use
partial-ROI coverage, correlation, broad agreement allowances, an expected
direction/minimum gap, or English keyword gates. Scoring is binary.

Build a new source-bound reference from genuine retained fits. Preserve model
coefficients, response estimates, sphere definitions, reconstructed fODFs and
signal residuals so secondary checks can distinguish numerical implementation
agreement from biological truth. Repeated execution must support the numerical
comparison; boundary-sensitive peak counts need inspection before freezing.

Positive tests cover equivalent CSV formatting/order, valid two-recipe subsets
and a non-MSMT primary. Negative tests target the demonstrated same-map/two-label
bypass, missing/padded/duplicate coordinates, fractional counts, extra invalid
groups, disconnected primary tables and incorrect aggregates/metadata.

Actual validation status comes from `REPAIR_STATUS.md` and the retained
exact-commit Harbor/authoring execution receipts. Reference-derived fixtures
alone do not establish source reproduction or successful execution.

## Limits

This tests a fixed computational measurement, not independent anatomy, population
prevalence, or proof that a submitted program ran honestly. Public numerical
answer material introduces contamination risk. No Sol/frontier difficulty run,
publication or acceptance is implied. Retain as a method/easy control unless
separate scientific and model-evaluation evidence supports a stronger role.

Resource ceiling: 2 CPU, 8 GiB RAM, no GPU, 3600 s agent, 1800 s verifier.
