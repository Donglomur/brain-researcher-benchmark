## QSMDIPOLE-001

**Source-derived closed-form L2 QSM reconstruction: an easy method control.**

### Paper and source correspondence

Langkammer et al. 2018, [10.1002/mrm.26830](https://doi.org/10.1002/mrm.26830),
Figure 1 identifies the challenge input data; Table 1/Figure 2 include the
provided CF-L2 baseline. The original archive's
`qsm2016_script_recon_evaluation.m` supplies the inversion, reg=0.09, physical
spacing, axis-2 B0 and D(0)=1/3. The target is that explicit computational method,
not a specific named-nucleus susceptibility or an original-paper performance rank.
Six numeric ROI medians are a benchmark summary, not the paper's regional
error against chi33 or the archive's GM/WM pooled absolute-error calculation.

The public [original archive](https://www.neuroimaging.at/media/qsm/20170327_qsm2016_recon_challenge.zip)
is 244,982,259 bytes. Only three selected image members are acquired with bounded,
verified byte-range requests. Original source CRCs, transport identity and locally
measured SHA256s are recorded; these are not independently published SHA256s or a
full-archive cryptographic measurement.

Original and shipped volumes have identical voxel values and geometry. Existing
gzip/header/datatype representations are retained, documented as lossless repacks,
and checked again against original members at Docker build. The field is already
normalized to ppm. The source spacing is [1.0625,1.0625,1.0714285714285714] mm,
not exactly isotropic. Analysis is entirely offline.

### Scientific correction

The old instruction mixed a fixed reconstruction with two hard-coded STI medians,
an ROI_3-versus-ROI_2 ordering, inferred anatomy and an unsupported zero-brain-mean
claim. Those acceptance targets are removed. A high Pearson correlation was also
insufficient to enforce the claimed full map because it ignores scale and offset.

Preserving the original code's D(0)=1/3 is now an explicit computational convention,
not a claim that this is the physically unique gauge. It sets the pre-mask mean
to three times the field mean; final masking changes that mean. No equality to
STI's offset or absolute tissue susceptibility is asserted.

The [2020 follow-up](https://doi.org/10.1002/mrm.28185) analyzes mismatch between
the challenge single-orientation field and the STI reference. Source-derived
numerical agreement is not evidence of biological accuracy. Individual label
anatomy remains unauthenticated; the original code only establishes broad GM/WM
grouping. Small evaluation ROIs must not be called whole-nucleus segmentations.

### Public contract and verifier

Unshifted physical dipole frequencies, array-index gradient penalty, no padding,
periodic boundaries, no extra preprocessing/reference subtraction, and post-only
masking are explicit. The complete finite submitted map is compared with the
genuine source-bound CF-L2 calculation. Outside-mask values must be exactly zero.
All six unique ROI counts and medians are recomputed from the submitted saved map;
input identities, geometry and declared numerical choices are checked.

No hidden STI/physiological bands, contrast ordering, dynamic-range threshold or
prose keyword is graded. Equivalent float precision and harmless formatting
variations are accepted. Private oracle intermediates are authoring evidence,
not participant deliverables. All-or-nothing scoring is stated honestly.

### Validation boundary and cost

Two CPUs, 8 GB RAM, no GPU; one 160³ FFT reconstruction. Separate real-FFT/original
MATLAB-frequency checks, spectral/DC diagnostics and adversarial output cases
are required before the final source-bound bank and clean-commit Harbor receipt.
Executed results belong in REPAIR_STATUS.md and the external per-PR receipt;
this proposal itself is not execution evidence.

The archive is public, but no dataset/main-QSM-code redistribution license was
found in the inspected official material. The Jimmy Shen NIfTI utility license
does not cover the dataset. Local validation is not permission to publish data
or a baked image. Maintainer licensing and scientific-role review remain open.
No Sol run or empirical hardness claim is included.
