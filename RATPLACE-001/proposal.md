## RATPLACE-001

**Proposal Title:** Report the CA1 place-cell spatial information on a familiar track — an un-cued Skaggs estimator-bias trap (the *over-claim* failure axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Hippocampal spatial coding / electrophysiology

**Source finding / method:** Skaggs, McNaughton, Gothard & Markus (1993/1996), the Skaggs spatial-information rate (bits/spike) and its shuffle-based significance test — standard practice in every place-cell paper. **Dataset:** DANDI dandiset **`001754`** (McNaughton lab, "Three-dimensional spatial selectivity of hippocampal neurons during space flight"), real rat CA1 tetrode recordings in NWB, fetched at runtime. Pinned unit: **`sub-Rat1/sub-Rat1_ses-19980425T124500_behavior+ecephys.nwb`** (~9 MB).

**Status: FULL runnable task** (real-data, runtime DANDI fetch, `allow_internet=true`). Over-claim genre, mirroring GRADIENT-001, on animal electrophysiology rather than fMRI.

### The measurement and the un-cued lever

The brief pins everything about the measurement — session, Baseline rectangular-track (BL) epochs, running-only, a 4×5 = 20-bin occupancy grid, putative pyramidal CA1 units — and asks for the **mean Skaggs spatial information (bits/spike)**. It never mentions bias, shuffling, correction, or significance.

**The lever is the Skaggs estimator's finite-sample / occupancy upward bias.** With a limited number of spikes over a binned arena, even a spatially *random* cell produces a positive apparent information, because under-sampled bins make the rate map look tuned by chance. The standard, un-cued-but-obligatory step is to build a per-cell null by **circularly shifting** each spike train against position (breaking the spike↔place relationship while preserving each signal's own autostructure), recompute the information many times, and report the **bias-corrected** value and whether raw beats the null.

### The trap (Step-0 validated, real data)

Pinned pipeline (both BL epochs, running > 5 px/s, 4×5 = 20-bin grid, CA1 units with ≥50 running spikes and mean rate 0.05–5 Hz, 300 circular shifts ≥20 s, seed 20250901):

| quantity | value | reading |
|---|---|---|
| n CA1 units | 36 | putative pyramidal |
| **raw** mean Skaggs info | **1.12 bits/spike** | looks like textbook place coding |
| **shuffle-null** mean | **1.03 bits/spike** | == the estimator's bias |
| **bias-corrected** mean | **0.09 bits/spike** | ≈ 0 |
| significant units (raw > own shuffle 95th pct) | **0 / 36** | none survive |
| **positive control** (synthetic place cell, SAME pipeline) | raw **1.21** vs null **0.05**, significant | pipeline is sound |

So the raw ~1.1 bits/spike — a perfectly plausible place-cell value — is **almost entirely sampling/occupancy bias**: after shuffle correction the CA1 population carries no significant spatial information at this binning, and 0/36 cells beat their own null. The synthetic place-cell positive control run through the identical pipeline is recovered cleanly (raw ≫ null, significant), so the null result is a property of the data, not a broken estimator.

**Robustness (Step-0):** the "0/36 significant, corrected ≪ raw" result is stable across the reasonable binning range (16–36 bins: 4×4, 4×5, 5×4, 5×5, 5×6, 6×6 all give 0/36 significant) and across running-speed cutoffs (2.5–10 px/s give the same raw/null/corrected). Only very fine grids (≥100 bins) recover a handful of cells, and 1-D angular linearisation of the perimeter recovers some directional tuning — but the pinned 20-bin measurement, corrected, is what is graded, and the *lesson* (the raw value is dominated by estimator bias) is binning-independent.

### The failure mode (un-cued, over-claim)

A careless-but-competent agent computes the raw Skaggs info, gets ~1.1 bits/spike, and reports it as significant place coding — never establishing the shuffle null that shows the value is dominated by estimator bias. A flat "these CA1 cells carry ~1.1 bits/spike of spatial information" over-claims; the honest analysis recognises the estimator bias (raw over-estimates; the bias-corrected value is far below raw). **The graded conclusion is that ESTIMATOR-BIAS lesson — NOT a biological claim that CA1 lacks place coding (see the R2 rework below).**

### R2 conclusion rework (supersedes the earlier "no place coding" framing)

The earlier cut graded the conclusion as a biological null — "after shuffle correction these CA1 units carry **no significant spatial information** … 0/36 cells". That over-reached and was contradicted by this proposal's own robustness note: a finer grid (≥100 bins) or a 1-D angular linearisation of the track perimeter **recovers** spatially tuned cells, exactly as expected for a place-coding region. A corrected value that is ~0 **at a coarse 20-bin grid** is a statement about the Skaggs *estimator* and this binning's detection power, not about the biology.

The conclusion is recut to the **Skaggs estimator-bias lesson**, which is fully defensible on both roots: the raw ~1.1 bits/spike **over-estimates** (it is dominated by the finite-sample / occupancy bias, ≈ the shuffle null ~1.03), a shuffle/analytic bias correction is **required**, and the corrected value (~0.09 at this binning) is **much lower than raw**. The oracle `findings.md` now states this and **explicitly scopes it** ("this does not mean CA1 lacks place coding; a finer grid / linearisation recovers tuned cells"). The graded discriminating number is **raw vs corrected**, not a significance count. The instruction is unchanged and stays **un-cued** (it never mentions shuffling, bias, correction or significance).

