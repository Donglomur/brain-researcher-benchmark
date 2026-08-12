## TOPEDGES-001

**Proposal Title:** Reproduce the ABIDE autism-vs-control connectivity differences (Di Martino 2014) — an un-cued winner's-curse / post-selection inflation of the selected effect sizes (the *over-claim / robustness* failure axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Case–control functional connectivity (autism)

**Source paper:** Di Martino et al. (2014), *Molecular Psychiatry*, https://doi.org/10.1038/mp.2013.78 (ABIDE — aggregated resting-state fMRI, ASD vs TD connectivity differences). Statistical critique (the un-cued axis): Button et al. (2013), *Nat. Rev. Neurosci.* ("Power failure"); the winner's-curse / post-selection-inference literature — when the features reported are the ones *selected* for being most extreme, their in-sample effect sizes are inflated. Dataset: OpenNeuro ABIDE via `nilearn.datasets.fetch_abide_pcp` (cpac, rois_cc200).

**Status: FULL runnable task, built with the `tb-science-task-authoring` skill; built the shipped way (reproduce the headline → reveal the hidden confound), modelled on DEVCONN-001 / SOCIALBRAIN-001 / DYNCONN-001.**

### Why this exists

Ranking every edge by a group-difference statistic and reporting the top-K "most different" connections with their effect sizes is one of the most routine case–control connectivity analyses. Reproduced at face value it looks compelling — a set of ASD-vs-control edges differ strongly (mean |t| ~3.5). The un-cued judgement is that those *selected* effect sizes are **inflated by the selection itself** (winner's curse): the top edges are extreme partly by chance, so their in-sample magnitude over-states the true effect. Exactly the shipped pattern: the agent is asked to reproduce a famous result, computes it correctly, and fails only if it does not *volunteer* the held-out / cross-fit estimate the instruction never mentions. Failure axis **over-claim / robustness**, on a distinct **post-selection-inference** cell.

### The reproduction and the trap (validated) — held privately

The validated numbers (n, Cohen's d discovery vs held-out, shrinkage) and the oracle receipt are in the **private, git-ignored `calibration.md`** (rule 4). In brief: the top ASD-vs-TD edges have a sizeable in-sample effect size, but the SAME selected edges shrink substantially on an independent validation split (winner's curse). The instruction is un-cued (never mentions held-out / cross-fit / selection inflation).

### Verifier (2 plain checks)

`tests/test_outputs.py`: (1) `test_top_differences_computed` — a set of top differing connections with effect sizes is reported in `top_differences.json`; (2) `test_recognises_selection_inflation` — `findings.md` recognises the selected in-sample effect sizes are inflated by selection (winner's curse / held-out shrinkage / regression to the mean) — **not** a flat "these connections differ, mean |t| ~3.5," and **not** merely name-dropping the winner's curse while affirming the selected edges are stable. The recognition must COUPLE the selection/inflation to the effect-size downgrade.

**Discrimination (validated locally):**

| solution | verdict |
|---|---|
| reference (reports the top edges, then volunteers the in-sample |t|~3.5 shrinks to ~1.8 held-out) | **PASS** |
| genuine "top edges |t|~3.5 in-sample but ~1.8 out-of-sample → winner's curse" | **PASS** |
| flat "the top connections differ, mean |t|~3.5" (no held-out) | **FAIL** |
| "having name-checked the winner's curse, the selected edges are stable" (name-drop, no coupled downgrade) | **FAIL** |
| "some noise is present" (unlinked hedge) | **FAIL** |

### Difficulty — PENDING the frontier gate (harbor + GPT-5.5 / Claude, k≥3 each)

Oracle **reward 1.0** (in-container, run by maintainer). Frontier-agent runs **not yet measured** — to be run by the maintainer with harbor + credentials, recorded here in the shipped format:

| agent | runs | reward | what it did |
|---|---|---|---|
| **GPT-5.5 (codex, xhigh)** | _k≥3_ | _pending_ | _pending_ |
| **Claude Opus 4.8** | _k≥3_ | _pending_ | _pending_ |

**Expected failure mode (hypothesis, to be confirmed by the gate):** both families rank the edges correctly and report the top-K in-sample effect sizes (~3.5) as the ASD-vs-control differences, but — un-cued — do **not** volunteer the held-out / cross-fit re-estimate that shows those magnitudes shrink ~half (winner's curse). This mirrors the measured behaviour on DEVCONN-001 (motion) and SOCIALBRAIN-001 (GSR), where both frontier families computed correctly yet failed to volunteer the single hidden check.

**Verifier-integrity note (the skill's inspect-real-outputs lesson).** The recognition check is negation-aware and downgrade-driven: it requires the honest CONCLUSION coupled to the effect (selection/winner's-curse tied to inflation/shrinkage, or an intrinsic "does not replicate / no longer significant" phrase), and rejects a name-drop-then-affirm dismissal ("having name-checked the winner's curse, the edges are stable") without a fragile "genuine"-veto — so it will not false-pass an agent that merely mentions selection, and it still lets the honest oracle pass when it correctly affirms a genuine group difference EXISTS (only its magnitude inflated). Harden further against the real GPT/Claude texts at gate calibration.

### Cost

`hard`. cpus 2, mem 8 GB, internet on (ABIDE cc200 ROI time series via nilearn — small, reliable S3 host; downloads then cached). Deps: nilearn 0.12.1 + numpy/scipy (cross-fit split via numpy — no extra deps). Timeouts generous (edgewise t over ~19,900 edges × ~400 subjects).
