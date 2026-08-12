## AUTISMDMN-001

**Proposal Title:** Whole-brain ASD-vs-control connectivity differences (ABIDE Dosenbach-160) — an un-cued multiple-comparisons inflation over ~12,720 confound-adjusted edge tests (the *over-claim / statistical-rigor* failure axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Autism resting-state functional connectivity

**Source paper:** Assaf et al. (2010), *NeuroImage*, https://doi.org/10.1016/j.neuroimage.2010.05.067 — reduced functional connectivity within default-mode sub-networks (PCC/mPFC) in ASD, one of the most-cited ASD intrinsic-connectivity findings. Reproducibility critique: King et al. (2019), *Molecular Autism*. Multiple-comparisons critique: Eklund et al. (2016), *PNAS*. Cohort context: Di Martino et al. (2014), *Molecular Psychiatry* (ABIDE). Dataset: `nilearn.datasets.fetch_abide_pcp` (cpac, rois_dosenbach160), precomputed to an offline connectome bundle.

**Status: FULL runnable task, rebuilt to the maintainer's VALIDITY standard (route-b offline: reads a packaged `data/*.npz`, real effect size, oracle emits per-item data the verifier CHECKS, `allow_internet=false`, answer in git-ignored `calibration.md`).** Failure axis **multiple-comparisons inflation** (statistical-inference family). Topic *ASD connectivity*, ABIDE.

### Why this exists

"Which resting-state connections differ between ASD and controls" is a textbook case-control analysis. In ABIDE the groups differ in head motion and are pooled across 20 acquisition sites, so a valid contrast must **control site, age, sex and motion** per edge. The un-cued judgement is that the ~12,720 edges are tested **simultaneously**, so the count of "significant" connections must be **corrected for multiplicity** — after which the uncorrected flood of "differences" collapses to a small, sparse set (the large majority of uncorrected hits are false positives). Exactly the shipped rigor pattern: the agent runs the confound-adjusted contrast, gets a large uncorrected count, and fails only if it does not *volunteer* the multiple-comparisons correction the instruction never mentions.

### The reproduction / trap (validated) — held privately

The validated numbers (n per group, uncorrected vs FDR vs FWE edge counts, the direction of the surviving edges, and the within-DMN Assaf test) and the oracle receipt are in the **private, git-ignored `calibration.md`** (rule 4). In brief: a confound-adjusted whole-brain edgewise ASD-vs-TD comparison flags **many hundreds** of connections at an uncorrected threshold (~half of them expected by chance), but after FDR/FWE correction only a **small, sparse** set survives — all in the ASD-hypoconnectivity direction. The within-DMN (Assaf 2010) mean is numerically lower in ASD (Assaf's direction) but non-significant. The instruction is un-cued (never mentions multiple-comparisons correction).

**Data-honesty note.** On the shared quality-checked=False Dosenbach-160 bundle (larger, higher-motion than the original 846-subject quality-checked set) a small number of edges genuinely survive strict correction — a real but sparse effect, stable across defensible motion-exclusion thresholds. Per the validity standard the task ships that honest ground truth (the exact counts are in `calibration.md`): the multiple-comparisons **over-claim** trap holds strongly (uncorrected hundreds → a handful corrected), and the honest headline is the corrected count, not the uncorrected one.

### Verifier (3 checks)

`tests/test_outputs.py`: (1) `test_group_comparison_computed` — a full edgewise comparison (≥5000 edges) with a reported significant count; validates the ACTUAL data (any listed significant edges are valid Dosenbach ROI-pairs in `[0,159]`; `n_subjects` plausible; a corrected count cannot exceed the reported uncorrected count). (2) `test_significance_corrected_for_multiplicity` — the reported headline count must reflect correction (small), **not** the uncorrected p<0.05 range; the extractor excludes `uncorrected`-labelled fields and converts a significant *fraction/percent* back to an absolute edge count so an uncorrected fraction cannot hide as ~0. (3) `test_recognises_multiple_comparisons` — negation-aware, downgrade-driven: `findings.md` must couple the multiplicity concept to a downgrade (uncorrected count inflated / mostly false positives / collapses after correction / only a small set survives), not a flat "N connections differ" nor a name-drop that still stands behind the uncorrected count.

**Discrimination (validated locally; exact counts in `calibration.md`):**

| solution | verdict |
|---|---|
| reference (confound-adjusted contrast; reports the uncorrected count then volunteers that correction collapses it to a small set) | **PASS** |
| genuine "many uncorrected but only a handful after FDR/FWE → most uncorrected hits are false positives" | **PASS** |
| flat "~hundreds/thousands of connections significantly differ (p<0.05)" (uncorrected count) | **FAIL** |
| significant *fraction* reported as the result (converts back to the uncorrected count) | **FAIL** |
| fabricated (out-of-range ROI pairs / corrected exceeding uncorrected) | **FAIL** |

### Difficulty — PENDING the frontier gate (harbor + GPT-5.5 / Claude, k≥3 each)

Oracle **reward 1.0** (offline, in-container). Frontier-agent runs **not yet measured** — to be run by the maintainer with harbor + credentials, recorded here in the shipped format:

| agent | runs | reward | what it did |
|---|---|---|---|
| **GPT-5.5 (codex, xhigh)** | _k≥3_ | _pending_ | _pending_ |
| **Claude Opus 4.8** | _k≥3_ | _pending_ | _pending_ |

**Expected failure mode (hypothesis, to be confirmed by the gate):** both families run the confound-adjusted edgewise contrast correctly and report the uncorrected count (hundreds–thousands of "significant" connections) as the group difference, without volunteering the multiple-comparisons correction over ~12,720 tests that collapses it to a handful. **Telegraphing risk:** "correct for multiple comparisons" is a well-known reflex, so this axis may prove easier for frontier agents than the confound axes — the gate will decide; if it is easy, that is recorded honestly.

**Verifier-integrity note (the skill's inspect-real-outputs lesson).** The count check is robust to the many natural phrasings of an *uncorrected* label (a transparent submission that reports both an uncorrected and a corrected count is judged on the corrected headline), and to significant counts hidden as a fraction/percent (converted back to an absolute edge count). It keys on the concluded number the submission stands behind, so a name-drop of "correction" without actually reporting the corrected count does not pass. Harden further against the real GPT/Claude texts at gate calibration.

### Cost

`hard`. cpus 2, mem 8 GB, **internet off** (offline packaged connectome bundle `data/dos160_autconn.npz`, ~22 MB). Deps: numpy + scipy only (no nilearn/network at run time). Timeouts generous (one vectorised per-edge OLS over ~945 subjects × 12,720 edges, plus a small per-edge fallback for degenerate-ROI NaN edges).
