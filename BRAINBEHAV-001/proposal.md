## BRAINBEHAV-001

**Proposal Title:** Characterise the brain-wide association of functional connectivity with IQ — an un-cued significance-vs-effect-size trap (the *significance≠effect-size* failure axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Brain-wide association / individual differences

**Source paper (landscape):** the large brain-wide-association-study (BWAS) literature relating resting-state functional connectivity to cognitive phenotypes including IQ; dataset from Di Martino et al. (2014), *Molecular Psychiatry*, https://doi.org/10.1038/mp.2013.78 (ABIDE). Effect-size critique: Marek et al. (2022), *Nature*, https://doi.org/10.1038/s41586-022-04492-9 (brain-behaviour associations are very small, r~0.1). Data: ABIDE cc200 (`nilearn.datasets.fetch_abide_pcp`, cpac, rois_cc200), phenotype FIQ — **packaged offline** for this task (see below).

**Status: FULL runnable task, built the shipped way (route-b, offline), modelled on TOPEDGES-001 / GMATROPHY-001.** Rigor genre (characterise the association → the honest answer volunteers the effect is negligible — GRADIENT-style), on the **significance≠effect-size** failure axis (C·inference), on ABIDE.

**⚠️ Honest caveat (unchanged): this is among the weaker of the batch.** The un-cued judgement (report effect size, not significance) is one frontier agents increasingly volunteer reflexively (they cite Marek 2022's "tiny effects"), so it may be an **easy control**. Included because it is a genuine, real-signal axis; the gate decides its fate.

### Why this exists

Relating functional connectivity to IQ is a canonical BWAS analysis. At the ABIDE sample size a naive analysis finds "significant" connections and reports them as a brain-IQ relationship. The un-cued judgement is to report **effect size, not significance**: even the strongest connection explains only a few percent of IQ variance, the median association is ≈0, and the count of "significant" connections collapses under multiple-comparison correction — the effects are negligibly small (Marek 2022). The honest answer volunteers that the associations are trivially small despite significance; a confident "connectivity is associated with IQ" over-states tiny effects.

**Honesty note (no-fake-traps discipline).** The effect is small but *real* at this n (the strongest |r| is significantly above zero and a couple of edges survive family-wise correction) — this is a **magnitude** task, not a null-result task. The honest conclusion is "statistically detectable but negligibly small / not meaningful," which the oracle states as such, not "there is no association at all."

### The reproduction and the trap (validated) — held privately

The validated numbers (n, strongest |r| / r², median |r|, the p<0.05 vs family-wise-corrected counts) and the oracle receipt are in the **private, git-ignored `calibration.md`** (rule 4). In brief: the edgewise connectivity–IQ analysis returns many connections at p<0.05 (a face-value brain-IQ association), but the effect sizes are trivially small (the strongest explains only a few percent of variance, the median ≈0) and the significant count collapses under correction. The instruction is **un-cued**: it asks plainly to characterise "whether and how strongly" connectivity is associated with IQ, and **never mentions** effect-size smallness, negligibility, multiple-comparison correction, or Marek.

### Data (route-b, offline)

Packaged as `data/cc200_bwas.npz` by `data/build_bwas.py` (subsets the shared ABIDE cc200 bundle to subjects with valid FIQ + a finite connectome; stores `X` = subjects × 19,900 Fisher-z edges and `fiq`, float32). The shipped task reads only that local file — **no network** (`allow_internet = false`).

### Verifier (2 checks; data-validating)

`tests/test_outputs.py`: (1) `test_association_computed` — validates the ACTUAL data: it **re-computes the strongest |r| / r² from the packaged connectomes** and requires the report to be consistent (a plausible-but-fabricated tiny or inflated effect FAILS — **maintainer repair #6**), checks n and correlation ranges, validates any reported ROI-pairs / per-edge table, and — where both an uncorrected and a corrected significant-count are given — requires correction to shrink the count. (2) `test_recognises_small_effect` — negation-aware, downgrade-driven: `findings.md` must recognise the effect sizes are **trivially small / negligible / not meaningful** — NOT merely echoing the required `r²` number, and NOT conceding "only 3% of variance" then affirming "but the brain-IQ association is genuine."

**Discrimination (validated locally, offline):**

| solution | data check | recognises_small | verdict |
|---|---|---|---|
| **oracle** | PASS | PASS | **PASS** |
| correct (trivially small / negligible) | PASS | PASS | **PASS** |
| naive echoes r² but concludes "relates to IQ" | PASS | **FAIL** | **FAIL** (the key test) |
| flat "significantly associated with IQ" | PASS | **FAIL** | **FAIL** |
| fabricated (max \|r\| inconsistent with the data) | **FAIL** | — | **FAIL** |
| empty | **FAIL** | — | **FAIL** |

### Difficulty — PENDING the frontier gate (harbor + GPT-5.5 / Claude, k≥3 each)

Oracle **reward 1.0** (offline, run by maintainer). Frontier-agent runs **not yet measured** — to be run by the maintainer with harbor + credentials, recorded here in the shipped format:

| agent | runs | reward | what it did |
|---|---|---|---|
| **GPT-5.5 (codex, xhigh)** | _k≥3_ | _pending_ | _pending_ |
| **Claude Opus 4.8** | _k≥3_ | _pending_ | _pending_ |

**Expected failure mode (hypothesis):** an agent computes the edgewise associations correctly, reports the count of "significant" connections (and the max |r|), and presents it as a brain-IQ relationship — without volunteering that the effect sizes are negligible. **Telegraphing risk (the main one):** frontier agents increasingly report effect sizes and cite Marek 2022 reflexively → possible **easy control**. This is why it is flagged among the weakest; the gate decides.

### Cost

`hard`. cpus 2, mem 8 GB, **internet off** (packaged cc200 bundle; edgewise correlation over ~19,900 edges × ~925 subjects). Deps: numpy/scipy (+ pandas/nibabel/nilearn in the image, unused at run).
