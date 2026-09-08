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
