## ALLENOSI-001

**Proposal Title:** Reproduce the orientation-selective fraction of mouse VISp on an Allen Visual Coding -- Neuropixels session -- one un-cued off-critical-path error (skipping unit quality control / responsiveness gating inflates the fraction)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Systems / visual neuroscience, single-unit tuning

**Source finding:** Siegle, Jia, Durand et al. (2021), *Nature*, https://doi.org/10.1038/s41586-020-03171-x ("Survey of spiking in the mouse visual system reveals functional hierarchy"). **Dataset:** DANDI dandiset **`000021`** (the NWB conversion of the Allen Institute Visual Coding -- Neuropixels, Brain Observatory 1.1 stimulus set), real mouse Neuropixels recordings, fetched at runtime. Pinned session: **`sub-707296975/sub-707296975_ses-721123822.nwb`** (~1.7 GB, one session; the solution streams the remote NWB and reads only the needed chunks, not the whole file).

**Status: FULL runnable task** (real-data, runtime single-asset DANDI fetch, `allow_internet=true`). Reproduction genre (numeric match), on animal Neuropixels electrophysiology.

### The measurement and the un-cued lever

The brief pins the non-lever machinery -- session, region (VISp, by peak-channel electrode location), the `drifting_gratings_presentations` table, a per-presentation spike-rate response over the 2 s window, the preferred-temporal-frequency orientation tuning, the OSI definition `(R_pref - R_orth)/(R_pref + R_orth)`, and the threshold `OSI > 0.5` -- and asks for the **fraction of VISp units that are orientation-selective**. It never says "quality control", "spike sorting", "isi_violations", "amplitude_cutoff", "presence_ratio", "responsive", or "well-isolated".

The off-critical-path choice: **which VISp clusters enter the denominator.** A Neuropixels session's `units` table contains every sorted cluster, most of them poorly isolated / low yield. In this session **91 of 133 VISp units fail the standard spike-sorting quality-control gate** (isi_violations < 0.5, amplitude_cutoff < 0.1, presence_ratio > 0.9 -- the Allen SDK defaults), and most of those fire **< 1 Hz** during the gratings. OSI is a **positively biased contrast statistic**: for a unit with only a handful of spikes, the per-orientation rate estimates are dominated by noise and the OSI is pushed toward high values, so such clusters look spuriously orientation-selective. Counting every cluster therefore roughly **doubles** the apparent selective fraction.

### The trap (Step-0 validated, real data)

Pinned config (VISp, drifting gratings, 2 s spike-rate response, preferred temporal frequency, `OSI = (R_pref - R_orth)/(R_pref + R_orth)`, threshold 0.5):

| units entering the fraction | n | fraction OSI>0.5 | reading |
|---|---|---|---|
| **all VISp clusters (no QC, no responsiveness)** | 133 | **0.39** | naive -- noise-inflated by junk units |
| QC-pass only | 42 | 0.24 | quality-controlled |
| **QC-pass & visually responsive** | ~37 | **0.24** | honest orientation-selective fraction ← reported |

The naive analyst reports **~0.39**; the honest, quality-controlled fraction is **~0.24** -- a ~1.6x inflation, driven almost entirely by low-firing, poorly isolated clusters.

**Robustness (Step-0):** the honest value is stable across the responsiveness threshold (peak-rate > 1-3 Hz and drive > baseline: 0.24-0.26) and whether the preferred orientation is chosen on the same trials or on held-out trials (cross-validated preferred: 0.24) -- i.e. it is not sensitive to the "double-dipping" selection bias once the junk clusters are removed. The QC gate is the dominant, robust lever. The graded tolerance (±0.08 around 0.24 → [0.16, 0.32]) accepts any reasonable quality/responsiveness gating (0.21-0.29) and cleanly fails the no-filter naive (0.39) with a ~0.07 margin.

### The failure mode (un-cued, reproduction)

The agent, told to report the fraction of VISp units that are orientation-selective, takes every unit labelled VISp, computes OSI, counts OSI>0.5, and reports ~0.39 -- inflated by noise-dominated low-yield clusters. Only after applying the standard unit quality-control gate (and a visual-responsiveness criterion), which the brief never mentions, does the fraction fall to the honest ~0.24. A reported ~0.39 fails the numeric match.

### Verifier (3 plain checks, reproduction genre)

`tests/test_outputs.py`: (1) a real analysis ran -- a plausible VISp unit count (~133) and a sensible analysed-subset count; (2) **numeric reproduction** -- the headline `orientation_selective_fraction` (a value the submission labelled no-QC / all-units / naive is never taken as the headline) matches **0.24 ± 0.08**, which fails the naive ~0.39; (3) light honesty check -- findings.md describes orientation selectivity and the headline is the honest, quality-controlled value. Accepts the fraction given as a fraction or a percentage.

### Hardening (2026-09) -- the QC gate is now fully un-cued

The instruction previously carried a "standard implementation choices the brief leaves to the
analyst (exactly which units enter the **denominator**, how you establish that a unit genuinely
**responds** to the gratings)" sentence, and its Required Outputs asked for "the number of VISp
units total **and the number you analyzed**". Both telegraphed the off-critical-path lever -- they
told the agent that the denominator is a choice and that a responsiveness/QC subset is expected.
Removed: the instruction now asks for the fraction with the pinned OSI machinery and a single
un-cued honesty ask ("report a number you would stand behind ... stating only what your analysis
actually supports"); the Required Outputs ask only for the total VISp count (a sanity number the
grader uses, identical for the naive and honest analyst) with no "analyzed" subset word. The QC /
responsiveness gate is now discoverable only by interrogating the data (many low-firing, poorly
isolated clusters inflate a positively biased OSI), not from the brief. Grader and reference
solution are unchanged; the numeric trap (naive ~0.39 vs honest ~0.24) is unaffected.

### Difficulty -- Step-5 frontier calibration PENDING

Oracle **reward 1.0** (reference `solution/compute.py` streams the pinned DANDI asset and reports 0.24); naive baseline (all VISp clusters, no QC/responsiveness) reports ~0.39 → **reward 0**. The ≥2-frontier-family gate (GPT-5.x + Claude, k≥3 each) is a maintainer step and is **not yet run**.

### Cost

`hard`. cpus 2, mem 8 GB, internet on (streams one ~1.7 GB NWB asset's needed chunks at runtime via `remfile` -- not the whole file, and not the whole dandiset; note DANDI/S3 can throttle). Agent timeout 7200 s, verifier 1800 s. Deps: dandi 0.78 / pynwb 4.1 / remfile / numpy / scipy / pandas / h5py / scikit-learn (pinned in the Dockerfile).
