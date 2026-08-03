## BWAS-001

**Proposal Title:** Functional connectivity vs IQ (ABIDE) — un-cued significance-vs-effect-size (tiny brain-wide-association effects) (the *significance≠effect-size* failure axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Brain-wide association / individual differences

**Source finding:** Marek et al. (2022), *Nature*, https://doi.org/10.1038/s41586-022-04492-9 (brain-wide association studies: brain-behaviour effects are very small); Di Martino et al. (2014, ABIDE). Data: `nilearn.datasets.fetch_abide_pcp` (cpac, rois_cc200), phenotype FIQ.

**Status: FULL runnable task, built with `tb-science-task-authoring`.** Opens a **new failure axis** — **significance≠effect-size** (C·inference) — on ABIDE.

**⚠️ Honest caveat: this is the WEAKEST of the 7-task batch.** Prose verifier + real telegraphing risk (frontier agents routinely report effect sizes, so they may not fall for it → possible easy control) + the reproducibility angle is only moderate (0.36), so the task is built on *effect size*, not irreproducibility. Included because it is a genuine, real-signal new axis; the gate should decide its fate first.

**Difficulty vs frontier agents: NOT YET MEASURED** (gate deferred).

### The trap (Step-0 validated; `scratchpad/bwas_step0b.py`)
ABIDE cc200, n~493 with FIQ, ~12k edges:

| measure | value |
|---|---|
| strongest \|connectivity–IQ r\| | **0.185** (r² = **3.4%** of variance) |
| median \|r\| | 0.035 (≈ 0) |
| edges p<0.05 | ~1040 (~995 expected by chance) |
| edges surviving FWE | **0** |

At n≈500 the associations are "statistically significant" but explain ≤~3% of variance — negligibly small. The un-cued judgement is to report effect size, not significance.

### Verifier (2 plain checks) + local calibration
`tests/test_outputs.py`: (1) a connectivity–IQ association was computed; (2) `findings.md` recognises the effect sizes are **trivially small / negligible** — NOT merely echoing the required `r²` number. Key design point: because `iq_association.json` *requires* `max_abs_r`/`r_squared`, the check demands a **qualitative dismissal**, else a naive "connectivity relates to IQ (r=0.19)" write-up would false-pass.

Local calibration (`scratchpad/validate_bwas.py`):

| output | computed | recognises_small |
|---|---|---|
| **oracle** | PASS | PASS — reward 1.0 |
| correct (trivially small / negligible) | PASS | PASS |
| flat "significantly associated with IQ" | PASS | **FAIL** |
| **naive echoes r²=3% but concludes "relates to IQ"** | PASS | **FAIL** ✅ (the key test) |
| vague "warrants further study" | PASS | **FAIL** |
| broken (no association) | **FAIL** | — |

### Cost
`hard`. cpus 2, mem 8 GB, internet on (ABIDE cc200 ROI time series to n=500 — small, reliable S3 host; edgewise correlation, timeout 5400). Deps: nilearn 0.12.1 + numpy/scipy/pandas/nibabel.
