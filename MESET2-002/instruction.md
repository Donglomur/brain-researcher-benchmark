# EPG-corrected T2 mapping of a heterogeneous multi-echo spin-echo cohort

## Task
`/app/data/` holds a cohort of quantitative T2-mapping exams (`sub-01` … `sub-08`). Each
subject was scanned with a single **CPMG multi-echo spin-echo** train (one 90° excitation
followed by a train of nominally-180° refocusing pulses). From each echo train, estimate the
per-voxel **quantitative maps** and write them out.

The cohort is **heterogeneous**: every subject's sidecar declares its own acquisition (echo
spacing, number of echoes, echo times, nominal flips, assumed T1), and you must adapt the
analysis per subject — a pipeline that assumes one fixed recipe will not fit them all.
**Compute a map only where the subject's acquisition determines it; where it does not, omit
that map.** There is no reference fitter provided — implement the estimators yourself and get
the spin-physics, units, and per-subject adaptation right.

Grading is **outcome-based and voxelwise**: each map you write is recomputed from the echo
train by a held-out reference and compared voxel-by-voxel inside the brain mask. Partial
cohorts and partial map sets are scored proportionally, so produce every map you can support
and omit the rest.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the physics and conventions common to all subjects: the **CPMG signal
model** (an ideal 90° excitation, then refocusing pulses of `kappa × refocus_deg`, with the
train modelled by the **Extended Phase Graph** — when refocusing is imperfect the train is
**not** mono-exponential), and the exact definitions of the graded quantities:

- **T2** (ms) — the single-component transverse relaxation time from the EPG stimulated-echo
  fit (the `(kappa, T2, amplitude)` that best fit the train under the signal model, amplitude
  projected out, with T1 fixed at the sidecar's `assumed_t1_ms`; T2 is essentially insensitive
  to that T1). Determinable for every subject.
- **flip** (degrees) — the fitted **effective refocusing flip angle** `kappa × refocus_deg`.
  Identifiable only from a long-enough train: co-estimate it when `n_echoes ≥ flip_min_echoes`
  (given in the protocol); when the train is shorter the flip is **not** identifiable, so
  assume nominal refocusing (`kappa = 1`, a mono-exponential T2) and **omit** the flip map.
- **M0_norm** (dimensionless) — the fitted amplitude divided by its **white-matter median**
  (tissue label 2); absolute amplitude carries the receive scale and is not graded.

Read `protocol.json` before you start — it fixes the excitation/refocusing convention, the
decay-only EPG relaxation model, the unit of each quantity, and the tissue legend.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `field_T`, `n_vox`, `n_echoes`, `esp_ms` (echo spacing), `te_ms` (the echo
  times), `excitation_deg`, `refocus_deg` (nominal), `assumed_t1_ms`, and the file names below.
- `mese.npy` — a float32 array of shape `(n_echoes, n_vox)`: the magnitude CPMG echo train,
  one row per echo, in the subject's voxel order.
- `tissue.npy` — per-voxel tissue label (shape `(n_vox,)`; see the protocol legend, white
  matter = 2).
- `mask.npy` — the brain mask (shape `(n_vox,)`; maps are graded over these voxels).

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **computable** map, each of shape `(n_vox,)` in the subject's
voxel order:
- `T2.npy` — transverse relaxation time (ms).
- `M0_norm.npy` — white-matter-normalised amplitude (dimensionless).
- `flip.npy` — fitted effective refocusing flip angle (degrees) — **only where determinable**.

Do **not** write a file for a map the subject's acquisition cannot support.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for
the maps you can produce so the rest of the cohort can be graded.
