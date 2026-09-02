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

A careless-but-competent agent computes the raw Skaggs info, gets ~1.1 bits/spike, and reports it as significant place coding — never establishing the shuffle null that shows the value is bias. A flat "these CA1 cells carry ~1.1 bits/spike of spatial information" over-claims; only recognising and correcting the estimator bias (reporting ~0 / not significant) passes.

### Verifier (4 plain checks, over-claim genre)

`tests/test_outputs.py`: (1) per-unit Skaggs information computed for ~36 CA1 units (plausible band); (2) a **shuffle / circular-shift null (or equivalent bias correction) was established** — the correction word must co-occur with a result token, so a bare pipeline mention cannot false-pass; (3) `findings.md` **does not over-claim** — it reports that after correction the population's spatial information is ~0 / not significant (bias), linking the near-zero/bias verdict to the spatial-information claim; (4) numeric teeth — the headline value in `results.json` is the **bias-corrected** one (< 0.5), not the raw ~1.1. Offline discrimination (locked): reference oracle **4/4 PASS**; naive raw-only baseline (reports 1.12 as real coding) **FAILS 3/4** (bias-correction, over-claim, and reported-value checks).

### Difficulty — Step-5 frontier calibration PENDING

Oracle **reward 1.0**; naive raw-Skaggs baseline **reward 0** (validated locally with the pinned DANDI asset). The ≥2-frontier-family gate (GPT-5.x + Claude, k≥3 each) is a maintainer step and is **not yet run**.

### Cost

`hard`. cpus 2, mem 8 GB, internet on (fetches one ~9 MB NWB asset from DANDI at runtime; note the DANDI/S3 archive can throttle). Agent timeout 5400 s, verifier 1800 s. Deps: dandi 0.78 / pynwb 4.1 / numpy / scipy / pandas / h5py / scikit-learn (pinned in the Dockerfile).
