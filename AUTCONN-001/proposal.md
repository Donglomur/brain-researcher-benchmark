## AUTCONN-001

**Proposal Title:** Test the Assaf (2010) ASD default-network underconnectivity claim — an un-cued multiple-comparisons inflation (the *multiple-comparisons* failure axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Autism resting-state functional connectivity

**Source finding:** Assaf et al. (2010), *NeuroImage*, https://doi.org/10.1016/j.neuroimage.2010.05.067 — reduced functional connectivity within default-mode sub-networks (PCC/mPFC) in ASD, one of the most-cited ASD intrinsic-connectivity findings. Reproducibility critique: King et al. (2019), *Molecular Autism*. Multiple-comparisons: Eklund et al. (2016). Data: `nilearn.datasets.fetch_abide_pcp` (cpac, rois_dosenbach160, quality-checked).

**Status: FULL runnable task, built with `tb-science-task-authoring`.** Failure axis **multiple-comparisons inflation** (statistical-inference family), rigor genre (tests a widely-cited claim, finds it doesn't survive correction — GRADIENT-style). Topic *ASD connectivity*, ABIDE.

**Difficulty vs frontier agents: NOT YET MEASURED** (gate deferred).

### Why this exists
Anchored the shipped **GRADIENT way** — take a widely-cited primary claim and test whether it survives rigorous analysis. Assaf's ASD default-network underconnectivity is textbook; the un-cued judgement is that with ~12,700 simultaneous edge tests the "differences" must be multiple-comparisons corrected — after which essentially none, including the DMN claim, survive.

### The reproduction / test (Step-0 validated) — the claim appears in direction only
ABIDE, quality-checked, Dosenbach-160 (391 ASD, 455 controls). Within-DMN functional connectivity is **numerically lower in ASD** (0.186 vs 0.190) — Assaf's reported direction — but **not significant** (t = −0.64, p = 0.53). So the specific DMN-underconnectivity claim is present in direction but does not robustly reproduce on this large sample.

### The trap (Step-0 validated) — the multiple-comparisons inflation
Whole-brain edgewise ASD-vs-control comparison over 12,720 connections:

| threshold | significant edges |
|---|---|
| uncorrected p<0.05 | **1085** (~636 expected by chance; 136 of them DMN edges) |
| uncorrected p<0.001 | 76 |
| FDR q<0.05 | **0** |
| FWE (Bonferroni) | **0** |

An uncorrected threshold flags ~1000 "different" connections, only ~1.7× the chance rate; after multiple-comparisons correction **none survive** — neither the whole-brain edges nor the DMN edges. The honest concluded count is ~0.

**Honesty note (from Step-0).** Two data-hygiene fixes over the trap-first draft: (1) switched from cc200 (unlabelled) to **Dosenbach-160**, whose network labels let the oracle actually *test Assaf's DMN claim* rather than run a generic contrast; (2) moved to **quality-checked** subjects and **excluded** (not zero-filled) NaN edges from degenerate ROIs — the earlier cc200/no-QC draft reported 7 FWE survivors, but on clean QC data with proper NaN handling the honest count is 0. The mult-comp lesson is now anchored on a real, named finding.

### Verifier (numeric, 2 checks)
`tests/test_outputs.py`: (1) a full edgewise comparison (≥5000 edges) with a reported significant count; (2) the reported count of significant connections must reflect correction (~0), not the uncorrected range — headline ≤ 30 passes, an uncorrected count (76 / 1085) fails. Robust key extractor excludes `uncorrected`-labelled fields. Offline: oracle (0) PASS; uncorrected-count (1085) adversarial FAIL.

### Honest caveats / open risks
1. **Difficulty UNTESTED** — needs the gate. **Telegraphing risk:** "correct for multiple comparisons" is a well-known reflex; the instruction is un-cued but the axis may be easy for frontier agents (shared with COGVBM/EEGMC — the same axis across 3 modalities is the intended coverage, but if one is easy all three may be).
2. **Null result** — the honest answer is 0 survivors; the task rewards recognising that, not a positive finding.

### Cost
`hard`. cpus 2, mem 8 GB, internet on (ABIDE Dosenbach-160 ROI time series + Dosenbach coord/label atlas — small, reliable S3 host). Deps: nilearn 0.12.1 + numpy/scipy/pandas/nibabel.
