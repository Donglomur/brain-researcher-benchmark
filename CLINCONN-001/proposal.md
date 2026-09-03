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

`hard`. cpus 2, mem 8 GB, internet on. Fetches, at runtime, the fMRIPrep rest outputs (surface `fsaverage5` giftis + confounds, ~13 MB/subject) for ~172 subjects; one Destrieux parcellation + connectome per subject; timeouts 7200 s. Deps: nilearn 0.12.1 + scipy/sklearn/pandas/nibabel. **Step-5 frontier calibration PENDING.**

### Cost

Data volume ~2.2 GB (surface derivatives, far lighter than the volumetric BOLD). Reproduces the published cohort structure; the graded quantity (recognition of the motion confound) is convention-invariant and un-cued.
