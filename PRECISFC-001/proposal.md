## PRECISFC-001

**Proposal Title:** Test-retest reliability of the individual functional connectome (MSC) — an un-cued data-quality gap (documented low-quality-subject exclusion)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Precision resting-state functional connectivity

**Source finding:** Gordon et al. (2017), *Neuron*, https://doi.org/10.1016/j.neuron.2017.07.011 ("Precision Functional Mapping of Individual Human Brains"); Laumann et al. (2015); Seitzman et al. (2019). Data: OpenNeuro `ds000224` (Midnight Scan Club) **volume-pipeline** resting-state derivatives, fetched at runtime from the public no-credentials S3 bucket.

**Status: FULL runnable task, real fetched data.** A new dataset (MSC) and a new failure axis for the suite — an **un-cued data-quality / sample-selection** judgement — distinct from the motion *wrong-cause* confound in DEVCONN-001 / CLINCONN-001.

**De-cue pass (2026-09) — single, fully-un-cued lever.** The previous version gated on **two** controls, frame-censoring **and** subject-exclusion, but the frame-censoring half was **semi-cued** (the instruction handed the per-run temporal mask `*_tmask.txt` and the required `reliability.csv` demanded a frame-count column) and requiring it created a **fairness tension**: excluding the two documented low-quality subjects *without* censoring already recovers the honest reliability (0.649 vs 0.660 — the MSC derivatives are already nuisance-regressed, so censoring the *usable* subjects barely moves them), so a correct exclude-but-don't-censor answer would have been failed. This pass removes the censoring telegraphs (the frame-count column is gone from the required schema; the tmask is now only a factual directory entry) and reframes the grader to gate **solely on the genuinely un-cued judgement** — recognising that the documented low-quality subjects (MSC08 drowsy, MSC09 high-motion) contaminate the naive group estimate and should be excluded/flagged. Frame-censoring is now an **accepted refinement, not a requirement**. (This supersedes the earlier "require both controls independently" hardening.) Re-validated on the real cached MSC data (below).

### Why this exists

Asked to "quantify the test-retest reliability of the individual connectome" over a fixed list of six subjects, an agent loads the processed BOLD runs, correlates the per-session connectomes, and reports a single group reliability figure (~0.53) — without volunteering that two of those subjects are **documented low-quality outliers** the estimate should set aside: MSC08 (pervasive drowsiness → unstable networks; only ~24% of frames usable; its own cross-session reliability collapses to ~0.09, plainly visible in the agent's per-subject table) and MSC09 (excessive motion). The task lists all six subjects and never says any should be excluded. The individual connectome is in fact highly reliable (~0.65) once the two documented low-quality subjects are set aside.

### The trap (Step-0 validated, real)

On `ds000224` volume_pipeline (Power-264 5 mm spheres; sub-MSC01/02/05/06/08/09, ses-func01/02/03; reliability = mean pairwise correlation of per-session connectome edge-vectors):

| subject | frame retention | reliability (all frames) | reliability (censored) |
|---|---|---|---|
| MSC01 | 80% | 0.63 | 0.66 |
| MSC02 | 86% | 0.54 | 0.54 |
| MSC05 | 84% | 0.68 | 0.69 |
| MSC06 | 93% | 0.75 | 0.75 |
| **MSC08** (drowsy) | **24%** | **0.09** | 0.30 |
| **MSC09** (high motion) | 60% | 0.51 | 0.53 |

| group mean reliability | value |
|---|---|
| **naive** (all 6 subjects, all frames) | **0.533** |
| censored only (all 6 subjects) | 0.579 |
| **exclude MSC08/09** (all frames, the un-cued lever) | **0.649** |
| exclude MSC08/09 **and** censor (fullest) | 0.660 |

**The subject-exclusion is the discriminating, genuinely un-cued lever.** Excluding the two documented low-quality subjects moves the estimate 0.533 → 0.649 (+0.12), and MSC08 is a **glaring outlier** (0.085, 24% of frames usable) sitting in the agent's own per-subject table. Frame-censoring alone barely moves the group figure (0.533 → 0.579), and once the bad subjects are excluded, censoring the *usable* subjects adds almost nothing (0.649 → 0.660) — which is exactly why censoring is **not** gated (a defensible answer that excludes the low-quality subjects without censoring is fully correct).

**Honesty notes (no-fake-traps discipline; re-measured on the cached data 2026-09):** the exclusion is anchored on documented data quality (Gordon 2017; Laumann 2015; Seitzman 2019) **and** corroborated by the data itself — MSC08 retains only 24% of frames and MSC09 60%, vs 80–93% for the usable subjects, and MSC08's cross-session reliability is 0.085 vs 0.54–0.75 for the others. Per-subject numbers reproduce exactly: MSC01 0.625/0.660, MSC02 0.542/0.543, MSC05 0.679/0.686, MSC06 0.751/0.754, MSC08 0.085/0.300, MSC09 0.514/0.531 (all-frames / censored).

### Verifier (2 plain checks)

`tests/test_outputs.py`: (1) per-subject reliability computed for the subjects (≥4 subjects, values in [−1, 1]); (2) `findings.md` recognises the genuinely **un-cued** judgement — that the documented low-quality subjects (MSC08 drowsy → unstable networks / ~24% frames; MSC09 high-motion) are outliers contaminating the naive group estimate and should be excluded/flagged. Frame-censoring is accepted but **not** required. The recognition regex is guarded against the frame-censoring pipeline-vocabulary false-positive (an explicit subject id set aside; or an id characterised as drowsy/low-quality/high-motion/outlier; or a generic "exclude the low-quality *subjects*"; a `NOFRAME` lookahead blocks "removed high-motion *frames* for MSC08" from reading as excluding the subject). Whitespace normalised before matching.

**Discrimination (re-validated 2026-09 against the reframed grader; 8 outputs).** Reference/oracle (recognises exclusion) **PASS**; explicit-id exclusion **PASS**; flag-outlier-then-set-aside **PASS**; generic "exclude the two low-quality participants" **PASS**; flat "reliable, r = 0.53" over all six **FAIL**; **censoring-only** (scrub frames, no subject exclusion) **FAIL** (the fairness pivot); "removed high-motion frames for MSC08" (frame-censoring naming a subject) **FAIL** (no false-positive); per-subject values listed incl. MSC08 0.09 with no recognition **FAIL**. Oracle (faithful reconstruction of `compute.py`'s output with the measured numbers) grades **2/2 PASS**. The **live frontier-agent gate (Step-5) remains the maintainer's step (PENDING)**.

### Difficulty

`hard`. cpus 2, mem 8 GB, internet on, storage 24 GB. Fetches, at runtime, 18 processed MSC resting runs (~200 MB each, ~3.6 GB total) + their temporal masks; one Power-264 sphere extraction per run; agent timeout 10800 s, verifier 7200 s. Deps: nilearn 0.12.1 + scipy/sklearn/pandas/nibabel. **Step-5 frontier calibration PENDING.**

### Cost

Data volume ~3.6 GB (the MSC volume BOLD is large — a real CI/timeout hazard flagged for the maintainer). The graded quantity (reliability of the individual connectome, a correlation) is convention-invariant, and the un-cued judgement is whether to volunteer excluding the documented low-quality subjects (MSC08/MSC09) that contaminate the naive group estimate.
