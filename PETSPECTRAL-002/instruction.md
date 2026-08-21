# Spectral analysis of a dynamic-PET cohort

## Task
`/app/data/` holds a cohort of dynamic-PET exams (`sub-01` … `sub-08`) of a reversible tracer.
For each subject you are given the region time-activity curves (TACs) and the input data needed
to quantify them. Fit a **non-negative spectrum of exponential kinetic components** to each
region's TAC and report the per-region macro-parameters defined below.

The cohort is **heterogeneous**: each subject's sidecar declares its `input_type` and lists its
files, and you must adapt the analysis per subject — some subjects provide an arterial **plasma**
input while others provide only a **reference-region** TAC, and the two require different models
and support different outputs. **Compute a quantity only where the subject's data determine it;
where they do not, omit it.**

Grading is **outcome-based and per-region**: each quantity you write is recomputed from the TACs
by a held-out reference and compared region-by-region. Partial cohorts and partial output sets
are scored proportionally, so produce every quantity you can support and omit the rest.

## Shared physics and output contract (`/app/data/protocol.json`)
Read this first. It pins, for the whole cohort:
- the two **signal models** — the plasma-input spectral model
  `C_T(t) = Σ_j α_j · (Cp ∗ e^(−β_j·t))(t)` and the reference-input model
  `C_T(t) = R1·C_ref(t) + Σ_j α_j · (C_ref ∗ e^(−β_j·t))(t)`, with all coefficients ≥ 0;
- the **β grid** (`beta_grid.values_per_min`) — the exact log-spaced kinetic-rate basis to use;
- the **frame model** — a frame's model value is the frame-average of the continuous curve over
  `[t_start, t_end]`, integrated on the pinned fine time grid;
- the **weighting** — weighted least squares with `w_i = frame_duration_i`;
- the exact **quantity definitions** and **units** (see below);
- the **output contract** — which files to write per input type, and which to omit.

## Graded quantities (per region, in the sidecar's region order)
- **VT** (`mL/cm^3`, plasma-input subjects) — total volume of distribution `= Σ_j α_j/β_j`.
- **K1** (`mL/min/cm^3`, plasma-input subjects) — the impulse-response flow `= IRF(0⁺) = Σ_j α_j`.
- **DVR** (dimensionless, reference-input subjects) — distribution-volume ratio
  `= R1 + Σ_j α_j/β_j`.
- **R1** (dimensionless, reference-input subjects) — relative delivery = the direct `C_ref` coefficient.

Absolute VT and K1 are **not identifiable** without an arterial input, so for a reference-input
subject report only DVR and R1 (omit VT and K1); for a plasma-input subject report only VT and K1
(omit DVR and R1).

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `input_type` (`plasma` or `reference`), `n_frames`, `n_regions`, `region_ids`,
  and the `files` map.
- `frames.npy` — `(n_frames, 2)` array of `[t_start, t_end]` in minutes.
- `tacs.npy` — `(n_frames, n_regions)` region TACs (decay-corrected concentration), in region order.
- `plasma.npy` — *plasma-input subjects only* — `(n_blood, 2)` array of `[t_min, Cp]` arterial samples.
- `reference.npy` — *reference-input subjects only* — `(n_frames,)` reference-region TAC.

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **computable** quantity, each of shape `(n_regions,)` in the sidecar's
region order:
- plasma-input subject → `VT.npy`, `K1.npy`
- reference-input subject → `DVR.npy`, `R1.npy`

Do **not** write a file for a quantity the subject's input type cannot support.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for the
quantities you can produce so the rest of the cohort can be graded.
