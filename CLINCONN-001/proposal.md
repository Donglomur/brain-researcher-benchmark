## CLINCONN-001

**Proposal Title:** Reproduce the schizophrenia-vs-control resting-connectivity difference — an un-cued head-motion confound (the *wrong-cause* failure axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Clinical functional connectivity

**Source finding:** Poldrack et al. (2016), *Scientific Data*, https://doi.org/10.1038/sdata.2016.110 (UCLA Consortium for Neuropsychiatric Phenomics, OpenNeuro `ds000030`); motion critique: Power et al. (2012), Satterthwaite et al. (2012), Van Dijk et al. (2012). Data: `ds000030` fMRIPrep derivatives (legacy release `R1.0.5`, `.../derivatives/fmriprep/`), task-rest, fetched at runtime from the public no-credentials S3 bucket.

**Status: FULL runnable task, real fetched data.** Complements DEVCONN-001 (developmental motion confound) on a *clinical* case-vs-control axis — a distinct dataset, modality (surface fMRIPrep derivatives), and finding, with the same **wrong-cause** judgement gap.

### Why this exists

An agent asked to "compare resting FC between the schizophrenia group and controls" will compute the connectomes, find that patients show higher / more widespread connectivity, and report a schizophrenia connectivity signature — **without volunteering the one check the task never mentions**: patients move far more in the scanner, and head motion inflates functional connectivity. This is the textbook clinical-connectivity confound (Power 2012; Satterthwaite 2012).

### The trap (Step-0 validated, real)

On the `ds000030` fMRIPrep rest derivatives (Destrieux `fsaverage5` surface parcellation; standard nuisance regression = 6 motion + aCompCor(6) + white matter; **50 SCHZ vs 122 CONTROL** with a usable rest run):

| | raw (no motion control) | motion-controlled | verdict |
|---|---|---|---|
| **premise** patients move more | mean FD SCHZ 0.253 vs CONTROL 0.161 | — | MWU **p = 4e-5** (~55% more) |
| short-range FC (SCHZ vs CONTROL) | 0.216 vs 0.178, t = **2.11** (p = 0.038) | mean-FD covariate: t = −0.08 (**p = 0.94**) | **collapses** |
| edge-wise \|t\|>2 group differences | **14.4%** of edges (89% patient-higher) | controlling FD: **7.4%** (≈ chance) | **collapses** |
| group-difference map vs QC-FC motion map | r = **0.52** | controlling FD: r = 0.20 | motion-aligned |
| decode SCHZ vs CONTROL (AUC) | 0.74 | motion-matched (FD<0.2): 0.63 | **drops** |

The apparent schizophrenia connectivity difference is present at face value and **is substantially a head-motion artifact** — patients move more, the difference aligns with the QC-FC motion map, and it collapses once motion is controlled. (`mean FC ~ mean FD` across subjects: r = 0.66.)

**Honesty notes (no-fake-traps discipline, from Step-0):**
1. After proper per-volume nuisance regression the *residual* whole-brain mean-FC group difference is only a trend (t = 1.80, p = 0.076); the effect is carried by **short-range** connectivity (motion's distance-dependent target: t = 2.11, p = 0.038) and by the **edge-wise fraction** (14.4% vs 5% chance). Both are anchored on, and both collapse under motion control. The task is framed as "report whether/how FC differs", so the agent's own summary (mean edge strength, short/long, edge-wise count) surfaces the apparent effect.
2. The motion difference is specific to **SCHZ vs CONTROL** (MWU p = 4e-5). BIPOLAR (p = 0.05) and ADHD (n.s.) move less; the clean, well-powered contrast is schizophrenia vs controls, so the task is anchored there.

### Verifier (2 plain checks)

`tests/test_outputs.py`: (1) per-subject connectivity computed for **both** diagnostic groups, values in [−1, 1]; (2) `findings.md` **recognises the motion confound** — the group difference is driven by / collapses under head motion (patients move more) — **not** a flat "patients show altered connectivity", **not** a flat "no difference", and **not** merely naming motion regressors in the pipeline. Offline discrimination (locked): reference PASS; over-claim FAIL; no-difference FAIL; pipeline-names-motion FAIL; vague "motion affects connectivity generally" hedge FAIL; covariate / motion-matched / QC-FC / "patients move more and it drives the effect" wordings PASS. Whitespace is normalised before matching so hard-wrapped findings are read as flowing sentences.

### Difficulty

`hard`. cpus 2, mem 8 GB, internet on. Fetches, at runtime, the fMRIPrep rest outputs (surface `fsaverage5` giftis + confounds, ~13 MB/subject) for ~172 subjects; one Destrieux parcellation + connectome per subject; timeouts 7200 s. Deps: nilearn 0.12.1 + scipy/sklearn/pandas/nibabel.

**Re-validated (hardening pass).** The recognition grader's pipeline-vocabulary guard was re-confirmed offline against four write-ups on a fixed connectivity.csv (DEVCONN-style, whitespace-normalised, no bare `reduc\w*`): the honest oracle answer PASSES; a naive "patients show altered connectivity" over-claim FAILS; a **pipeline-vocab-only** write-up that regresses the 6 motion parameters "to reduce confounds" but never links motion to the group result FAILS (the key false-positive); a correct answer that links head motion to the group difference via a motion-matched subsample PASSES. **The live frontier-agent gate (Step-5, ≥2 families k≥3) is the maintainer's step and remains PENDING;** only the numeric Step-0 substrate and the offline verifier discrimination are validated here.

### Cost

Data volume ~2.2 GB (surface derivatives, far lighter than the volumetric BOLD). Reproduces the published cohort structure; the graded quantity (recognition of the motion confound) is convention-invariant and un-cued.

### Proof-of-work rework (held-out reference)

The verifier was upgraded to the proof-of-work contract (PROOF_OF_WORK_SPEC.md). A held-out
reference (`tests/reference.npz`, never shipped to the agent) was built by running
`solution/compute.py` on the real ds000030 R1.0.5 fMRIPrep rest derivatives (fsaverage5 Destrieux;
**50 SCHZ + 122 CONTROL = 172 subjects** with a usable rest run, pinned by `subject_id`). It stores
each subject's `mean_fc / short_range_fc / long_range_fc` + group label and the discriminating
statistics (naive short-range group t = +2.11; FD-controlled t = −0.08; edgewise 14.4%→7.4%; mean
FD SCHZ 0.253 vs CONTROL 0.161). The grader now (1) matches the submitted per-subject connectivity
to the reference (cross-subject r ≥ 0.95 + per-subject tolerance + real group labels), (2) recomputes
the naive short-range group t from the submitted rows and cross-checks it against the reported JSON,
and (3) grades the discriminating post-control statistics (the motion-controlled group t collapses
toward null; patients' mean FD is higher) as numbers. Validated by subprocess pytest:
honest PASS; no-table / constant / fabricated (right group mean, shuffled per-subject) / naive
(no motion control, over-claim) / right-headline-fake-rows all FAIL. Data > 100 MB/file so raw
inputs stay runtime-fetch with the cohort pinned; baking the derived per-subject inputs is a
maintainer follow-up.

### Second-pass hardening (2026-09, RECOMPUTE-from-rows + fairness widening)

The first-pass pillar 3 trusted the **reported** FD-controlled group t (only requiring |t| ≤ 1.2 and
a loose match to the reference −0.08). That is the red-team hole: the FD-covariate stat is bounded
near-null, so an agent could compute the real naive group t (validated in pillar 2) and simply
**guess** "collapses, t ≈ 0" without ever running the FD-covariate analysis.

Fix (RECOMPUTE-from-neutral-table, §1): a per-subject **mean framewise displacement (`mean_fd`)**
column — plain motion QC every fMRIPrep run emits — is now a required output, and the FD-covariate
group t (OLS of short-range FC on `[1, SCHZ, mean_fd]`, t of the diagnosis coefficient) plus the
naive→controlled collapse are **recomputed from the submitted `{short, group, mean_fd}` rows** and
matched to the held-out reference. The submitted `mean_fd` is validated per subject against a new
held-out `ref_fd` (cross-subject r ≥ 0.85 + absolute match); a shuffled/fabricated FD column does
not absorb the diagnosis effect (recomputed FD-covariate t ≈ +2.3 instead of ≈ 0) and fails. The
reported t is now only a consistency cross-check. `instruction.md` names `mean_fd` neutrally as a QC
column (never "control for motion"); `tests/` is held out of the container, so the recognition of
the confound stays a volunteered judgement in a real eval.

Fairness widening (red-team: `CORR_MIN` 0.95 rejected defensible variants): the per-subject
short-range cross-subject lock is widened **0.95 → 0.85** (matching DEVCONN). This is a pure
fairness gain with no security cost — the binding fabrication teeth is the absolute per-subject
match (e.g. substituting `mean_fc` for `short_range_fc` correlates 0.96 across subjects but matches
absolutely for only 14% of subjects, so it still fails), plus the real group labels and the
recomputed FD-covariate collapse.

Second-pass validation matrix (subprocess pytest): honest PASS; defensible (+/−7% per-subject
connectivity & FD, corr ~0.99) PASS; fabricated/constant no-FD table FAIL; attack C real
connectivity + NO mean_fd column + guessed t=−0.08 FAIL; attack C real connectivity + shuffled
mean_fd + guessed collapse FAIL (recomputed FD-covariate t = +2.27, no collapse). `ref_fd` added to
`tests/reference.npz` (0.008 MB; per-subject FD reproduces the reference naive t = 2.112 and
FD-covariate t = −0.077 exactly).
