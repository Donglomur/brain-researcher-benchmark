# LCMV beamformer source reconstruction of a heterogeneous MEG cohort

## Task
`/app/data/` holds a MEG cohort (`sub-01` … `sub-08`). Each subject was recorded in one or more
measurement **conditions**; for each condition you are given the per-epoch sensor covariances,
together with a single empty-room noise covariance, a fixed-orientation lead field, and the
source grid. From these, reconstruct the per-source **neural activity index (NAI)** with a
linearly-constrained-minimum-variance (LCMV) beamformer and write it out.

The cohort is **heterogeneous**: each subject's sidecar declares which conditions were acquired
and the array dimensions, and the sensor data were preprocessed differently from subject to
subject, so a single fixed recipe (or a plain matrix inverse) will not fit them all — read each
sidecar and adapt. **Compute a map only where the subject's acquisition determines it; where it
does not, omit that map.**

Grading is **outcome-based and per-source**: each NAI map you write is recomputed from the
covariances by a held-out reference and compared source-by-source over the grid. Partial
cohorts and partial condition sets are scored proportionally, so produce every map you can
support and omit the rest.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the conventions common to all subjects: the covariance / lead-field / noise
file layout, the **rank convention** (invert the data covariance on its numerical rank — a
truncated Moore–Penrose inverse — because some subjects' covariances are rank-reduced), the
exact **NAI definition**, and the output spec. Read it before you start.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `n_chan`, `n_src`, `n_epoch`, the `conditions` list, and the file names for
  each condition's epoch covariances, the noise covariance, the lead field, and the grid.
- `cov_epochs_<cond>.npy` — float32 `(n_epoch, n_chan, n_chan)`: the per-epoch sensor
  covariances for condition `<cond>` (in the subject's channel order).
- `noise_cov.npy` — float32 `(n_chan, n_chan)`: the empty-room sensor-noise covariance `N`.
- `leadfield.npy` — float32 `(n_chan, n_src)`: column `r` is the fixed-orientation lead vector
  `L(r)` (its per-column scale and sign are arbitrary).
- `grid.npy` — float32 `(n_src, 3)`: source positions (metres).

## The graded quantity
For each source `r`, the **neural activity index**

```
NAI(r) = ( L(r)^T C^+ L(r) ) / ( L(r)^T C^+ N C^+ L(r) )
```

where `C` is the condition's data covariance (the equal-weight average of its epoch
covariances), `C^+` is the inverse of `C` taken over its numerical rank (see the protocol's
rank convention), and `N` is the empty-room noise covariance. Equivalently
`NAI = (w^T C w) / (w^T N w)` for the unit-gain LCMV weights `w = C^+ L / (L^T C^+ L)`. NAI is
dimensionless and is invariant to each lead-field column's scale and sign.

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **acquired** condition, each of shape `(n_src,)` in grid order:
- `nai_A.npy` — the NAI for condition A.
- `nai_B.npy` — the NAI for condition B — **only where condition B was acquired**.

Do **not** write `nai_B.npy` for a subject whose sidecar lists no condition B.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for
the maps you can produce so the rest of the cohort can be graded.
