# Source-derived CF-L2 susceptibility reconstruction control

## Scientific target

Implement the supplied closed-form, gradient-regularized L2 dipole inversion
on one subject's QSM Reconstruction Challenge 2016 data. Report six numeric
evaluation-region medians from your reconstructed map.

The source is Langkammer et al., *Magnetic Resonance in Medicine* 2018,
[10.1002/mrm.26830](https://doi.org/10.1002/mrm.26830): Figure 1 describes the
inputs; Table 1/Figure 2 include the provided CF-L2 reconstruction baseline.
The original archive's `qsm2016_script_recon_evaluation.m`, section
"closed-form L2 recon", supplies this numerical recipe. This task reproduces
that calculation, with numeric-ROI medians as a **benchmark-defined summary**.
It does not reproduce the paper's pooled ROI error, rank algorithms, establish
an anatomical iron finding, or recover an unquestionable biological ground truth.
The [challenge follow-up](https://doi.org/10.1002/mrm.28185) discusses limits of
the single-orientation field and STI reference comparison.

## Inputs and provenance

All analysis is offline. `/app/data` contains:

- `phs_tissue.nii.gz`: local tissue field in ppm, already normalized by
  gyro × TE × B0; no extra phase-to-ppm conversion.
- `msk.nii.gz`: binary brain mask.
- `evaluation_mask.nii.gz`: integer evaluation labels. Measure labels 1–6.
  The original code groups these as GM and labels >6 as WM, but supplies no
  individual named-anatomy legend. Use numeric ROI identities.
- `protocol.json`, `input_manifest.json`, `source_manifest.json` and the
  source-staging receipt: public recipe, hashes and original-member provenance.

The native array shape is (160,160,160). Use physical spacing
`[1.0625,1.0625,1.0714285714285714]` mm from original `spatial_res.txt`,
not a claim of exact isotropy. Header z spacing rounds to 1.0714285373687744.
Preserve native array-axis order and the affine in the public metadata template.
Field/mask spatial header units are unspecified; the original code establishes
the physical spacing and field normalization.

The shipped values and geometry match original archive members exactly, although
gzip/header representations differ and masks were losslessly cast to uint8.
Original members are retained under `original/` for provenance, not fitted
reference answers. Original STI/COSMOS maps are not supplied. Data are publicly
accessible; dataset/main-code redistribution terms remain unestablished.

## Public reconstruction contract

Use the complete provided field grid, without additional masking, smoothing,
detrending, background removal, resampling or offset subtraction.

1. B0 is array axis 2 (zero-based). Construct unshifted physical frequencies
   `k_j = fftfreq(N_j, d=voxel_size_mm[j])`.
2. For nonzero frequency use
   `D(k) = 1/3 - k_2**2 / (k_0**2+k_1**2+k_2**2)`.
   Set **D(0)=1/3**, preserving the original code's computational convention.
3. For integer Fourier indices `n_j=0,...,N_j-1`, use
   `E = sum_j |1-exp(2*pi*i*n_j/N_j)|**2`.
   This is an **array-index gradient penalty**; do not divide by voxel spacing.
4. With `reg=0.09`, solve
   `X = conj(D)*FFT(field)/(abs(D)**2 + reg*E)`.
   Use backward FFT normalization (unscaled forward, 1/product(N) inverse),
   no padding, and the corresponding periodic boundary convention.
5. Take the real inverse FFT, then multiply by the brain mask. Return ppm.
   Every voxel must be finite and every outside-mask voxel exactly zero.

Equivalent numerical implementations are accepted within the tolerances below.
The original MATLAB uses twice the physical Fourier frequencies and adds machine
epsilon to its squared-frequency denominator; the common scale cancels except
for negligible roundoff. This contract specifies the unshifted form explicitly,
not bitwise MATLAB identity.

Do not subtract a CSF, WM or brain-mean reference. D(0)=1/3 implies the
**pre-mask** mean susceptibility is three times the field mean. Masking generally
changes that mean. Neither step guarantees zero brain-mask mean or the STI
reference's offset; this is not a universal absolute-susceptibility convention.

## Required outputs

Write to `${OUTPUT_DIR}` (default `/app/output`):

- `susceptibility_ppm.npy`: real floating (160,160,160) array in native index
  order, in ppm. Float32 or float64 is acceptable.
- `nuclei_susceptibility.csv`: exactly one row for each label 1–6, with
  `label,n_voxels,susceptibility_ppb`. Compute the voxel count from the
  evaluation mask and **1000 × median(saved map[ROI])** for each ROI.
  The legacy filename does not authenticate nuclei. An optional `nucleus`
  display column may use `ROI_1`, etc.; it is not graded.
- `run_metadata.json`: start from the static public
  `/app/method_contract.json`, and add `status="ok"`,
  `n_brain_voxels`, `n_rois_reported=6`, and
  `brain_mask_mean_ppb=1000*mean(saved map[brain mask])`.
- `findings.md`: nonempty discussion of the numeric medians, method, reference
  convention and interpretive limits. No required keywords or exact wording.

Reordered CSV rows/columns, integral numeric label notation such as `1.0`,
harmless extra columns/metadata and equivalent precision are acceptable. The
provided template describes inputs and choices, not computed answers.

The verifier checks the **entire numerical map**, not just a correlation or
two approximate published ROI values. Map tolerance is absolute 2e-7 ppm plus
relative 2e-5; outside-mask zeros and ROI membership/counts are exact.
CSV medians may differ from saved-map recomputation by at most 0.02 ppb
(two-decimal rounding is supported). Brain-mean tolerance is 0.001 ppb plus
relative 1e-5; geometry metadata absolute tolerance is 1e-6. Other numeric recipe
metadata allows 1e-12 absolute decimal-rounding error.
No physiological range, ROI ordering, STI-matching band or prose keyword is
an acceptance criterion. Scoring is all-or-nothing over required outputs.

## Failure handling

If source identity, geometry or data validity fails, exit nonzero. Still write
parseable metadata with `status="failed_precondition"` and a nonempty reason,
a header-only CSV and an explanatory findings file. Do not invent a map.
