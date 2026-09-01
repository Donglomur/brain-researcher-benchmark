# Absolute tissue-sodium-concentration (TSC) mapping of a heterogeneous 23Na cohort

## Task
`/app/data/` holds a cohort of ultra-high-field sodium (**23Na**) MRI exams
(`sub-01` … `sub-07`). Each subject has **one** spoiled-gradient-echo acquisition (single- or
multi-echo) together with a set of **external reference phantoms of known [Na]** in the field
of view. From these signals, estimate the per-voxel **absolute tissue sodium concentration
(TSC), in mmol/L**, and write it out.

The cohort is **heterogeneous**: every subject's sidecar declares its own acquisition (flip
angle, TR, echo times, per-region relaxation constants, and the phantom set), and you must
adapt the analysis per subject — a pipeline that assumes one fixed recipe will not fit them
all. **Compute a quantity only where the subject's acquisition determines it; where it does
not, omit it.** There is no reference solver provided — implement the estimators yourself and
get the physics, the units, and the per-subject adaptation right.

Grading is **outcome-based and voxelwise against the true underlying physiology**: each map you
write is compared voxel-by-voxel, over the tissue labels, to the *true* per-voxel sodium
concentration (mmol/L) and effective T2* (ms) that generated the signals. **Any scientifically
valid estimator is accepted** — weighted or unweighted log-linear relaxation fit, median-ratio
or through-origin phantom calibration, whichever SNR threshold and robust bad-tube rejection you
prefer — because every correct method recovers the same absolute physiology within tolerance.
You are **not** required to reproduce any particular reference implementation's output. Partial
cohorts and partial map sets are scored proportionally, so produce every map you can support.

## Robustness / data-quality contract  (READ THIS)
The signals are realistic, not clean, and the absolute mmol/L scale is only as good as the
calibration and the SNR handling. Handle all of the following robustly; *which* sessions and
*which* voxels are affected is **not disclosed** — you must find them from the data:

- **A grossly mis-calibrated reference tube.** In a **minority of sessions**, one of the
  external reference phantom tubes is grossly mis-calibrated (its corrected signal is
  inconsistent with the through-origin trend of the other tubes by tens of percent). **You must
  detect and reject such an outlier tube before fitting the calibration slope**, or the entire
  TSC scale of that session is biased. Any scientifically valid robust scheme is acceptable
  (a MAD/z outlier test on the per-tube gain ratio, etc.); the clean tubes scatter only ~1–2 %.
- **Low-SNR signal-void voxels.** In a **minority of sessions**, a compact cluster of near-noise
  voxels (susceptibility dropout) sits inside the parenchyma. These carry no reliable signal and
  are unrecoverable — **exclude them** (write them non-finite or ~0), do **not** report them as a
  spurious concentration.
- **B1+ / receive / T1-saturation correction.** The transmit (`b1.npy`) and receive
  (`rxsens.npy`) maps are inhomogeneous on some sessions; ignoring either biases TSC. The true
  flip is `a = B1 × radians(alpha_deg)` and enters the saturation factor everywhere (tissue and
  phantom voxels alike).

Rician noise (modest, tissue SNR ≈ 30+) is present on every voxel and does **not** need special
handling beyond an ordinary fit.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the physics and conventions common to all subjects: the SPGR **signal
model** (session gain, receive sensitivity, the B1+/T1 **saturation factor**
`f_sat(a, T1) = sin(a)(1−E1)/(1−cos(a)E1)`), the **B1+ convention** (`a = B1 × radians(flip_deg)`),
how the relaxation-corrected TE=0 signal is recovered, the **external-reference-phantom
calibration** that fixes the absolute mmol/L scale, the exact definitions of **TSC** and
**T2\*** with their **units**, and the **tissue legend**. Read it before you start.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `field_T`, `alpha_deg` (nominal flip), `tr_ms`, `te_ms` (echo times),
  `noise_sigma`, a `tissue_relax` table (per tissue-label relaxation constants), and a
  `phantoms` list (each with its `label`, known `conc_mM`, and relaxation constants), plus the
  file names below.
- `signal.npy` — the magnitude SPGR signal, a float32 array of shape `(n_echoes, n_vox)`
  (one row per echo) in the subject's voxel order.
- `b1.npy` — the per-voxel transmit factor B1 (shape `(n_vox,)`, 1.0 = nominal).
- `rxsens.npy` — the per-voxel receive sensitivity (shape `(n_vox,)`, 1.0 = nominal).
- `tissue.npy` — per-voxel tissue label (shape `(n_vox,)`; see the protocol legend — GM=1,
  WM=2, tumour=3, CSF=4; labels ≥ 11 are the external reference phantom tubes).
- `mask.npy` — the acquired region (shape `(n_vox,)`).

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **computable** map, each of shape `(n_vox,)` in the subject's
voxel order:
- `TSC.npy` — absolute tissue sodium concentration (mmol/L), for parenchymal voxels (GM, WM,
  tumour).
- `T2star.npy` — effective sodium transverse relaxation time (ms) — **only where determinable**.

Do **not** write a file for a map the subject's acquisition cannot support.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for
the maps you can produce so the rest of the cohort can be graded.