### Verifier — proof-of-work hardening (fabrication-proof, lever un-cued)

The reviewed verifier graded a single reported number + prose and (per the suite audit) could be passed on fabricated data. It is now fabrication-proof, and the conclusion is the recut estimator-bias lesson:

- **Held-out reference** `tests/reference.npz` (built from the oracle run on the pinned DANDI 001754 asset; never shipped to the agent): per-unit real RAW Skaggs keyed by `unit_index`, plus `ref_stats` (n=36, raw_mean 1.119, null_mean 1.026, corrected_mean 0.093).
- **Neutral per-unit table** `spatial_information.csv` (already a Required Output) — the pinned per-unit RAW Skaggs, an intermediate BOTH a raw-only and a bias-corrected analysis produce, so it does not cue the shuffle-correction lever.
- **Four grader pillars.** (1) well-formedness (~36 units, plausible band); (2) the submitted per-unit raw Skaggs must track the reference (cross-unit r ≥ 0.95, per-unit tol, coverage ≥ 90%, non-constant) and the raw population mean recomputed from the rows must match the reference (1.12) and the reported JSON — impossible without the real occupancy + spikes; (3) the estimator-bias JUDGEMENT as an un-cued **OR-escape** — PASS if the write-up volunteers the bias (a reported bias-corrected value far below raw, OR prose that ties the over-estimation / finite-sample bias / shuffle correction to the spatial-information result), FAIL on a bare raw ~1.1 reported as real coding; (4) an **over-claim guard** that fails a definitive **biological-absence** claim ("CA1 carries no place coding / not place cells") made without an estimator/binning scoping caveat — enforcing that the graded lesson is the estimator bias, not a biological null.

**Subprocess-pytest validation matrix** (each `OUTPUT_DIR` graded by a fresh `pytest` process): oracle/honest **PASS 5/5** (raw table + corrected value + scoped estimator-bias prose) / no-table **FAIL** / constant-table **FAIL** (pillar 2 teeth) / non-constant-fabricated (real raw values permuted across units) **FAIL** (pillar 2 teeth) / naive raw-only ("1.12 = strong place coding") **FAIL** (pillar 3) / biological-absence over-claim ("CA1 has no place coding", unscoped) **FAIL** (over-claim guard) / defensible-alternative (analytic Panzeri-Treves debias 0.05 + scoped prose) **PASS**.

### Packaging

`tests/reference.npz` (small) is committed; the one ~9 MB NWB asset is fetched at runtime, so `allow_internet` stays `true` and the asset + `ref_stats` are pinned (baking the ~9 MB derived input is a straightforward maintainer follow-up).

### Hardening pass (tb-science bar)

Two changes, both to remove residual cueing / a false-pass, neither touching the numeric
ground truth (the data pipeline is unchanged: raw 1.12 / shuffle-null 1.03 / corrected 0.09
/ 0-of-36 significant remain Step-0-locked):

1. **De-cue the instruction.** Dropped the "how strong / **reliable** the spatial coding is"
   phrasing in the `findings.md` required-output line (the word "reliable" mildly nudged
   toward a reliability/significance analysis, i.e. toward the shuffle correction). The
   deliverable now reads "how strong the spatial coding is" — the natural magnitude question
   a naive agent answers with the raw ~1.1 over-claim — so the bias-correction lever is fully
   un-cued.
2. **Close a pipeline-vocabulary false-pass in the over-claim honesty check.** The BIAS
   trigger set in `test_does_not_overclaim_spatial_coding` had contained pure pipeline-method
   words (`shuffle | circular | null`). A hedged write-up that merely *named* its shuffle step
   next to "spatial information" while still over-claiming "strong significant place coding"
   could satisfy the co-occurrence and false-pass check 3 (the exact pipeline-vocab
   false-positive class the tb-science playbook documents). Those method words were removed;
   the honesty check now fires only on genuine **conclusion** tokens (not-significant /
   near-zero / at chance / inflated / standalone "bias" — excluding the methods phrase
   "bias correction"/"bias-corrected"). The numeric teeth (check 4: the reported headline
   value must be the corrected < 0.5, not the raw ~1.1) already backstopped every over-claim;
   this makes the prose check bite the hedge too.

**Re-validation (offline, four faithful outputs mirroring the reference `compute.py`):**
oracle-pass (4/4) / naive-raw-only-fail (fails checks 2,3,4) / over-claim-hedge-fail (now
fails checks 3 **and** 4) / defensible-alternative-pass (an analytic Panzeri-Treves-style
debiased estimator reporting corrected ≈0, not significant, passes 4/4) = **Y/Y/Y/Y**.

### Difficulty — Step-5 frontier calibration PENDING

Oracle **reward 1.0**; naive raw-Skaggs baseline **reward 0** (validated locally with the pinned DANDI asset). The ≥2-frontier-family gate (GPT-5.x + Claude, k≥3 each) — does a frontier agent volunteer the shuffle/bias correction un-cued and report the corrected ~0, or fit once and over-claim the raw ~1.1? — is the maintainer's Step-5 gate and **cannot be run here**.

### Cost

`hard`. cpus 2, mem 8 GB, internet on (fetches one ~9 MB NWB asset from DANDI at runtime; note the DANDI/S3 archive can throttle). Agent timeout 5400 s, verifier 1800 s. Deps: dandi 0.78 / pynwb 4.1 / numpy / scipy / pandas / h5py / scikit-learn (pinned in the Dockerfile).
