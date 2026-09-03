# Deep-gray susceptibility by dipole inversion (QSMDIPOLE-001)

## Scientific context

Quantitative susceptibility mapping (QSM) recovers the tissue magnetic susceptibility
distribution χ from the measured local field by inverting the unit dipole convolution. The
deep-gray nuclei accumulate iron with age and are the highest-susceptibility structures in the
healthy brain, so their mean susceptibility is a standard QSM read-out. The **2016 QSM
Reconstruction Challenge** (Langkammer et al., *Magn Reson Med* 2018,
https://doi.org/10.1002/mrm.26830) provides, for one subject, a single-orientation local tissue
field together with a susceptibility-tensor-imaging (STI) **χ₃₃ reference** reconstructed from 12
head orientations — the challenge's ground-truth susceptibility map.

## Task

Reconstruct the susceptibility map of this subject **from the single-orientation tissue field**
and report the mean susceptibility of the deep-gray nuclei, **reproducing the deep-gray
susceptibility of the STI χ₃₃ reference** (the reference map itself is held out — it is not in
`/app/data`).

The inputs are in `/app/data` (see `protocol.json`):

- `phs_tissue.nii.gz` — the single-orientation local tissue field, already normalised to **ppm**
  (divided by γ·TE·B₀, background field removed). Grid 160³, 1.06 mm isotropic.
- `msk.nii.gz` — brain mask.
- `evaluation_mask.nii.gz` — labelled ROI mask. Deep-gray nuclei are labels **1–6**; the two you
  must report are **globus pallidus (label 3)** and **putamen (label 2)**. `protocol.json` gives the
  full label legend.

Use the **reconstruction recipe pinned in `protocol.json`**: the closed-form L₂ (gradient-
regularised Tikhonov) dipole inversion with the Lorentz-corrected dipole kernel
`D(k) = 1/3 − k_z²/|k|²` (B₀ along axis index 2), gradient regulariser
`E(k) = Σ_j |1 − e^{2πi k_j/N_j}|²`, solution
`χ̂(k) = conj(D)·field̂(k) / (|D|² + reg·E(k))` with `reg = 0.09`, then multiply the image-space
susceptibility by the brain mask. Report susceptibility in **ppb** (1 ppm = 1000 ppb).

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `susceptibility_ppm.npy` — the reconstructed susceptibility map (float, shape 160³, **ppm**).
- `nuclei_susceptibility.csv` — one row per deep-gray nucleus (labels 1–6):
  `label, nucleus, susceptibility_ppb`.
- `run_metadata.json` — dataset id, the inversion method and `reg`, and the choices you made.
- `findings.md` — a short written summary of the deep-gray susceptibilities you obtained and how
  they compare to the STI reference. State only what your analysis actually supports.

## Failure handling

If the inputs in `/app/data` cannot be resolved, exit non-zero with `failed_precondition` and a
non-empty reason, and still write a parseable `run_metadata.json`, `nuclei_susceptibility.csv`
(header only), and `findings.md`.
