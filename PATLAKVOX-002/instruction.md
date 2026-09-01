# Voxelwise Patlak parametric imaging of a dynamic brain-PET cohort

## Task
`/app/data/` holds a cohort of dynamic brain-PET exams (`sub-01` … `sub-08`). Each subject was
scanned with one radiotracer and reconstructed into per-voxel **time-activity curves (TACs)** over
the acquisition frames. For every subject, estimate the per-voxel **parametric map(s)** the
acquisition supports and write them out.

The cohort is **heterogeneous**: the tracer, isotope, frame schedule, the graphical-analysis start
time, and what was measured (an arterial input function, or only a reference region) differ from
subject to subject, and within a plasma-input subject a voxel may be irreversibly trapping or
reversible — so **a single fixed Patlak recipe will not fit every subject or every voxel**. No
fitting code is provided; implement the estimators yourself and get the physics, units, decay, and
per-subject / per-voxel adaptation right.

Grading is **outcome-based and voxelwise against the true underlying kinetics**: each map you
write is compared voxel-by-voxel, inside the brain mask, to the *planted* parametric map that
generated the TACs. **Any scientifically valid estimator is accepted** — Gjedde-Patlak, plasma
Logan, Ichise MA1 or a 2-tissue-compartment fit for the plasma maps; multilinear reference-Patlak
for Ki_ref; whichever robust motion-frame repair you prefer — because every correct method
recovers the same macro-parameters within tolerance. You are **not** required to reproduce any
particular reference implementation's output. Partial cohorts and partial maps are scored
proportionally, so produce every map you can support and omit the rest.

## Shared physics and output contract (`/app/data/protocol.json`)
Read it first. It gives the conventions common to all subjects: the **time units** (minutes; rates
per minute), the **decay-correction** convention (TACs and blood/plasma are stored *without* decay
correction — decay-correct every value to injection time with the isotope half-life before
analysis), how the **metabolite-corrected arterial parent plasma** is assembled from the arterial
file when one is present, the **reference-region** input convention when one is not, the
`t_star_min` graphical-analysis window, and the exact definitions of the three graded quantities:

- **Ki** — Gjedde-Patlak net influx rate constant (mL/min/mL) of a plasma-input, irreversibly
  **trapping** voxel: the slope of `C_T(t)/Cp(t)` vs `∫₀ᵗ Cp dτ / Cp(t)` over the `t ≥ t*` frames
  (equivalently a 2-tissue-compartment fit with `k4 = 0`, `Ki = K1·k3/(k2+k3)`).
- **VT** — total distribution volume (mL/mL) of a plasma-input **reversible** voxel (the same value
  is returned by plasma Logan, Ichise MA1, or a 2-tissue-compartment fit).
- **Ki_ref** — reference-Patlak relative net influx (1/min) of a reference-input, irreversibly
  trapping voxel: the slope of `C_T(t)/C_R(t)` vs `∫₀ᵗ C_R dτ / C_R(t)` over the `t ≥ t*` frames,
  with `C_R` the reference-region mean TAC.

## Robustness / data-quality contract  (READ THIS)
The TACs are realistic, not clean:

- **Grossly motion-corrupted frames.** In a **subset of the subjects, a few whole frames are
  grossly corrupted** by head motion — the frame's activity is a gross outlier of the smooth
  tracer time-course (an abrupt jump or drop across the whole field of view). They sit in the
  **late, highest-leverage part of the graphical-analysis window**, so a single corrupted frame
  left in place biases the fitted slope well past tolerance. **You must detect and repair (or
  reject) such frames robustly before forming any integral or fitting any slope.** *Which*
  subjects and *which* frames are affected is **not disclosed** — you must find them from the
  data, and there may be **more than one per subject**, so a one-pass "drop the single worst
  frame" fix is not enough; iterate until the retained frames are mutually consistent. Some
  subjects are clean. Any scientifically valid robust scheme is acceptable (iterative gross-
  outlier detection on the global activity trend, robust regression, etc.); a non-robust fit over
  all frames recovers the wrong parameters on the affected subjects and fails those panels.

Ordinary counting noise is present on every frame and does **not** need special handling beyond
the standard graphical/compartmental fit.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `isotope`, `half_life_min`, the frame schedule (`frame_start_min`,
  `frame_dur_min`), `t_star_min`, `input_kind` (`"plasma"` or `"reference"`), `region_labels`
  (region name → integer label), `n_vox`, and either an `aif_file` (when `input_kind` is
  `"plasma"`) **or** a `reference_region` name (when it is `"reference"`).
- `tac.npy` — a float32 array of shape `(n_frames, n_vox)`: per-voxel activity in `kBq/mL`, in
  voxel order, **not** decay-corrected.
- `mask.npy` — the brain mask (shape `(n_vox,)`; maps are graded over these voxels).
- `region.npy` — an anatomical region label per voxel (shape `(n_vox,)`); it does **not** encode
  kinetic type.
- `plasma.json` (only when `aif_file` is set) — the arterial samples: `plasma_time_min`,
  `whole_blood_kbq_ml` (not decay-corrected), `parent_fraction`, and `plasma_to_blood_ratio`.

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **supported** map, each of shape `(n_vox,)` in voxel order:
- `ki.npy` — Ki (mL/min/mL), plasma-input subjects.
- `vt.npy` — VT (mL/mL), plasma-input subjects.
- `kiref.npy` — Ki_ref (1/min), reference-input subjects.

Within a map, write the value at each voxel the quantity applies to and **NaN** at every other
voxel — a reversible voxel is NaN in `ki.npy`, a trapping voxel is NaN in `vt.npy`, and the
reference region is NaN in `kiref.npy`. Do **not** write a file for a map the subject's input type
does not support (a plasma subject has no `kiref.npy`; a reference subject has no `ki.npy`/`vt.npy`).

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for the
maps you can produce so the rest of the cohort can be graded.
