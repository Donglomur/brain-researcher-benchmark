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

---

## Proof-of-work rebuild (verifier hardening, 2026-09)

The prior grader **never opened `age_effects.json`** (which holds the headline r/p): it checked
only that `connectivity.csv` had in-range short/long columns for both groups and that `findings.md`
contained a motion-confound sentence — so **fabricated per-subject rows + a keyword sentence
passed**. This pass applies the suite-wide **proof-of-work** contract
(`scratchpad/PROOF_OF_WORK_SPEC.md`).

**Held-out reference (`tests/reference.npz`, built from `solution/compute.py`, never shipped to
the agent).** Per-subject short-range / long-range / segregation for the 122 children + 33 adults
of the nilearn-pinned ds000228 (Power-264 5 mm spheres), plus age/group. Discriminating statistics:
the raw maturational age~short-range effect is **r_s = −0.204 (p = 0.011)** and collapses under a
mean-FD partial correlation to **r = −0.031 (p = 0.70)**; children move far more than adults
(mean FD **0.371** vs **0.187**, MWU p = 4e-6).

**Four grading pillars** (`tests/test_outputs.py` + `tests/proof_of_work.py`):
1. **Exact subjects + per-item values** — `connectivity.csv` must cover ≥90 % of the real subjects,
   be non-constant, and its per-subject short-range must track the held-out reference
   (cross-subject r ≥ 0.85, per-subject |Δ| ≤ 0.04).
2. **Recompute** — the all-subjects Spearman(age, short-range) recomputed from the submitted rows
   must equal the raw maturational reference (−0.204) and the reported JSON.
3. **Discriminating number(s)** — the **motion collapse** graded as numbers: the raw age~short
   effect must be negative (~−0.20) *and* the mean-FD partial correlation must be ~null
   (|r| ≤ 0.12), a markedly smaller magnitude; children's mean FD must exceed adults'. A run that
   never did the motion check cannot report the partial correlation.
4. **Secondary prose** — the existing negation-aware motion-confound recognition; not the sole gate.

**Validation (subprocess pytest per case, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`):**

| case | result |
|---|---|
| honest (oracle reference values) | PASS |
| no `connectivity.csv` | FAIL |
| constant short-range table | FAIL |
| non-constant fabricated (real IDs, shuffled short-range) | FAIL |
| naive (real short/long rows + raw effect, **no motion control**) | FAIL (pillar 3) |

The naive run passes pillars 1–2 (its rows are the real per-subject values) and fails **precisely**
at the discriminating motion-controlled number — the intended teeth.

**Packaging.** Real subjects pinned via `tests/reference.npz`. The raw ds000228 derivatives exceed
GitHub's 100 MB/file limit, so `allow_internet=true` + runtime fetch are retained; baking the
derived per-subject ROI series is a maintainer follow-up. Reference built on
`fetch_development_fmri()` (all 155 subjects) + Power-2011 264-ROI 5 mm spheres.

### Second-pass hardening (2026-09, RECOMPUTE-from-rows)

The first-pass pillar 3 still **trusted the reported** motion-controlled partial (it only required
the reported `age_short_partial_given_fd.r` to satisfy |r| ≤ 0.12). That is the red-team hole: the
motion-collapse stat is bounded near-null, so an agent could compute the real raw effect (validated
in pillars 1–2) and simply **guess** "partial ≈ 0" without ever running the FD-covariate analysis.

Fix (the RECOMPUTE-from-neutral-table pattern, §1): a per-subject **mean framewise displacement
(`mean_fd`)** column — plain motion QC every fMRIPrep run emits — is now a required output, and the
mean-FD partial correlation `Spearman(age, short | mean_fd)` plus the collapse (`|raw| − |partial|`)
are **recomputed from the submitted `{age, short, mean_fd}` rows** and matched to the held-out
reference. The submitted `mean_fd` is validated per subject against a new held-out `ref_fd`
(cross-subject r ≥ 0.85 + absolute match to 0.05). A shuffled/fabricated FD column does not
reproduce the collapse — the recomputed partial stays at ≈ −0.19 (≈ the raw effect) instead of
≈ −0.03 — and fails. The reported partial is now only a consistency cross-check. `instruction.md`
names `mean_fd` neutrally as a QC column (never "control for motion"); `tests/` is held out of the
container, so recognising the confound stays a volunteered judgement in a real eval.

Second-pass validation matrix (subprocess pytest): honest PASS; defensible (±3 % connectivity, ±7 %
FD) PASS; fabricated/constant no-FD table FAIL; attack C real connectivity + **no `mean_fd`** column
+ guessed partial −0.03 FAIL; attack C real connectivity + **shuffled `mean_fd`** + guessed partial
FAIL (recomputed partial = −0.190, no collapse). `ref_fd` added to `tests/reference.npz` (0.008 MB;
the per-subject FD reproduces the reference partial −0.0315 and the child/adult mean FD exactly).
