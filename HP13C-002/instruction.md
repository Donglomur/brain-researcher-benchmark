# Kinetic mapping of a hyperpolarized 13C-pyruvate dynamic cohort

## Task
`/app/data/` holds a cohort of dynamic hyperpolarized [1-13C]pyruvate exams
(`sub-01` … `sub-08`). Each subject was imaged as a time-series of 13C metabolite signals as
injected pyruvate converts to its downstream products. From these signals, estimate the
per-voxel **apparent conversion rate maps** and write them out.

The cohort is **heterogeneous**: every subject's sidecar declares the metabolites it actually
acquired, its relaxation constants, its per-frame excitation, and how the pyruvate was
delivered, and you must adapt the analysis per subject — a pipeline that assumes one fixed
recipe will not fit them all. **Estimate a rate only where the subject's acquisition determines
it; where it does not, omit that map.** There is no reference fitter provided — implement the
kinetic estimator yourself and get the model, units, and per-subject adaptation right.

Grading is **outcome-based and voxelwise against the true underlying kinetics**: each map you
write is compared voxel-by-voxel, inside the brain mask, to the *true* apparent rate that
generated the signals (the reference fit on the noise-free, corruption-free signal). **Any
scientifically valid estimator is accepted** — a different forward integrator, a different
optimiser, a different gross-frame detector — because every correct method recovers the same
apparent rate within tolerance. You are **not** required to reproduce any particular reference
implementation's output. Partial cohorts and partial map sets are scored proportionally, so
produce every map you can support and omit the rest.

## Shared kinetic model and output contract (`/app/data/protocol.json`)
A single JSON with the physics and conventions common to all subjects: the two-/three-site
**kinetic model** (the rate matrix relating pyruvate → lactate → bicarbonate), the **acquisition
model** (how the sampled signal relates to the longitudinal magnetization through the per-frame
flip angle, with RF depletion between frames), the **inflow convention** (how a provided vascular
input function versus a compact bolus enters the model), the exact **estimator** definition for
the rate constants (a signal-domain least-squares fit with the common signal amplitude profiled
out), the **units**, and the **tissue legend**. Read it before you start.

## Robustness / data-quality contract  (READ THIS)
The signals are realistic, not clean. Four things must be handled per subject (their per-subject
realisation is declared in each sidecar or must be found in the data):

- **Inflow model.** A subject imaged during a **continuous infusion** provides a `vif_file`; the
  forward model must be **driven by that inflow**. A subject given a **compact bolus** has no VIF
  and is a **closed system** decaying from its initial magnetization. Using the wrong inflow model
  biases kPL by ~40–50%.
- **Site count.** A subject that resolves a **bicarbonate channel** needs the **three-site** model
  (fit kPL and kPB); a **pyruvate+lactate-only** subject needs the **two-site** model (fit kPL;
  **omit** kPB). Fitting a two-site model to three-site data mis-attributes the →HCO3 loss and
  biases kPL — the model choice is coupled, not cosmetic.
- **Fixed relaxation and excitation.** The per-subject **T1 constants** and **per-frame flip
  angles** are given and must be threaded into the discrete kinetic model (wrong T1 / flips →
  biased rate).
- **Grossly corrupted dynamic frames.** In a **majority of subjects, one or two individual
  dynamic frames are grossly corrupted** (an RF-spike or signal-dropout timepoint) and are
  inconsistent with the smooth kinetic time-course. **You must detect and reject such frames
  robustly before the fit.** *Which* subjects and *which* frames are affected is **not
  disclosed** — find them from the data. Every subject's late frames are additionally low-SNR as
  the hyperpolarization decays (an ordinary fit handles this; no special treatment needed).

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `tr_s`, `n_frames`, `n_vox`, `times_s`, an `inflow` tag, and a `metabolites`
  list; each metabolite gives its `name`, `T1_s`, the per-frame `flip_deg`, and the `file`
  holding its signal. If the subject was imaged during a continuous infusion the sidecar also
  names a `vif_file`.
- one `<name>.npy` per metabolite — a float32 array of shape `(n_frames, n_vox)`: the magnitude
  13C signal, one row per dynamic frame, in the subject's voxel order.
- `vif.npy` (infusion subjects only) — the inflow shape into pyruvate, shape `(n_frames,)`,
  arbitrary units.
- `tissue.npy` — per-voxel tissue label (shape `(n_vox,)`; see the protocol legend).
- `mask.npy` — the brain mask (shape `(n_vox,)`; maps are graded over these voxels).

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **determinable** rate map, each of shape `(n_vox,)` in the subject's
voxel order:
- `kPL.npy` — apparent pyruvate → lactate conversion rate (1/s).
- `kPB.npy` — apparent pyruvate → bicarbonate conversion rate (1/s) — **only where a bicarbonate
  channel is resolved**.

Do **not** write a file for a map the subject's protocol cannot support.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for the
maps you can produce so the rest of the cohort can be graded.
