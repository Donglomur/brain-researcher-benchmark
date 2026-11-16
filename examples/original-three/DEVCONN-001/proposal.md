## DEVCONN-001

**Proposal Title:** Reproduce the developmental "local-to-distributed" connectivity result — an un-cued head-motion confound (the *wrong-cause* failure axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Developmental functional connectivity

**Source finding:** Fair et al. (2009), *PLoS Computational Biology*, https://doi.org/10.1371/journal.pcbi.1000381 ("Functional Brain Networks Develop from a 'Local to Distributed' Organization"); motion critique: Power et al. (2012), Satterthwaite et al. (2012). Dataset: OpenNeuro `ds000228` via `nilearn.datasets.fetch_development_fmri`.

**Status: FULL runnable task, built with the `tb-science-task-authoring` skill.** Opens the third failure axis (**wrong-cause**), on a non-connectivity-monoculture control (motion), complementing GRADIENT-001 (over-claim) and SOCIALBRAIN-001 (confident-refutation).

### Why this exists

Both shipped tasks probe un-cued judgement, but neither probes **wrong-cause attribution** — the agent reproduces an effect and never asks whether a *confound* produced it. This task fills that gap with the textbook example: developmental connectivity is the canonical head-motion confound (children move ~2× more; motion is distance-dependent), yet an agent asked to "reproduce the developmental finding" will compute it, find it significant, and report it — without volunteering the motion check the task never mentions.

### The trap (Step-0 validated, real)

On the nilearn-pinned `ds000228` (Power-264, 5 mm spheres, 122 children + 33 adults; short/long = bottom/top tertile of ROI-pair distance):

| | raw (no motion control) | motion-controlled | verdict |
|---|---|---|---|
| **premise** child moves more | child mean FD 0.371 vs adult 0.187 | — | MWU **p = 4e-6** (~2×) |
| age ~ short-range FC (children) | r_s = **−0.205** (p = 0.011) | partial \| mean FD: r = −0.033 (**p = 0.68**) | **collapses** |
| segregation (short−long) child vs adult | **p = 0.030** | motion-matched FD<0.2: **p = 0.61** | **collapses** |

The developmental local-to-distributed effect is present at face value and **vanishes once head motion is controlled** — it is substantially a motion artifact, not a robust maturational signal.

**Honesty notes (no-fake-traps discipline, from Step-0):**
1. The *first* metric was wrong: naive "mean long-range FC" showed child > adult (opposite of the textbook), because it captures motion's **global positive bias**, not distance-dependence. Discarded. The real, fair flip lives on **short-range / segregation + proper motion control** (FD covariate / motion-matching). Step-0 caught this.
2. Subtler than SOCIALBRAIN-001's GSR flip: short-range FC alone is so strong (p = 6e-8) it partially survives matching (p = 0.0035 at FD<0.2); the *clean* significant→null collapse is on the age-continuous effect with an FD covariate and on the segregation index under motion-matching. The task is anchored on those, **not** on "weaker long-range" (global-bias contaminated).

### Verifier (2 plain checks)

`tests/test_outputs.py`: (1) per-subject short/long connectivity computed for both age groups; (2) `findings.md` **recognises the motion confound** — the developmental effect is driven by / collapses under head-motion control — **not** a flat "reproduces"/"doesn't", and **not** merely naming motion regressors in the pipeline. Offline discrimination (locked numbers): reference PASS; flat-reproduces (+ pipeline-names-motion) FAIL; flat-doesn't-reproduce FAIL; correct-confound (covariate / matching wording) PASS; vague "motion can affect connectivity generally" hedge FAIL.

### Difficulty — MEASURED: both frontier families FAIL, k≥3 each

Oracle **reward 1.0** (container, downloads=0 via host cache mount).

| agent | runs | reward | what it did |
|---|---|---|---|
| **GPT-5.5 (codex, xhigh)** | 4/4 | **FAIL** | computed short/long/segregation + age + group means correctly; hedged "does not reproduce the full result"; **0/4 ever mentioned head motion** — never asked whether the group that moves 2× more produced it. |
| **Claude Opus 4.8** | 3/3 | **FAIL** | richer analysis (categorical-vs-graded verdict); the closest run volunteered a **global-amplitude** caveat ("both short- and long-range higher in children") — genuinely skeptical — but **still never identified or checked head motion** as the cause. 2/3 zero motion mentions; the 3rd only named motion in its pipeline confound list. |

Both families, every run, fail for the same un-cued **wrong-cause** reason: they do the computation, some even volunteer *a* caveat, but none volunteer the motion check on the higher-motion group. Hand re-scored (skill Step 5): `test_connectivity_and_age_effect_computed` PASS for all, only `test_reproduction_recognises_motion_confound` fails → the failure is the judgement gap, not a format bug.

**Verifier-integrity note (skill's inspect-real-outputs lesson, live — 2nd instance after SOCIALBRAIN's GSR):** the first verifier version *false-passed* Claude's global-amplitude run, because its regex counted the pipeline phrase "fMRIPrep **reduced confounds regressed** (**motion**, aCompCor, …)" as the insight (a `reduced`→`regressed`→`motion` chain, and a bare `confound…motion` chain). Caught by hand-reading the PASS. Fixed: the motion insight must be **linked to the developmental result** (a confound *of* the age/group effect, or the effect *collapsing under motion control*) — not motion named in the pipeline. Re-tuned and verified: reference + covariate/matched wordings PASS; all 7 real agent runs + pipeline-naming + vague-hedge adversarials FAIL.

### Cost

`hard`. cpus 2, mem 8 GB, internet on (downloads all 155 ds000228 subjects; one Power-264 sphere extraction per subject; timeouts 7200 s). Deps: nilearn 0.12.1 + scipy/sklearn/pandas/nibabel. Dev/agent runs may mount the host `nilearn_data` cache to skip the osf download (local flag only, never committed).
