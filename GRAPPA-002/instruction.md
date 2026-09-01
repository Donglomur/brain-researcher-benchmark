# GRAPPA parallel-imaging reconstruction of a heterogeneous multi-coil cohort

## Task
`/app/data/` holds a cohort of accelerated multi-coil MRI acquisitions (`sub-01` … `sub-08`).
Each subject was scanned with an **undersampled** (parallel-imaging) k-space plus a separate
fully-sampled **auto-calibration (ACS)** block. From these, reconstruct the missing k-space by
**GRAPPA**, combine the coils, and write the coil-combined **magnitude image**.

The cohort is **heterogeneous**: every subject's sidecar declares its acceleration, its acquired
phase-encode lines, and its calibration kernel geometry, and you must adapt the reconstruction
per subject — a pipeline that assumes one fixed recipe will not reconstruct them all. There is
no reconstruction library provided — implement GRAPPA yourself and get the k-space bookkeeping,
the calibration fit, and the coil combination right.

Grading is **outcome-based and per-pixel against the fully-sampled true image**: each
reconstructed magnitude is compared, over the object, to the *true* coil-combined magnitude of
the **fully-sampled** acquisition (the root-sum-of-squares over the live coils of the clean full
k-space that generated the data). **Any scientifically valid GRAPPA reconstruction is accepted**
— whatever linear algebra, corrupt-line / dead-coil detection, or kernel size you choose —
because every correct reconstruction recovers the fully-sampled image up to residual aliasing.
You are **not** required to reproduce any particular reference implementation's output. The
comparison is **up to a single global scale** (each image is normalised by its median over the
object), so an overall intensity/receive-gain convention does not matter — only the spatial
content (residual aliasing) does. Each subject is scored independently, so reconstruct as many
as you can.

## Shared conventions and output contract (`/app/data/protocol.json`)
A single JSON with the conventions common to all subjects: the **k-space convention**
(DC-centered; a coil image is `ifft2(ifftshift(K))`), the **coil combination** (root-sum-of-
squares of the coil images), the **sampling convention** (which phase-encode lines are acquired
for an acceleration `R`, and how the `R-1` missing offsets are defined), the **GRAPPA kernel
definition** (a shift-invariant kernel of `pe_blocks` source lines × `ro_cols` readout columns ×
all coils, fit by least squares from the ACS), and the **output spec**. Read it before you start.

## Robustness / data-quality contract  (READ THIS)
The acquisitions are realistic, not clean. Three things must be handled correctly, or they leave
structured aliasing in the reconstruction:

- **Every R-1 missing-line offset.** For acceleration `R` there are `R-1` distinct missing-line
  offsets `t = 1 … R-1`, and **each must be reconstructed with its own kernel fit**. A pipeline
  that assumes a single offset (the `R=2` case) leaves the `R>2` subjects grossly aliased. The
  acceleration is in each sidecar; adapt to it.
- **Grossly corrupted ACS lines.** In a **majority of subjects, one or two individual ACS
  calibration lines are grossly corrupted** (motion spikes) and are inconsistent with the rest of
  the calibration block. **You must detect and reject such lines robustly before the kernel fit**,
  or the fitted weights alias the reconstruction. Note the corrupt lines sit in the low-energy
  transition zone of the ACS while the center-of-k-space lines are legitimately much brighter, so
  a single global energy threshold does not separate them — a local, iterative robust detector is
  needed. *Which* subjects and *which* lines are affected is **not disclosed** — find them from
  the data.
- **Dead receive channels.** Some subjects have a **dead (noise-only) receive coil** that must be
  **excluded from both the kernel fit and the RSS coil combination**, or it corrupts the weights
  and inflates the magnitude. *Which* subjects and *which* channel is **not disclosed** — detect
  it from the data (a channel that is pure noise in the ACS and imaging k-space).

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `R` (acceleration), `n_pe`, `n_ro`, `n_coils`, `acquired_pe` (the full-grid
  phase-encode indices present in `kspace.npy`, in order), `acs_pe` (the full-grid indices of the
  ACS block), and `kernel` = `{pe_blocks, ro_cols}` (the calibration kernel geometry to use).
- `kspace.npy` — the undersampled imaging k-space, a complex array of shape
  `(n_coils, len(acquired_pe), n_ro)`, DC-centered, holding only the acquired lines.
- `acs.npy` — the separate fully-sampled ACS calibration block, a complex array of shape
  `(n_coils, len(acs_pe), n_ro)`, DC-centered. Use it **only** to fit the kernel weights.
- `mask.npy` — the object mask (shape `(n_pe, n_ro)`; the reconstruction is graded over these
  pixels).

## Required output (`/app/output/sub-XX/`)
Write `recon.npy` — the reconstructed coil-combined **magnitude** image, a float32 array of
shape `(n_pe, n_ro)` in natural image order (as returned by the inverse DFT above, with no extra
`fftshift`).

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `recon.npy` files
for the subjects you can reconstruct so the rest of the cohort can be graded.
