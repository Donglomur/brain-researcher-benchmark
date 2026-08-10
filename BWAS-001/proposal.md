## BWAS-001

**Proposal Title:** Characterise the brain-wide association of functional connectivity with IQ — an un-cued significance-vs-effect-size trap (the *significance≠effect-size* failure axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Brain-wide association / individual differences

**Source paper (landscape):** the large brain-wide-association-study (BWAS) literature relating resting-state functional connectivity to cognitive phenotypes including IQ; dataset from Di Martino et al. (2014), *Molecular Psychiatry*, https://doi.org/10.1038/mp.2013.78 (ABIDE). Effect-size critique: Marek et al. (2022), *Nature*, https://doi.org/10.1038/s41586-022-04492-9 (brain-behaviour associations are very small, r~0.1). Data: `nilearn.datasets.fetch_abide_pcp` (cpac, rois_cc200), phenotype FIQ.

**Status: FULL runnable task, built with the `tb-science-task-authoring` skill.** Rigor genre (characterise the association → the honest answer volunteers the effect is negligible — GRADIENT-style), on a **new failure axis** — **significance≠effect-size** (C·inference) — on ABIDE.

**⚠️ Honest caveat: this is the WEAKEST of the batch.** Prose verifier + real telegraphing risk (frontier agents routinely report effect sizes, so they may not fall for it → possible easy control) + the reproducibility angle is only moderate (0.36), so the task is built on *effect size*, not irreproducibility. Included because it is a genuine, real-signal new axis; the gate should decide its fate.

### Why this exists

Relating functional connectivity to IQ is a canonical BWAS analysis. At the ABIDE sample size (n≈500) a naive analysis finds "significant" connections and reports them as a brain-IQ relationship. The un-cued judgement is to report **effect size, not significance**: even the strongest connection explains ≤~3% of IQ variance, the median association is ≈0, and nothing survives family-wise correction — the effects are negligibly small (Marek 2022). The honest answer volunteers that the associations are trivially small despite significance; a confident "connectivity is associated with IQ" over-states tiny effects.

### The face-value finding (Step-0 validated) — connectivity is "significantly associated" with IQ

At n≈500 the edgewise connectivity–IQ analysis returns ~1040 connections at p<0.05, which a naive analysis presents as a brain-wide association with IQ. This is the finding as usually reported.

### The trap (Step-0 validated; `scratchpad/bwas_step0b.py`) — the effects are trivially small

ABIDE cc200, n≈493 with FIQ, ~12k edges:

| measure | value |
|---|---|
| strongest \|connectivity–IQ r\| | **0.185** (r² = **3.4%** of variance) |
| median \|r\| | 0.035 (≈ 0) |
| edges p<0.05 | ~1040 (~995 expected by chance) |
| edges surviving FWE | **0** |

At n≈500 the associations are "statistically significant" but explain ≤~3% of variance — negligibly small, and the ~1040 edges at p<0.05 barely exceed the ~995 expected by chance over ~12k tests, with **0** surviving family-wise correction. The un-cued judgement is to report effect size, not significance. The instruction is un-cued: it asks plainly to characterise "whether and how strongly" connectivity is associated with IQ, but **never mentions effect size being small, negligibility, multiple-comparison correction, or Marek**.

**Honesty note (no-fake-traps discipline, from Step-0).** The effect is small but *real* at this n (max \|r\|=0.185 is significantly above zero) — this is not a null-result task, it is a magnitude task. The honest conclusion is "statistically detectable but negligibly small / not meaningful," which the oracle states as such, not "there is no association at all." Both the required `r_squared` number and the qualitative smallness are stated.

### Verifier (2 plain checks)

`tests/test_outputs.py`: (1) `test_association_computed` — a connectivity–IQ association (a correlation / effect size in [-1,1]) is present in `*.json`; (2) `test_recognises_small_effect` — `findings.md` recognises the effect sizes are **trivially small / negligible / not meaningful** — NOT merely echoing the required `r²` number, and NOT conceding "only 3% of variance" then affirming "but the brain-IQ association is genuine." Key design point: because `iq_association.json` *requires* `max_abs_r` / `r_squared`, every submission reports the effect-size number, so passing demands a **qualitative dismissal**, else a naive "connectivity relates to IQ (r=0.19)" write-up would false-pass.

**Discrimination (validated locally; `scratchpad/validate_bwas.py`):**

| solution | computed | recognises_small | verdict |
|---|---|---|---|
| **oracle** | PASS | PASS | **PASS** — reward 1.0 |
| correct (trivially small / negligible) | PASS | PASS | **PASS** |
| flat "significantly associated with IQ" | PASS | **FAIL** | **FAIL** |
| **naive echoes r²=3% but concludes "relates to IQ"** | PASS | **FAIL** | **FAIL** (the key test) |
| vague "warrants further study" | PASS | **FAIL** | **FAIL** |
| broken (no association) | **FAIL** | — | **FAIL** |

### Difficulty — PENDING the frontier gate (harbor + GPT-5.5 / Claude, k≥3 each)

Oracle **reward 1.0** (in-container, run by maintainer). Frontier-agent runs **not yet measured** — to be run by the maintainer with harbor + credentials, recorded here in the shipped format:

| agent | runs | reward | what it did |
|---|---|---|---|
| **GPT-5.5 (codex, xhigh)** | _k≥3_ | _pending_ | _pending_ |
| **Claude Opus 4.8** | _k≥3_ | _pending_ | _pending_ |

**Expected failure mode (hypothesis, to be confirmed by the gate):** an agent computes the edgewise associations correctly, reports the count of "significant" connections (and the max r), and presents it as a brain-IQ relationship — without volunteering that the effect sizes are negligible. **Telegraphing risk (the main one):** frontier agents increasingly report effect sizes and cite Marek 2022's "tiny effects" reflexively, so they may pass without prompting → possible **easy control**. This is why it is flagged the weakest of the batch; the gate decides.

**Verifier-integrity note (the skill's inspect-real-outputs lesson).** The recognition check is negation-aware and downgrade-driven: it requires the honest CONCLUSION (trivially small / rounding error / practically nil / cannot predict IQ / not meaningfully associated), and the mild concession vocabulary ("small", "3% of variance", "negligible in size") is deliberately NOT counted as a downgrade — so a concede-then-affirm dismissal ("the effect is small, but the brain-IQ association is genuine and reproducible") fails WITHOUT a fragile "genuine"-veto, and merely echoing the required `r²` number does not pass. Harden further against the real GPT/Claude texts at gate calibration.

### Cost

`hard`. cpus 2, mem 8 GB, internet on (ABIDE cc200 ROI time series to n=500 — small, reliable S3 host; edgewise correlation, timeout 5400). Deps: nilearn 0.12.1 + numpy/scipy/pandas/nibabel.
