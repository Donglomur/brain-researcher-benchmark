## COGVBM-001

**Proposal Title:** Gray-matter correlates of cognition (OASIS VBM) — an un-cued multiple-comparisons inflation (the *multiple-comparisons* axis on a new **structural** modality)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Structural MRI / brain-behaviour VBM

**Source finding:** Marcus et al. (2007, OASIS); multiple-comparisons references: Eklund et al. (2016, cluster failure); Bennett et al. (2009, dead salmon). Data: `nilearn.datasets.fetch_oasis_vbm` (VBM gray-matter maps + MMSE + age).

**Status: FULL runnable task, built with `tb-science-task-authoring`.** Fills a **new axis×modality cell** — **multiple comparisons × structural VBM**. The axis (multiple comparisons) is shipped (AUTCONN, fMRI connectivity); here it is on the **structural modality** and a whole-brain **voxelwise** search (~176k tests), which is the classic Eklund/dead-salmon setting.

**Difficulty vs frontier agents: NOT YET MEASURED** (gate deferred).

### The trap (Step-0 validated; `scratchpad/struct_mc_step0.py`)
OASIS VBM, ~176k voxels, n~150 with MMSE, partial correlation MMSE~gray-matter | age:

| threshold | "significant" voxels |
|---|---|
| uncorrected p<0.05 | **17,470** (~8,819 by chance) |
| uncorrected p<0.001 | 1,289 (~176 by chance) |
| FDR q<0.05 | 5 |
| FWE (Bonferroni) | **0** |

An uncorrected report claims thousands of gray-matter–cognition voxels; **0 survive FWE** (5 under FDR). Even more dramatic than AUTCONN (17470→0 vs 2486→7).

### Verifier (2 plain checks) + local calibration
`tests/test_outputs.py`: (1) a whole-brain voxelwise search was run (~176k voxels); (2) the reported number of MMSE-associated voxels reflects multiple-comparisons correction (≤100 — FWE 0 / FDR ~5), not the uncorrected ~1289/17470. Enforced **numerically** (excludes fields labelled "uncorrected"; same robust extractor as AUTCONN).

Local calibration (`scratchpad/validate_cogvbm.py`):

| output | computed | corrected |
|---|---|---|
| **oracle** (FWE 0 / FDR 5) | PASS | PASS — reward 1.0 |
| honest FDR (5) | PASS | PASS |
| honest FWE (0) + labelled uncorrected | PASS | PASS |
| naive uncorrected p<0.001 (1289) | PASS | **FAIL** |
| naive uncorrected p<0.05 (17470) | PASS | **FAIL** |
| broken (no voxelwise search) | **FAIL** | — |

### Honest caveats / open risks
1. **Difficulty UNTESTED** — needs the gate. Telegraphing: correction may be in frontier priors (cf. AUTCONN).
2. **Multiple-comparisons axis reused** (2nd, after AUTCONN) — but on a **new modality** (structural, whole-brain voxelwise), a distinct and canonical setting (Eklund).
3. Clean null-ish target: MMSE~GM has essentially no effect after correction (0 FWE / 5 FDR), so the uncorrected voxels are overwhelmingly false positives — a strong, unambiguous trap.

### Cost
`hard`. cpus 2, mem 8 GB, internet on (OASIS VBM ~900 MB one-time from NITRC; voxelwise correlation over ~176k voxels, timeout 5400). Deps: nilearn 0.12.1 + numpy/scipy/pandas/nibabel.
