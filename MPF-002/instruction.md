# Macromolecular proton fraction (MPF) mapping of a heterogeneous fast-qMT cohort

## Task
`/app/data/` holds a cohort of quantitative magnetization-transfer (qMT) exams
(`sub-01` … `sub-08`). Each subject was scanned with an unsaturated **reference** image and one
or more **MT-weighted** images, plus per-voxel `R1f`, `B1+` and `B0` maps. From these, estimate
the per-voxel **macromolecular proton fraction (MPF)** with the constrained two-pool model and
write it out.

The cohort is **heterogeneous**: every subject's sidecar declares the MT measurements it
actually acquired (each with its saturation offset and amplitude), and you must adapt the
analysis per subject — a pipeline that assumes one fixed recipe will not fit them all. **Compute
a quantity only where the subject's acquisition determines it; where it does not, omit it.**
There is no reference fitter provided — implement the estimators yourself and get the physics,
units, and per-subject adaptation right.

Grading is **outcome-based and voxelwise against the true underlying physiology**: each map you
write is compared voxel-by-voxel, inside the analysis mask, to the *true* quantity that
generated the signals. **Any scientifically valid estimator is accepted** — a different
lineshape quadrature, a different optimizer or single-point root-finder, whichever robust
outlier-volume rejection you prefer — because every correct method recovers the same physiology
within tolerance; you are **not** required to reproduce any particular reference implementation.
Each (subject × map) is scored independently, so produce every map you can support and omit the
rest.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the physics and conventions common to all subjects: the **two-pool
continuous-wave steady-state signal model** (the MT ratio `S_MT/S_ref` as a function of the
bound-pool fraction `f`, the exchange rate `R`, `R1f`, and the saturation condition), the
**super-Lorentzian** bound-pool lineshape, the **saturation convention** (`B1+`-scaled amplitude
`w1 = GAMMA·b1rms_ut·1e-6·b1`, off-resonance-corrected offset `Delta_eff = offset_hz − b0`), the
**pinned constrained-model constants**, the exact definitions of **MPF** (single-point inversion
with the exchange rate pinned, vs. the joint constrained fit for a full Z-spectrum) and of the
forward exchange rate **kf**, the **unit** of each quantity, and the **tissue legend**. Read it
before you start.

## Robustness / data-quality contract  (READ THIS)
The signals are realistic, not clean:

- **B1+ / B0.** The saturation power scales with the transmit field (`w1 ∝ b1`, so the
  saturation rate `∝ b1²`) and the effective offset shifts with off-resonance
  (`Delta_eff = offset_hz − b0`). Apply `b1` and `b0` to **every** MT measurement; ignoring
  either grossly biases MPF.
- **Grossly corrupted MT volumes.** In a **majority of the multi-measurement (full-Z) subjects,
  one MT-weighted volume is grossly corrupted** (a motion artefact scaling the whole volume) and
  is physically inconsistent with the two-pool model of the rest of that subject's Z-spectrum.
  **You must detect and reject such a corrupted volume robustly before the (MPF, exchange) fit
  is trusted.** *Which* subjects and *which* volume are affected is **not disclosed** — find them
  from the data. Any scientifically valid robust scheme is acceptable; a non-robust fit over all
  volumes recovers the wrong MPF and exchange rate on the affected subjects and fails those
  panels. (Single-point subjects have only one MT measurement and no such volume.)
- **Rician noise** (modest, per-subject) is present on every measurement and needs no special
  handling beyond an ordinary fit.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `field_T`, `f0_mhz`, `n_vox`, and a `measurements` list; each entry gives the
  MT-weighted measurement's `offset_hz` and `b1rms_ut`, in the row order of `mtw.npy`.
- `mtw.npy` — a float32 array of shape `(n_meas, n_vox)`: the MT-weighted magnitude signal, one
  row per measurement, in the subject's voxel order.
- `ref.npy` — the unsaturated reference magnitude signal (shape `(n_vox,)`).
- `r1f.npy` — the free-pool longitudinal rate R1f (shape `(n_vox,)`, 1/s).
- `b1.npy` — the per-voxel transmit factor B1 (shape `(n_vox,)`, 1.0 = nominal).
- `b0.npy` — the per-voxel off-resonance in Hz (shape `(n_vox,)`).
- `tissue.npy` — per-voxel tissue label (shape `(n_vox,)`; see the protocol legend, white
  matter = 2).
- `mask.npy` — the analysis mask (shape `(n_vox,)`; maps are graded over these voxels).

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **computable** map, each of shape `(n_vox,)` in the subject's
voxel order:
- `MPF.npy` — macromolecular proton fraction (p.u., percent).
- `kf.npy` — forward free→bound exchange rate (1/s) — **only where determinable**.

Do **not** write a file for a quantity the subject's acquisition cannot support.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for
the maps you can produce so the rest of the cohort can be graded.
