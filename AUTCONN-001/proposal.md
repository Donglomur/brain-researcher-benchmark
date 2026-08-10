## AUTCONN-001

**Proposal Title:** Test the Assaf (2010) ASD default-network underconnectivity claim — an un-cued multiple-comparisons inflation (the *over-claim / statistical-rigor* failure axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Autism resting-state functional connectivity

**Source paper:** Assaf et al. (2010), *NeuroImage*, https://doi.org/10.1016/j.neuroimage.2010.05.067 — reduced functional connectivity within default-mode sub-networks (PCC/mPFC) in ASD, one of the most-cited ASD intrinsic-connectivity findings. Reproducibility critique: King et al. (2019), *Molecular Autism*. Multiple-comparisons critique: Eklund et al. (2016), *PNAS*. Cohort context: Di Martino et al. (2014), *Molecular Psychiatry* (ABIDE). Dataset: `nilearn.datasets.fetch_abide_pcp` (cpac, rois_dosenbach160, quality-checked).

**Status: FULL runnable task, built with the `tb-science-task-authoring` skill; built the shipped GRADIENT-style rigor way (take a widely-cited primary claim → test whether it survives rigorous analysis).** Failure axis **multiple-comparisons inflation** (statistical-inference family). Topic *ASD connectivity*, ABIDE.

### Why this exists

Assaf's ASD default-network underconnectivity is a textbook claim. The un-cued judgement is that a whole-brain edgewise ASD-vs-control contrast runs ~12,700 simultaneous tests, so the "differences" must be multiple-comparisons corrected — after which essentially none, including the DMN claim, survive. Exactly the shipped rigor pattern: the agent runs the standard contrast, gets a large uncorrected count, and fails only if it does not *volunteer* the correction the instruction never mentions.

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

An uncorrected threshold flags ~1000 "different" connections, only ~1.7× the chance rate; after multiple-comparisons correction **none survive** — neither the whole-brain edges nor the DMN edges. The honest concluded count is ~0. Reporting the uncorrected count presents multiple-comparisons noise as real group differences.

**Honesty note (no-fake-traps discipline, from Step-0).** Two data-hygiene fixes over the trap-first draft: (1) switched from cc200 (unlabelled) to **Dosenbach-160**, whose network labels let the oracle actually *test Assaf's DMN claim* rather than run a generic contrast; (2) moved to **quality-checked** subjects and **excluded** (not zero-filled) NaN edges from degenerate ROIs — the earlier cc200/no-QC draft reported 7 FWE survivors, but on clean QC data with proper NaN handling the honest count is 0. The mult-comp lesson is now anchored on a real, named finding.

### Verifier (2 plain checks)

`tests/test_outputs.py`: (1) `test_group_comparison_computed` — a full edgewise comparison (≥5000 edges) with a reported count of significantly-differing connections; (2) `test_significance_corrected_for_multiplicity` — the reported headline count must reflect correction (~0), **not** the uncorrected range: a corrected count ≤ 30 passes, an uncorrected count (76 / 1085) fails. The extractor excludes `uncorrected`-labelled fields and converts a significant *fraction/percent* back to an absolute edge count so an uncorrected 0.085 / 8.5% cannot hide as ~0.

**Discrimination (validated locally):**

| solution | verdict |
|---|---|
| reference (runs the whole-brain contrast, then reports ~0 survive correction — DMN claim non-significant, no edges FWE/FDR) | **PASS** |
| genuine "1085 uncorrected but 0 after FDR/FWE → no reliable group differences" | **PASS** |
| flat "~1085 connections significantly differ between ASD and controls" (uncorrected count) | **FAIL** |
| "76 connections at p<0.001 differ" (still uncorrected) | **FAIL** |
| significant *fraction* 0.085 reported as the result (converts to ~1081) | **FAIL** |

### Difficulty — PENDING the frontier gate (harbor + GPT-5.5 / Claude, k≥3 each)

Oracle **reward 1.0** (in-container, run by maintainer). Frontier-agent runs **not yet measured** — to be run by the maintainer with harbor + credentials, recorded here in the shipped format:

| agent | runs | reward | what it did |
|---|---|---|---|
| **GPT-5.5 (codex, xhigh)** | _k≥3_ | _pending_ | _pending_ |
| **Claude Opus 4.8** | _k≥3_ | _pending_ | _pending_ |

**Expected failure mode (hypothesis, to be confirmed by the gate):** both families run the edgewise contrast correctly and report the uncorrected count (dozens–thousands of "significant" connections) as the group difference, without volunteering the multiple-comparisons correction over ~12,700 tests that leaves ~0 survivors. **Telegraphing risk:** "correct for multiple comparisons" is a well-known reflex, so this axis may prove easier for frontier agents than the confound axes — the gate will decide; if it is easy, that is recorded honestly.

**Verifier-integrity note (the skill's inspect-real-outputs lesson).** The count check is robust to the many natural phrasings of an *uncorrected* label (a transparent submission that reports both an uncorrected and a corrected count is judged on the corrected headline, not penalised for the nominal one), and to significant counts hidden as a fraction/percent (converted back to an absolute edge count). It keys on the concluded number the submission stands behind, so a name-drop of "correction" without actually reporting the corrected ~0 does not pass. Harden further against the real GPT/Claude texts at gate calibration.

### Cost

`hard`. cpus 2, mem 8 GB, internet on (ABIDE Dosenbach-160 ROI time series + Dosenbach coord/label atlas — small, reliable S3 host; downloads then cached). Deps: nilearn 0.12.1 + numpy/scipy/pandas/nibabel. Timeouts generous (one Dosenbach-160 correlation matrix per subject over ~850 subjects).
