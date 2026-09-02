# Multi-pool CEST quantification of a heterogeneous Z-spectrum cohort

## Task
`/app/data/` holds a cohort of chemical-exchange-saturation-transfer (CEST) exams
(`sub-01` … `sub-08`). Each subject was scanned with a saturated-signal stack over a set of
frequency offsets (a **Z-spectrum**). From these signals, estimate the per-voxel **exchange-pool
amplitudes** and write them out.

The cohort is **heterogeneous**: every subject's sidecar declares the saturation offsets it
actually acquired, and you must adapt the analysis per subject — **compute a pool's amplitude
only where the subject's sampling can identify it; where it cannot, omit that map.**

Grading is **outcome-based and voxelwise**: each amplitude map you write is compared
voxel-by-voxel, inside the brain mask, against a **held-out target** — the amplitudes the
**fully-specified pinned model below** produces on these exact signals. **Any scientifically
valid implementation of that pinned estimator is accepted** (the grader runs no reference code
and prefers no particular linear-algebra library); because the pool centres and widths are
fixed, the amplitudes are the unique ordinary-least-squares coefficients of a fixed linear basis,
so an SVD pseudo-inverse, a QR solve, the normal equations, or any equivalent recover the same
values. Partial map sets are scored proportionally, so produce every map you can support and
omit the rest.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the physics and conventions common to all subjects. **Read it before you
start.** It pins:

- the **Z normalisation** `Z = S / S0`;
- the **pinned pool model** — a fixed 4-pool Lorentzian, `Z(dw) = 1 - eta * Σ_i A_i ·
  L(dw - B0; delta_i, W_i)` with `L(x; delta, W) = 1 / (1 + (2·(x - delta)/W)²)` and the
  **fixed** centres `delta_i` and widths `W_i` of the water, MT, amide (+3.5 ppm) and NOE
  (-3.6 ppm) pools (centres and widths are fixed — only the per-voxel amplitudes are free);
- the **graded quantity** — the amplitudes `A_i` are the **ordinary least-squares** coefficients
  of that fixed Lorentzian basis (with `y = (1 - Z)/eta` and design column `M_ik =
  L(dw_k - B0; delta_i, W_i)`, solved per voxel); report `A_amide` and `A_noe`;
- the **B0 convention** (`dw_true = dw_nominal - B0`, `b0.npy` in ppm) and the **B1 convention**
  (`eta` = the per-voxel saturation-efficiency factor in `b1.npy`; divide it out);
- the **identifiability rule** deciding, from a subject's acquired offsets, which CEST pools are
  determinable (and which must be omitted), and the exact **output spec**.

## Robustness / data-quality contract (READ THIS)
The saturation stacks are **not clean**. A subset of the subjects carry one or two **grossly
motion-corrupted saturation frames** — a whole offset image scaled up or down by a large factor
— mixed in among the good frames. These corrupted frames are **gross, unambiguous outliers**
(their per-voxel signal is off by tens of percent to several-fold, far outside the noise), and
they will **badly bias the fitted amplitudes** if left in. You must **detect and reject them per
subject before the least-squares fit** (any robust criterion works — the corrupted frames stand
out dramatically from the smooth Z-spectrum; the held-out target is the pinned fit with exactly
those gross outliers removed). **Which subjects are affected, and which frames, is not
disclosed** — discover it from the data. Do **not** discard clean frames: throwing away good
saturation offsets changes the fit and is itself an error. Subjects with no corrupted frames
need no rejection.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `field_T`, `f0_mhz`, `n_vox`, `n_offset`, the `offsets_ppm` list, and the
  file names below.
- `sat.npy` — the saturated signal, a float32 array of shape `(n_offset, n_vox)`, one row per
  acquired offset, in the subject's voxel order.
- `S0.npy` — the unsaturated reference signal (shape `(n_vox,)`).
- `b0.npy` — per-voxel B0 offset in ppm (shape `(n_vox,)`).
- `b1.npy` — per-voxel saturation-efficiency factor `eta` (shape `(n_vox,)`, 1.0 = nominal).
- `tissue.npy` — per-voxel tissue label (shape `(n_vox,)`; see the protocol legend).
- `mask.npy` — the brain mask (shape `(n_vox,)`; amplitudes are graded over these voxels).

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **identifiable** CEST pool, each of shape `(n_vox,)` in the
subject's voxel order:
- `amide.npy` — the amide/APT pool amplitude (+3.5 ppm) — **only where determinable**.
- `noe.npy` — the NOE pool amplitude (-3.6 ppm) — **only where determinable**.

Do **not** write a file for a pool the subject's sampling cannot identify.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for
the pools you can produce so the rest of the cohort can be graded.
