# Myelin water fraction from an EPG-corrected multi-echo-T2 cohort

## Task
`/app/data/` holds a cohort of quantitative multi-echo spin-echo (CPMG) exams
(`sub-01` … `sub-08`). Each subject was scanned with a single multi-echo T2 decay per voxel.
From these decays, estimate the per-voxel **myelin water fraction (MWF)** and, where the
acquisition supports it, the spectrum's **geometric-mean T2 (gmT2)**, and write them out.

The cohort is **heterogeneous**: every subject's sidecar declares its own acquisition (number
of echoes, echo spacing, nominal refocusing flip angle, the transmit map), and you must adapt
the analysis per subject — a pipeline that assumes one fixed recipe will not fit them all.
**Compute a map only where the subject's acquisition determines it; where it does not, omit
that map.** There is no reference fitter provided — implement the estimator yourself and get
the spin physics, the regularized inversion, the units, and the per-subject adaptation right.

## What is graded
Grading is **outcome-based and voxelwise against the true underlying physiology**. Each map you
write is compared voxel-by-voxel, inside the brain mask, to the *true* value the pinned model
determines from the signal (the artifact-free reference value). Because the T2 spectrum
inversion is ill-posed, the graded MWF/gmT2 are the values of the **pinned, convention-fixed**
inversion (grid, regularization weight, MWF cutoff, gmT2 window all pinned in the protocol);
**any scientifically valid estimator that implements the pinned physics is accepted** — an
isochromat Bloch or EPG basis, any bounded-variable NNLS solver, any gross-echo detector —
because they all recover the same value within tolerance. You are **not** required to reproduce
any particular reference implementation's output. Each (subject × map) is scored independently
and partial cohorts and partial map sets are scored proportionally, so produce every map you can
support and omit the rest.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the physics and conventions common to all subjects. Read it before you
start. It pins, exactly:
- the **CPMG sequence** and the per-voxel **true refocusing flip** `alpha = B1 × radians(refocus_deg)`;
- the **signal model** `s[j] = Σ_k x_k · EPG(TE_j; T2_k, alpha)` — an extended-phase-graph
  (EPG) CPMG echo amplitude for each T2 component at the true refocusing flip (this is what
  makes the decay non-mono-exponential when the refocusing flip departs from 180°), with a
  fixed `T1 = 1000 ms` and no equilibrium recovery, so `s = A x` is linear in the non-negative
  component amplitudes `x`;
- the **spectrum fit**: the pinned T2 grid (40 log-spaced values, 10–2000 ms) and the pinned
  first-derivative-regularized non-negative least squares (fixed weight `mu = 1.5`);
- the **MWF** definition (short-T2 fraction, cutoff 40 ms), the **gmT2** definition
  (amplitude-weighted geometric-mean T2 over 40–200 ms), and the pinned **3-pool model** used
  for acquisitions that cannot resolve a spectrum.

## Robustness / data-quality contract  (READ THIS)
The signals are realistic, not clean:

- **Grossly corrupted echoes.** In a **majority of subjects, one or two individual echo volumes
  are grossly corrupted** (e.g. by motion — a large spike or drop-out) and are physically
  inconsistent with the CPMG decay of the rest of that subject's echo train. **You must detect
  and reject such corrupted echoes robustly before the regularized inversion** (or the 3-pool
  fit); a fit that keeps them recovers the wrong spectrum and a wrong MWF/gmT2. *Which* subjects
  and *which* echoes are affected is **not disclosed** — you must find them from the data. Any
  scientifically valid robust scheme is acceptable.
- **Imperfect refocusing.** Several subjects have a nominal refocusing flip below 180°, scaled
  per voxel by the transmit map `b1.npy`; the true flip `alpha = B1 × radians(refocus_deg)`
  drives stimulated echoes, so the decay is **not** mono-exponential. Use the EPG basis at the
  true per-voxel flip — a plain `exp(-TE/T2)` basis biases the MWF.
- **Rician noise** (modest) is present on every echo and does **not** need special handling
  beyond the ordinary regularized fit.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `n_echoes`, `esp_ms` (echo spacing), `te_ms` (the echo times),
  `refocus_deg` (nominal refocusing flip), `n_vox`, and the file names below.
- `signal.npy` — a float32 array of shape `(n_echoes, n_vox)`: the CPMG magnitude decay, one
  row per echo, in the subject's voxel order.
- `b1.npy` — the per-voxel transmit factor B1 (shape `(n_vox,)`, 1.0 = nominal).
- `tissue.npy` — per-voxel tissue label (shape `(n_vox,)`; see the protocol legend).
- `mask.npy` — the brain mask (shape `(n_vox,)`; maps are graded over these voxels).

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **computable** map, each of shape `(n_vox,)` in the subject's
voxel order:
- `MWF.npy` — myelin water fraction (dimensionless, in [0, 1]) — for every subject.
- `gmT2.npy` — geometric-mean T2 of the spectrum (ms) — **only where determinable**.

Do **not** write a file for a map the subject's acquisition cannot support.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for
the maps you can produce so the rest of the cohort can be graded.
