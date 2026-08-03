## AUTCONN-001

**Proposal Title:** Group resting-state connectivity differences in autism (ABIDE) — an un-cued multiple-comparisons inflation (the *cluster/multiple-comparisons* failure axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Case-control resting-state functional connectivity

**Source finding:** Di Martino et al. (2014), *Molecular Psychiatry*, https://doi.org/10.1038/mp.2013.78 (ABIDE — large multi-site autism resting-state resource). Multiple-comparisons references: Eklund et al. (2016, *PNAS*, cluster failure); Bennett et al. (2009, the "dead-salmon" demonstration). Data: `nilearn.datasets.fetch_abide_pcp` (cpac, rois_cc200).

**Status: FULL runnable task, built with `tb-science-task-authoring`.** Opens a **new failure axis** — **multiple comparisons / cluster inflation** (the statistical-inference family) — on a **new dataset** (ABIDE, which downloads reliably from `s3.amazonaws.com/fcp-indi`). Distinct topic (*multiple comparisons* / *cluster inference*) and axis from every shipped task.

**Difficulty vs frontier agents: NOT YET MEASURED.** The gate (GPT-5.5 xhigh + Claude Opus, k≥3) needs Harbor + credentials, deferred. This documents Step-0 (real, measured) and the oracle/adversarial calibration (local).

### Why this exists
No shipped task covers the multiple-comparisons axis. This fills it with the canonical pitfall: reporting "significant" case-control connectivity differences at an uncorrected threshold, over ~20,000 simultaneous edge tests.

### The trap (Step-0 validated; `scratchpad/new_multcomp.py`)
ABIDE cc200, ASD (n≈149) vs TD (n≈151), **19900 edges**, edgewise Welch t-test:

| threshold | "significant" edges | note |
|---|---|---|
| uncorrected p<0.05 | **2486** | ~995 expected by chance |
| uncorrected p<0.001 | 262 | |
| FDR q<0.05 | 123 | |
| FWE (Bonferroni) | **7** | the honest count |

Reporting the 2486 uncorrected edges over-claims by ~350×; only 7 survive strict correction.

### Verifier (2 plain checks) + local calibration
`tests/test_outputs.py`: (1) a full edgewise comparison was run (~19900 edges); (2) the reported number of significantly-differing connections reflects multiple-comparisons correction — i.e., the concluded count is **≤ 250** (FWE ~7 / FDR ~123), not the uncorrected ~262 / ~2486. Enforced **numerically** on the reported count (excludes any field the submission labels "uncorrected"; counts list-lengths for edge lists; ignores edge *index values*).

Local calibration (`scratchpad/validate_autconn.py`):

| output | computed | corrected |
|---|---|---|
| **oracle** (FWE 7 / FDR 123) | PASS | PASS — reward 1.0 |
| honest FDR (123) | PASS | PASS |
| honest FWE (7) + labeled uncorrected | PASS | PASS |
| naive uncorrected p<0.05 (2486) | PASS | **FAIL** |
| naive uncorrected p<0.001 (262) | PASS | **FAIL** |
| listed 300 uncorrected edges | PASS | **FAIL** |
| broken (no edgewise analysis) | **FAIL** | — |

### Honest caveats / open risks
1. **Difficulty UNTESTED** — needs the gate.
2. **Telegraphing risk:** multiple-comparisons correction may already be in frontier priors (like leakage; cf. LEAK-DI easy control). The gate decides whether agents volunteer it un-cued.
3. Verifier threshold (250) sits between FDR (~123) and uncorrected-p<0.001 (~262); harden against real agent output shapes at calibration.

### Cost
`hard`. cpus 2, mem 8 GB, internet on (ABIDE cc200 ROI time series — small, reliable S3 host). Deps: nilearn 0.12.1 + numpy/scipy/pandas/nibabel.
