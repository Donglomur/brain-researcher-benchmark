## TASKFC-001

**Proposal Title:** Estimate the task-state functional connectivity between two co-engaged visual regions — an un-cued *task-evoked co-activation* inflation (a new failure axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Task-state functional connectivity

**Source finding / axis anchor:** Cole et al. (2019), *NeuroImage*, https://doi.org/10.1016/j.neuroimage.2018.12.054 ("Task activations produce spurious but systematic inflation of task functional connectivity estimates"); see also Fair et al. (2007), Al-Aidroos et al. (2012), Norman-Haignere et al. (2012) on *background connectivity*. Dataset: nilearn language-localizer demo (`fetch_language_localizer_demo_dataset`, OSF `k4jp8`), 10 subjects, RSVP reading (`language` vs `string` blocks).

**Status: FULL runnable task, built with the `tb-science-task-authoring` skill.** Replaces the retired CONNSTAB-001 (PR #189). Opens a **new failure axis** (*task-evoked co-activation inflating task-state FC*) on a **new modality/method** (task-fMRI GLM × connectivity), breaking the resting-state-connectivity monoculture of GRADIENT/SOCIALBRAIN/DEVCONN.

### Why this exists

The shipped tasks probe over-claim, confident-refutation, and wrong-cause on resting-state connectivity / gradients. None probe the **task-fMRI connectivity** pitfall that a raw correlation of BOLD time series *during a task* is not a valid estimate of connectivity: two regions co-driven by the stimulus co-vary because of the **shared task-evoked response**, so the raw correlation is systematically inflated by co-activation, not coupling (Cole 2019). The honest analyst removes the task-evoked response first (**background connectivity**). An agent asked to "estimate the task-state connectivity between two regions" will extract the time series, correlate them, and report the (inflated) number — without volunteering the evoked-response check the task never mentions.

### The lever (Step-0 validated, real, robust)

nilearn language-localizer demo (all 10 subjects), two 8 mm spheres at MNI **(-30,-90,-6)** and **(30,-90,-6)** (left/right lateral occipital cortex, both strongly driven by the visual RSVP). Common preprocessing for both estimates = cosine drift + 6 motion regressors; Fisher-*z* averaged Pearson correlation. The **only** difference between the two estimates is whether the task-evoked GLM response (`language` + `string`, Glover HRF) is regressed out first.

| estimate | value | note |
|---|---|---|
| **library-default naive** (nilearn `NiftiSpheresMasker` + `ConnectivityMeasure`) | r = **0.643** | what a competent agent produces by default |
| raw task-state FC (drift+motion cleaned, task-evoked kept) | r = **0.630** | the requested deliverable |
| **background FC** (task-evoked regressed out) | r = **0.461** | the honest estimate |
| **inflation** raw − background | **+0.169** | paired *t* = 4.02, **p = 3.0e-03**, raw > background in **10/10 subjects** |

**Robust across defensible variants** (sphere radius × task-evoked model):

| | glover HRF | glover + derivative | FIR (flexible) |
|---|---|---|---|
| r = 6 mm | +0.161 (10/10) | +0.202 (10/10) | +0.108 (10/10) |
| r = 8 mm | +0.169 (10/10) | +0.218 (10/10) | +0.121 (10/10) |
| r = 10 mm | +0.158 (9/10) | +0.194 (9/10) | +0.108 (10/10) |

Every cell: raw > background, all p < 0.012. The raw estimate always materially exceeds the background estimate; roughly a fifth to a third of the apparent raw coupling is shared stimulus-evoked co-activation.

**No-fake-traps / specificity check — a negative control.** A pair that is *not* co-driven by the task (left visual (-30,-90,-6) vs left motor (-38,-22,54)) shows **no inflation**: raw 0.059 vs background 0.126 (raw > background in only 1/10 subjects). So regressing the task does **not** mechanically lower correlations — it specifically removes the shared task-evoked drive in co-activated pairs. This rules out the "regression artifact" objection and confirms the effect is genuine task-evoked co-activation.

### The STRONG bar

- **Un-cued:** instruction and required outputs never mention the evoked response, task regression, background connectivity, co-activation, or Cole. It asks only for the task-state FC between the two regions.
- **Off-critical-path:** the deliverable (a connectivity value) is fully producible by correlating the raw time series; recognising the evoked-response inflation is a *volunteered* judgement, not a step needed to answer.
- **Naive-default-is-wrong:** the library default (nilearn masker + `ConnectivityMeasure` = 0.643) is exactly what a competent agent does and it systematically overstates the coupling by ~27% relative to the background estimate — a recognised, documented error (Cole 2019: "spurious but systematic inflation").
- **Big robust gap:** unanimous 10/10, p = 0.003, holds across all radius × HRF variants, with a clean negative control.

### Verifier (2 plain checks, `tests/test_outputs.py`)

1. `test_connectivity_computed` — a valid per-subject task-state FC (in [-1,1]) is computed for the two regions across the subjects, plus a group value in `connectivity_summary.json`. Schema-robust (any connectivity-like column; any-depth numeric search). Both naive and honest pass — the shared critical path.
2. `test_recognises_task_evoked_inflation` — `findings.md` recognises that the raw task-state connectivity is inflated by the shared task-evoked response and that the background / task-regressed connectivity is materially lower. **Guarded** (skill Step-5 pipeline-vocabulary lesson): the evoked-response term must *co-occur with a connectivity RESULT token in an inflation/reduction direction* (or a causal "inflated **by** the task-evoked response" link); the trigger set deliberately **excludes** bare pipeline vocabulary (motion / nuisance / drift / confound / aCompCor), so a submission that merely describes a GLM or motion regression does not pass.

### Offline discrimination (locked; oracle reward 1.0)

Reference (oracle) computes both estimates and reports the inflation → **PASS** (reward 1.0). Adversarial/defensible set (all as expected):

| output | grader |
|---|---|
| oracle reference | **PASS** |
| naive flat ("FC is r=0.63, strong coupling") | FAIL |
| naive + pipeline vocabulary (GLM/motion/nuisance described, flat FC) | FAIL |
| over-claim ("very strong intrinsic connectivity") | FAIL |
| vague hedge ("FC affected by many factors incl. paradigm") | FAIL |
| co-activation named + per-subject variation (no inflation insight) | FAIL |
| GLM-for-activation only (task regressed for activation, flat FC) | FAIL |
| defensible-correct, FIR background ("removed task-evoked, FC fell to 0.51, overstates") | **PASS** |
| defensible-correct, task-regression ("regressed task design, dropped to 0.46, inflated") | **PASS** |
| defensible-correct, terse ("inflated by task-evoked activation; background 0.46") | **PASS** |

### Difficulty

The construction bar (un-cued · off-critical-path · naive-default-wrong · big robust gap · guarded fair grader · oracle 1.0 · schema-robust) is met. The live frontier-agent gate (≥2 families, k≥3) is the maintainer's Step-5; the un-cued/off-critical-path shape matches the shipped hard tasks (DEVCONN/SOCIALBRAIN) whose frontier gap was measured.

### Cost

`hard`. cpus 2, mem 8 GB, internet on (`allow_internet=true`); the language-localizer demo is small (10 subjects, 4.5 mm resampled) and compute is light (two spheres per subject + a GLM design), timeouts 3600 s. Deps: nilearn 0.12.1 + scipy/sklearn/pandas/nibabel (pinned; identical set to the merged DEVCONN-001). Dev/agent runs may mount the host `nilearn_data` cache to skip the OSF download (local flag only, never committed); external runners fetch at runtime.

## Proof-of-work verifier (v-pow, 2026-09)

Held-out reference `tests/reference.npz` (from `solution/compute.py`, never shipped): per-subject
RAW and BACKGROUND task-state FC for the 10 pinned language-localizer subjects (sub-01..sub-10) +
`ref_stats` (raw_g=0.630, bg_g=0.461, inflation=0.169, paired t=4.02, p=3.0e-3, raw>bg 10/10).
reference.npz sha256 2a5ffb4fabe7140f. The task stays **un-cued** (background FC is volunteered,
never named in the instruction); `connectivity.csv` now invites "any additional per-subject
connectivity you computed" (no cue).

### Second-pass hardening (2026-09, RECOMPUTE-from-rows)

The first-pass verifier trusted a **reported group background scalar** in pillar 3 and only
validated the per-subject background column *if present*. That is the red-team hole (TASKFC Tier 2,
"background FC reported not recomputed"): an agent could compute the real per-subject RAW FC (the
naive path), never run the residual analysis, and simply **publish/guess** a ~0.46 group background
to clear pillar 3.

Fix (the RECOMPUTE-from-neutral-table pattern, §5(a) mild-hint variant for a separate-pipeline
discriminator): the per-subject **background connectivity column is now MANDATORY** and the group
background + the raw>background inflation are **recomputed from the per-subject rows**, not read
from the summary. The per-subject background values are validated against the held-out reference
(cross-subject r>=0.95, absolute per-subject match within 0.05). This has real teeth because across
the 10 subjects **corr(raw, background) is only ~0.74** — a fabricated background scaled from the
raw column fails both the cross-subject correlation and the absolute match. The reported group
background is kept only as a consistency cross-check.

Note (§5 tradeoff, documented): making the background column mandatory in the **grader** is the
least-bad option for this separate-pipeline discriminator. It does **not** cue the in-container
agent — `tests/` is held out of the container, and `instruction.md` is unchanged (it still names
neither the task-evoked response nor background connectivity), so recognising the inflation remains
a volunteered judgement in a real (fresh, server-side-graded) eval. Only a submission that both
computed the real per-subject residual correlations and reported them can pass.

Pillars (subprocess-validated): (1) per-subject RAW FC covers the pinned subjects, non-constant,
cross-subject r>=0.95 to the reference (kills fabricated/dup rows); (1b, MANDATORY) a per-subject
background column matches the reference (cross-subject r>=0.95, per-subject within 0.05); (2) group
RAW + background means recompute from the rows == reference == reported; (3) group background +
raw>background inflation **recomputed from the rows** is materially lower than raw (gap>=0.08),
matches the reference inflation (~0.169) and background (~0.46), and is systematic (raw>bg in >=8/10
subjects, recomputed); (secondary) the task-evoked inflation prose.

Validation matrix (subprocess pytest): honest PASS | defensible (+/-7% per-subject raw & background,
corr ~0.99) PASS | fabricated/constant no-background table FAIL | attack C: real raw + NO background
column + guessed group background 0.46 FAIL | attack C: real raw + background fabricated as scaled
raw (~0.46 mean) FAIL (cross-subject r=0.737 < 0.95).

Packaging: pinned nilearn language-localizer demo (all 10 subjects), nilearn 0.12.1 stack; data
runtime-fetched, `allow_internet=true` retained. Baking the per-subject inputs is a maintainer
follow-up.
