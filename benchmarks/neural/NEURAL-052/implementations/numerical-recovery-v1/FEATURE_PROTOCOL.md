# Fixed NEURAL052 image-only nuisance features

This is deterministic construction from the exact 100 repeated THINGS-fMRI photographs. It is not a neural analysis, learned image model, fit, benchmark score or claim that all image-level confounding is removed. No neural response or semantic label is an input to this transformation.

## Input identity and access

`SELECTED_MEMBERS.json` joins all 100 exact `stimulus` filenames from the authenticated repeated-image metadata; no alternate exemplars, missing-file omission or CC0 replacement. The original OSF `images_THINGS.zip` file670d6f7dbce84f4a7bb9371b, version1, is5,022,473,688 B. Its publisher-reported SHA256 is fb5a7cac28a27ff1ff8b723f072ed4a8309bc807a5f481b001da93f4213f3d24. Only the complete central directory and exact member ranges were acquired. This is **not** a local full-archive hash verification. The shared central directory is pinned; local headers/names, password-based ZIP decoding and member CRC32 all agree. `ACQUISITION.json` records a local SHA256 for each complete decoded JPEG (100 files;9,463,358 B).

`GEOMETRY.json` records header-only checks and source-profile hashes before feature preparation. Every image is square RGB JPEG; side lengths480..2025. EXIF orientation is absent or1. Three images carry ICC profiles, which are preserved and pinned, not dropped. The decoder is isolated Pillow11.3.0, official macOSarm64 CPython3.12wheel921bd305b10e82b4d1f5e802b6850677f965d8394203d182f078873851dada69; NumPy2.2.6/Python3.12.8. No shared environment was modified.

The source's actual `LICENSE` retains owner copyright for original photographs and describes research/educational use. It does not provide a general redistribution permission. Keep all JPEGs/operator acquisition material private to local source preparation; do not commit or publish these photographs as benchmark public assets. The distinct THINGSplus CC0 archive is not a substitute for the images shown. This note records source terms and makes no public-release clearance claim.

## Frozen transformation

Decode the original JPEG using Pillow11.3.0; convert to RGB; resize the complete square to256×256 with Pillow's LANCZOS filter (no crop/padding/EXIF rotation). Convert the resulting uint8 RGB to float64 by division by255. Do not transform embedded ICC profiles or invert display gamma. The descriptors therefore summarize encoded pixels, not calibrated photometric or retinal luminance, and do not reconstruct the scanner display's rendering pipeline.

In the fixed order in `prepare_features.FEATURES`, return15 scalars:

1. RGB channel means (three) and population standard deviations (three), over all256² pixels.
2. Population standard deviation of encoded luma Y=0.2126R+0.7152G+0.0722B (one).
3. Mean squared first differences of Y horizontally and vertically (two), with no wraparound/padding; units are squared encoded intensity difference per one resampled pixel.
4. Five radial Fourier-power fractions of mean-removed Y. Use the full two-dimensional NumPy FFT, explicitly set the DC power to0, and bin cycles/pixel by radii [0,.0625),[.0625,.125),[.125,.25),[.25,.5),[.5,sqrt(.5)]. Divide each sum by all non-DC power. The last bin includes the diagonal Nyquist corner; no half-spectrum weighting ambiguity.
5. One indicator for exactly spatially constant Y. For constant Y, all five power fractions and Y SD/gradient energies are0, and this indicator is1. Independently constant RGB channels have exact SD0. Nonconstant images use indicator0; no adaptive energy threshold or feature normalization is fitted.

The output has every filename exactly once in lexicographic order, each source JPEG hash, fixed feature names, actual package versions, and pins for the program/acquisition/selection/geometry. It contains no neural data. Any later centering, scaling, regularization or nuisance-model fitting must occur only on that scientific fold's training concepts/sessions. This100-image feature table does not supply the other8,640 images or complete NEURAL051's8,740-image requirement.

## Checks and boundaries

Generated checks cover constant RGB, analytic horizontal gradients, a known radial frequency exactly on a bin boundary, the diagonal Nyquist frequency, filename order/completeness/duplicates/traversal, and malformed pixel arrays. They use invented arrays only. The geometry check initially refused three ICC-bearing images; the explicit no-ICC-transform policy above retains all100 and fixes that source-handling choice before feature computation. No pixel-outcome, neural association or performance-based choice was made.
