# Local validation follow-up — 2026-10-01

## Source and scientific target

Retained as the original challenge's provided CF-L2 computational method control,
not a named-nucleus finding or a claim to biological STI truth. Figure 1,
Table 1/Figure 2 and the original evaluation script establish the input/method
correspondence. Numeric ROI medians are an explicitly benchmark-defined summary.

The official dated archive is 244,982,259 bytes. Bounded source requests acquired
only three image members (3,686,367 member bytes; 3,635,069 compressed payload
bytes), plus original directory/code metadata. No full archive, STI or COSMOS
reference was acquired. CRC32/HTTP range/ETag checks and measured SHA256 pins are
retained. There is no independently published SHA256 or full-archive hash claim.

Every original and shipped voxel value and affine/zoom matches exactly. Existing
three shipped files remain unchanged. Differences are lossless gzip/header
repacking, float32/int16 masks cast to uint8, slope 0 to explicit 1, and the field's
unused extension flag. Original members are retained read-only in the image and
independently reparsed. The source spacing is not exactly isotropic; original
code establishes ppm normalization and physical spacing despite unspecified
field/mask header units.

Original code groups six GM and five WM labels but does not authenticate the
individual anatomical legend. The six measurement ROIs have 94/105/120/18/27/53
voxels, not demonstrated whole-nucleus segmentations.

## Numerical and verifier repair

The original D(0)=1/3, reg=0.09 and index-gradient conventions are preserved and
public. Removed: zero brain-mask mean/STI-offset claims, two hard-coded STI
targets, anatomical aliases, ROI ordering, correlation-only acceptance and
physiological/dynamic-range gates. Complete finite source-bound maps, exact
outside-mask zeros, six unique ROI counts/medians and saved-map arithmetic are
checked. Harmless formatting/precision and a separate actual SciPy reconstruction
are accepted within prespecified tolerances; no prose keywords are graded.

The offline native reconstruction covers 933,481 brain voxels. ROI medians in ppb:
53.654606, 78.039780, 153.291389, 76.285485, 85.817568, 99.396616.
Final brain-mask mean is -0.040995 ppb. The independent original-MATLAB-frequency
SciPy real-FFT implementation differs by at most 5.29e-14 ppm before float32
serialization; serialization contributes at most 7.45e-9 ppm. The pre-mask
spectral normal-equation relative residual is 8.51e-14 and DC error 8.91e-20 ppm.
Regularized forward relative residual is 0.5383, a diagnostic rather than a
required perfect fit. This is numerical agreement, not biological accuracy.

The actual field DC is nearly zero (pre-mask mean 1.58e-13 ppm), so this real
dataset alone does not distinguish alternative DC conventions at map tolerance.
Small analytic fixtures test that algebra separately; no real-data discrimination
claim is made for the DC choice.

The bank was regenerated only after original-source and spectral-identity checks.
Initial adversarial testing exposed six no-op test mutations on Fortran-order
arrays; write-through mutations and explicit mutation assertions fixed the tests,
without changing the verifier/tolerances. Failed logs are retained. The corrected
authoring suite includes 80 mechanics, 21 numerical, 44 staging fixtures and
60 genuine-output cases (8 positives, 52 negatives).

## Acceptance boundary

Native/independent checks are complete; final clean-commit Harbor reward, image,
digest and regression readback are recorded after commit in:

`/home/zijiaochen/projects/brain_researcher_benchmark/tracking/pr_repairs_2026-10-01/pr-151/receipt.json`.

Native tests alone do not establish that final reward. Original/native/independent
evidence remains under `brain-researcher-benchmark-runs/20261001/pr151-*`.

Public access is established, but data/main-code redistribution terms are not.
The included NIfTI utility license does not license the MRI data. Maintainer
licensing and scientific-role acceptance remain open; no data/image publication,
push, PR comment, merge or Sol/frontier difficulty run is included.
