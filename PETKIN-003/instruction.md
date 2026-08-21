# Kinetic quantification of a dynamic brain-PET cohort

## Task
`/app/data/` holds a cohort of dynamic brain-PET exams (`sub-01` … `sub-08`). Each subject was
scanned with one radiotracer; you are given regional **time-activity curves (TACs)** over the
acquisition frames. For every subject, quantify each region's **binding / kinetic parameter**
and write it out.

The cohort is **heterogeneous**: the tracer, isotope, frame schedule, and what was measured
(an arterial input function, or only a reference region) differ from subject to subject, and
you must adapt the analysis accordingly — **a single fixed quantification recipe will not fit
all subjects.** No fitting code is provided; implement the kinetic estimators yourself and get
the physics, constants, and per-subject/per-region choice of model right.

Grading is **outcome-based**: each quantity you report is recomputed from the TACs by a
held-out reference and compared within a tolerance. Partial cohorts are scored proportionally,
so quantify every region you can and report each under the single quantity its data support.

## Shared physics and output contract (`/app/data/protocol.json`)
Read it first. It gives the conventions common to all subjects: the **time units** (minutes;
rates per minute), the **decay-correction** convention (TACs and blood/plasma are stored
*without* decay correction — decay-correct every value to injection time with the isotope
half-life before analysis), the **frame-duration weighting** of fits, how the
**metabolite-corrected arterial parent plasma** is assembled from the arterial file when one is
present, the `t_star_min` linear-analysis window, and the exact **definitions** of the three
graded quantities:

- **BPND** — non-displaceable binding potential of a reversible reference-tissue ligand
  (`BPND = DVR − 1`), a convention-invariant equilibrium ratio.
- **VT** — total distribution volume (mL/cm³) of a reversible plasma-input tracer.
- **Ki** — irreversible net influx rate constant (mL/cm³/min) of a trapping plasma-input tracer.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `tracer`, `isotope`, `half_life_min`, the frame schedule
  (`frame_start_min`, `frame_dur_min`), `region_names` (the column order of `tac.npy`),
  `t_star_min`, and either a designated `reference_region` (with its efflux constant
  `reference_k2prime_per_min`) **or** an `aif_file` giving the arterial input — depending on
  what the exam measured.
- `tac.npy` — a float64 array of shape `(n_frames, n_regions)`: the regional activity in
  `kBq/mL`, in `region_names` order, **not** decay-corrected.
- `plasma.json` (only when `aif_file` is set) — the arterial samples: `plasma_time_min`,
  `whole_blood_kbq_ml` (not decay-corrected), `parent_fraction`, and `plasma_to_blood_ratio`.

## Required outputs (`/app/output/sub-XX/`)
Write the quantity each region supports, as JSON objects keyed by region name:
- `bpnd.json` — `{region: BPND}`
- `vt.json` — `{region: VT}`
- `ki.json` — `{region: Ki}`

Report each region under **exactly one** quantity — the one its acquisition and kinetics
support — and omit it from the others. A region's reference region (when one is designated) is
the input and is not graded; do not report it.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid JSON for the
regions you can quantify so the rest of the cohort can be graded.
