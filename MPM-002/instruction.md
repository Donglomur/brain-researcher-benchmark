# Quantitative multi-parameter mapping (MPM) of a heterogeneous SPGR cohort

## Task
`/app/data/` holds a cohort of quantitative multi-parameter-mapping exams
(`sub-01` … `sub-07`). Each subject was scanned with one or more multi-echo spoiled
gradient-echo (SPGR/FLASH) contrasts. From these signals, estimate the per-voxel
**quantitative maps** (R1, PD, and — where the acquisition supports them — R2\* and MTsat)
and write them out.

The cohort is **heterogeneous**: every subject's sidecar declares the contrasts it actually
acquired (flip angle, TR, echo times, and whether the contrast is MT-weighted), and you must
adapt the analysis per subject — a pipeline that assumes one fixed recipe will not fit them
all. **Compute a map only where the subject's acquisition determines it; where it does not,
omit that map** (see *Computability*). Implement the estimators yourself and get the physics,
units, and per-subject adaptation right.

## What is graded
Grading is **outcome-based and voxelwise against the true underlying physiology**. Each map
you write is compared voxel-by-voxel, inside the brain mask, to the *true* quantitative map
that generated the signals. **Any scientifically valid estimator is accepted** — ordinary or
weighted least squares, closed-form or iterative VFA, whichever robust echo-rejection scheme
you prefer — because every correct method recovers the same physiology within tolerance. You
are **not** required to reproduce any particular reference implementation's output. Each
(subject × map) is scored independently and partial cohorts/map-sets are scored
proportionally, so produce every map you can support and omit the rest.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the physics and conventions common to all subjects: the SPGR **signal
model**, the **B1+ convention** (`a = B1 × radians(flip_deg)`, applied wherever a flip angle
enters), and the exact definitions of the graded quantities. Read it before you start. The
estimators are the standard MPM / hMRI-toolbox ones:

- **R2\*** — the **ESTATICS** joint log-linear fit (Weiskopf et al. 2014): one shared R2\*
  across all of a subject's echo trains with a separate log-intercept per contrast.
- **R1 / PD** — the **rational (small-flip-angle) SPGR variable-flip-angle** solve: regress
  `a_c / S0_c` on `a_c² / TR_c` across the flip-angle (non-MT) contrasts; intercept = `1/A`,
  slope = `1/(2·A·R1)`. `PD_norm` is the proton-density amplitude divided by its white-matter
  median (absolute PD carries an ungradeable receive-scale convention).
- **MTsat** — the **Helms et al. 2008** saturation, in percent units (p.u.):
  `δ = R1·TR_mt·(A·a_mt / S0_mt − 1) − a_mt²/2`, reported ×100.

The planted physiology reproduces literature 3 T quantitative values (white matter
R1 ≈ 1.05 s⁻¹, R2\* ≈ 22 s⁻¹, MTsat ≈ 3 p.u., PD ≈ 70 % of CSF), with per-field, per-tissue
variation.

## Robustness / data-quality contract  (READ THIS)
The signals are realistic, not clean:

- **B1+ transmit inhomogeneity.** Some subjects have a strongly non-uniform transmit field
  (`b1.npy`). The true flip angle is `a = B1 × radians(flip_deg)`; ignoring B1+ biases R1,
  PD and MTsat. Apply it everywhere a flip angle enters.
- **Grossly corrupted echoes.** In a **minority of subjects, one or two individual echo
  volumes are grossly corrupted** (e.g. by motion) and are physically inconsistent with the
  mono-exponential decay of the rest of that subject's echo train. **You must detect and
  reject such corrupted echoes robustly before fitting** R2\* and the TE=0 intercepts.
  *Which* subjects and *which* echoes are affected is **not disclosed** — you must find them
  from the data. Any scientifically valid robust scheme is acceptable (robust regression,
  outlier rejection on the log-signal residuals, etc.); a non-robust fit over all echoes will
  recover the wrong R2\* and intercepts on the affected subjects and fail those panels.

Rician noise (modest) is present on every echo and does **not** need special handling beyond
an ordinary fit.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `field_T`, `f0_mhz`, `n_vox`, and a `contrasts` list; each contrast gives
  `name`, `mt_weighted`, `flip_deg` (nominal), `tr_ms`, `te_ms` (the echo times), and the
  `file` holding its signal.
- one `<name>.npy` per contrast — a float32 array of shape `(n_echoes, n_vox)`: the magnitude
  SPGR signal, one row per echo, in the subject's voxel order.
- `b1.npy` — the per-voxel transmit factor B1 (shape `(n_vox,)`, 1.0 = nominal).
- `tissue.npy` — per-voxel tissue label (shape `(n_vox,)`; see the protocol legend, white
  matter = 2).
- `mask.npy` — the brain mask (shape `(n_vox,)`; maps are graded over these voxels).

## Computability (which maps to write per subject)
Decide **from the acquisition**, not from any label:
- **R2\*** — only when at least one contrast is **multi-echo**. A single-echo subject cannot
  constrain R2\*; **omit it**.
- **MTsat** — only when an **MT-weighted contrast is present**; otherwise **omit it**.
- **R1, PD_norm** — always computable from the flip-angle contrasts.

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **computable** map, each of shape `(n_vox,)` in the subject's
voxel order:
- `R1.npy` — longitudinal relaxation rate (1/s).
- `PD_norm.npy` — white-matter-normalised proton density (dimensionless).
- `R2star.npy` — effective transverse relaxation rate (1/s) — **only where determinable**.
- `MTsat.npy` — magnetization-transfer saturation (p.u.) — **only where determinable**.

Do **not** write a file for a map the subject's protocol cannot support — writing an
unsupported map fails that panel.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for
the maps you can produce so the rest of the cohort can be graded.
