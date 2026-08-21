# Quantitative T1rho dispersion of a heterogeneous spin-lock cohort

## Task
`/app/data/` holds a cohort of rotating-frame (spin-lock, T1rho) relaxometry exams
(`sub-01` … `sub-08`). Each subject was scanned over a set of **spin-lock frequencies** (FSL,
the spin-lock amplitude in Hz); at every FSL a short **spin-lock-time** (TSL) series was
acquired. From these signals, estimate the per-voxel rotating-frame relaxation rate and its
**chemical-exchange dispersion**, and write the maps out.

The cohort is **heterogeneous**: every subject's sidecar declares the spin-lock frequencies it
actually sampled, and the number of distinct frequencies decides which quantities its data can
support — so a pipeline that assumes one fixed recipe will not fit them all. **Report a quantity
only where the subject's sampling determines it; where it does not, omit that map.** There is no
reference fitter provided — implement the estimators yourself and get the model, units, and
per-subject adaptation right.

Grading is **outcome-based and voxelwise**: each map you write is recomputed from the signals by
a held-out reference and compared voxel-by-voxel. Partial cohorts and partial map sets are scored
proportionally, so produce every map you can support and omit the rest.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the physics and conventions common to all subjects: the mono-exponential
spin-lock **signal model** at each frequency, the chemical-exchange **dispersion model**, the
**determinability rule** (how the number of distinct spin-lock frequencies decides whether the
dispersion is fittable), the exact **estimator definitions**, the **reference spin-lock
frequency**, the **unit** of each quantity, the **grading region**, and the **tissue legend**.
Read it before you start. In particular:

- At each spin-lock frequency the series is mono-exponential in TSL,
  `S(TSL) = S0 · exp(−R1rho · TSL)`, with **TSL in ms** and **R1rho a RATE in 1/s**.
- R1rho disperses with the spin-lock amplitude by chemical exchange,
  `R1rho(ω1) = R1rho_inf + Rex / (1 + (ω1·τ)²)`, where `ω1 = 2π·FSL` (rad/s). **R1rho_inf** (1/s)
  is the exchange-independent, high-amplitude floor and **Rex** (1/s) is the **dispersion
  amplitude** `= R1rho(0) − R1rho_inf`. These two asymptotes are the graded dispersion
  quantities; they are invariant to how the frequency axis is scaled, and the correlation time τ
  is **not** graded.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `fsl_hz` (the distinct spin-lock frequencies), `fsl_ref_hz` (the common
  reference frequency, sampled by every subject), `tsl_ms` (the spin-lock times), `n_vox`, and the
  `signal_file` / `tissue_file` / `mask_file` names.
- `signal.npy` — a float32 array of shape `(n_fsl, n_tsl, n_vox)`: the magnitude spin-lock signal
  at each (spin-lock frequency, spin-lock time), in the subject's voxel order.
- `tissue.npy` — per-voxel tissue label (shape `(n_vox,)`; see the protocol legend, GM = 1,
  WM = 2, CSF = 3).
- `mask.npy` — the brain mask (shape `(n_vox,)`).

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **determinable** map, each of shape `(n_vox,)` in the subject's
voxel order:
- `R1rho_ref.npy` — R1rho (1/s) at the reference spin-lock frequency `fsl_ref_hz` — **always**.
- `R1rho_inf.npy` — exchange-independent dispersion floor (1/s) — **only where the dispersion is
  determinable**.
- `Rex_amp.npy` — dispersion amplitude (1/s) — **only where the dispersion is determinable**.

Do **not** write a file for a map the subject's spin-lock sampling cannot support. Maps are graded
over parenchyma voxels (GM and WM); CSF and background are excluded.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for the
maps you can produce so the rest of the cohort can be graded.
