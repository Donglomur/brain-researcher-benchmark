## SOCIALBRAIN-001

**Proposal Title:** Reproduce Richardson 2018's anti-correlation headline — an un-cued GSR-dependence trap (the *hard* reproduction)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Developmental functional connectivity

**Source paper:** Richardson et al. (2018), *Nature Communications*, https://doi.org/10.1038/s41467-018-03399-2 (dataset: OpenNeuro ds000228, via `nilearn.fetch_development_fmri`).

**Status: FULL runnable task, validated end-to-end; DEFEATS both frontier agents.** Built with the `tb-science-task-authoring` skill.

### Why this exists

A *clean* reproduction of a robust result is authentic but **easy** — during development an easy control variant (reproduce-and-report Richardson's within-network maturation, pipeline fully pinned) was measured and **both frontier agents passed**, simply computing and reporting honestly. The finding: difficulty comes from **un-cued volunteered judgement**, not reproduction-by-computation. This task injects exactly that into the reproduction genre — reproduce the famous *headline*, whose reproducibility hinges on a preprocessing choice (GSR) the agent must volunteer to investigate. (The easy control was validated then not shipped; this is the hard task.)

### The trap (Step-0 validated, real)

Richardson's headline — ToM and pain networks become increasingly anti-correlated with age (r_s≈−0.35) — reproduces **almost exactly, but only under global-signal regression (GSR)**:

| pipeline | across-network vs age (children) | adult mean |
|---|---|---|
| standard clean (confounds, detrend, z-score, **no GSR**) | r_s = **−0.07**, p=.45 (n.s.) | −0.08 |
| **+ global-signal regression** | r_s = **−0.34**, p=1e-4 | −0.20 |
| Richardson (paper) | r_s = −0.35, p<1e-4 | −0.17 |

GSR is mathematically known to introduce/strengthen negative correlations (Murphy 2009; Saad 2012; Murphy & Fox 2017). So an anti-correlation present only under GSR is **GSR-dependent, not a robust developmental effect**. The honest answer reports that dependence. ROIs are pinned; **preprocessing is left free** and the instruction is un-cued (no mention of GSR, robustness, or sensitivity).

### Verifier (2 plain checks)

`tests/test_outputs.py`: (1) connectivity computed; (2) `findings.md` recognises the **GSR-dependence** — that the anti-correlation reproduces *with* GSR and not *without* (or that GSR induces it) — **not** a flat "reproduces"/"doesn't", and not merely naming the pipeline.

### Difficulty — MEASURED (Step 5): defeats both frontier agents

| agent | reward | what it did |
|---|---|---|
| **GPT-5.5 (codex, xhigh)** | **FAIL** | one pipeline (no GSR, bandpass), across r=−0.155 (n.s.) → "supports only the direction, not a clear reproduction." Never tested GSR. |
| **Claude Opus 4.8** | **FAIL** | one pipeline (no GSR, bandpass), across r=−0.156 (n.s.) → flat "does not reproduce." Generic ROI/pipeline caveat but never tested GSR. |

Both ran a single standard pipeline, got the null, and gave a flat verdict — **neither volunteered the GSR-sensitivity analysis** that reveals the real (GSR-dependent) story. The un-cued trap works.

**Verifier-integrity note (the skill's inspect-real-outputs lesson, live):** the first verifier version *false-passed* GPT-5.5 because it wrote "no global signal regression" to describe its pipeline and a bare `no global signal` regex branch counted that as the insight. Inspecting the captured output caught it; the check now requires GSR to be *linked to the result* (re-tuned and verified against the real GPT/Claude outputs + adversarials).

### Discrimination (validated locally)

| solution | verdict |
|---|---|
| reference (runs both pipelines, reports GSR-dependence + artifact caveat) | **PASS** |
| genuine "null without GSR, −0.34 with GSR → GSR-dependent" | **PASS** |
| flat "doesn't reproduce" (never tried GSR) | **FAIL** |
| "applied GSR, got −0.35, reproduced!" (no dependence/caveat) | **FAIL** |
| real GPT-5.5 output / real Claude output | **FAIL** |

### Cost

`hard`. cpus 2, mem 8 GB, internet on (downloads all 155 ds000228 subjects + whole-brain global-signal extraction for the GSR pipeline; timeouts 5400 s). Agent runtimes ~16–22 min. Deps: nilearn 0.12.1 + scipy/sklearn/pandas/nibabel.
