# pH-weighted amide-proton-transfer (APT) CEST ratiometric indices

## Task
`/app/data/` holds a cohort of chemical-exchange-saturation-transfer (CEST) exams
(`sub-01` … `sub-08`). Each subject was scanned with a saturation Z-spectrum: the water signal
sampled over a list of saturation frequency offsets (in ppm relative to water). From these
signals, estimate the per-voxel **ratiometric APT indices** and write them out.

The cohort is **heterogeneous**: every subject's sidecar declares the offset list it actually
acquired, and you must adapt the analysis per subject — a pipeline that assumes one fixed offset
schedule will not fit them all. **Compute an index only where the subject's acquisition
determines it; where it does not, omit that index.**

Grading is **outcome-based and voxelwise against the true underlying physiology**. Each index
you write is compared voxel-by-voxel, inside the brain mask, to the *true* ratiometric index that
generated the signals (the B0-corrected pinned-offset ratios of the clean Z-spectrum). **Any
scientifically valid estimator is accepted** — linear or PCHIP B0 interpolation, whichever robust
corrupted-frame rejection scheme you prefer — because every correct method recovers the same
indices within tolerance. You are **not** required to reproduce any particular reference
implementation's output. Each (subject × index) is scored independently.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the conventions common to all subjects: how to form the **Z-spectrum**
(`Z = S / M0`), the **B0 convention** (the B0-corrected value at true offset Ω is the measured
spectrum evaluated at `Ω + b0`, by interpolating the acquired spectrum — read the pinned offsets
from the B0-corrected spectrum, not from a parametric pool-model fit), and the exact definitions
of the two graded indices:

- **APTR** (dimensionless) `= (Z(6.0) − Z(3.5)) / (Z(6.0) − Z(−3.5))` — a B0-corrected
  ratiometric APT-weighted index (amide 3.5 ppm, NOE −3.5 ppm, reference 6.0 ppm). Determinable
  for every subject.
- **AACID** (dimensionless, McVicar 2014) `= Z(3.5)·(Z(6.0) − Z(2.75)) / (Z(2.75)·(Z(6.0) −
  Z(3.5)))` — a B0-corrected, concentration-independent pH index (amide 3.5 ppm,
  guanidinium/amine 2.75 ppm, reference 6.0 ppm). Determinable **only** when the amine offset
  2.75 ppm is bracketed by the acquired offsets; otherwise it is not computable and must be
  omitted.

Read it before you start.

## Robustness / data-quality contract  (READ THIS)
The signals are realistic, not clean:

- **B0 inhomogeneity.** Some subjects have a strongly non-uniform B0 field (`b0.npy`, up to
  ±0.3 ppm). The B0-corrected Z-value at true offset Ω is the measured spectrum at `Ω + b0`,
  obtained by interpolating the acquired spectrum; ignoring B0 reads the wrong point of the
  Z-spectrum and biases every index. Apply it at every pinned offset.
- **Grossly corrupted offset frames.** In a **minority of subjects, one or two whole saturation
  frames are grossly corrupted** (e.g. by motion — the entire image at one offset scaled by a
  large factor) and are physically inconsistent with the rest of that subject's Z-spectrum.
  **You must detect and reject such corrupted frames robustly before reading the pinned-offset
  Z-values.** *Which* subjects and *which* offsets are affected is **not disclosed** — you must
  find them from the data. Any scientifically valid robust scheme is acceptable (leave-one-out
  residual outlier rejection, robust interpolation, etc.); a non-robust pipeline that reads a
  corrupted frame recovers the wrong ratio and fails the affected panels.

Modest Rician noise is present on every frame and does **not** need special handling beyond an
ordinary read.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `n_vox`, the acquired `offsets_ppm` list, and the file names below.
- `zspec.npy` — a float32 array of shape `(n_offsets, n_vox)`: the magnitude water signal `S`,
  one row per saturation offset, in the subject's voxel order.
- `m0.npy` — the unsaturated reference signal `M0` (shape `(n_vox,)`).
- `b0.npy` — the per-voxel B0 shift of the water resonance, in ppm (shape `(n_vox,)`).
- `tissue.npy` — per-voxel tissue label (shape `(n_vox,)`; see the protocol legend).
- `mask.npy` — the brain mask (shape `(n_vox,)`; indices are graded over these voxels).

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **computable** index, each of shape `(n_vox,)` in the subject's
voxel order:
- `APTR.npy` — the ratiometric APT-weighted index (every subject).
- `AACID.npy` — the ratiometric pH index — **only where determinable**.

Do **not** write a file for an index the subject's offsets cannot support.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for the
indices you can produce so the rest of the cohort can be graded.
