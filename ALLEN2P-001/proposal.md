## ALLEN2P-001

**Proposal Title:** Reproduce the orientation-/direction-selective fraction of a mouse VISp two-photon field on an Allen Brain Observatory experiment -- one un-cued off-critical-path error (choosing each neuron's preferred grating condition and measuring OSI/DSI on the same trials inflates the fraction)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Systems / visual neuroscience, two-photon calcium imaging, single-cell tuning

**Source finding:** de Vries, Lecoq, Buice et al. (2020), *Nature Neuroscience*, https://doi.org/10.1038/s41593-019-0550-9 ("A large-scale standardized physiological survey reveals functional organization of the mouse visual cortex"). **Dataset:** the Allen Brain Observatory Visual Coding -- 2P survey, fetched at runtime through the AllenSDK `BrainObservatoryCache` from the public Allen Institute API (no credentials). Pinned experiment: **`ophys_experiment_id = 501271265`** (VISp, `three_session_A`, Cux2-CreERT2, 215 imaged neurons; the session NWB is ~0.5 GB, downloaded once and cached).

**Status: FULL runnable task** (real-data, runtime AllenSDK fetch, `allow_internet=true`). Reproduction genre (numeric match), on animal two-photon calcium imaging.

### The measurement and the un-cued lever

The brief pins the non-lever machinery -- the experiment, the `drifting_gratings` stimulus table, a per-presentation response taken as the **mean dF/F over the presentation window**, the preferred (direction, temporal-frequency) condition, the two-point OSI `(R_pref - R_orth)/(R_pref + R_orth)` and DSI `(R_pref - R_null)/(R_pref + R_null)`, and the threshold `> 0.5` -- and asks for the **fraction of imaged neurons that are orientation- or direction-selective** (denominator = all imaged neurons). It never says "held out", "cross-validate", "double dipping", "circular", "selection bias", "winner's curse", or "responsive".

The off-critical-path choice: **the preferred (direction, temporal-frequency) condition is chosen as the argmax over the 8 x n_tf conditions.** If it is chosen on the very trials that are then used to measure `R_pref`, `R_orth` and `R_null`, the selection is a winner's curse -- `R_pref` is biased upward by having been picked as the maximum of noisy per-condition estimates, so the ratio contrast statistics OSI/DSI are biased high and even neurons that are not genuinely tuned clear the 0.5 threshold. This is textbook circular analysis (double dipping; Kriegeskorte et al. 2009; the temporal-frequency / preferred-condition dependence of Allen selectivity indices is documented by Mesa et al. 2021, *eNeuro*). Choosing the preferred condition on one set of trials and measuring OSI/DSI on a disjoint held-out set removes the bias and roughly reproduces the honest fraction.

### The trap (Step-0 validated, real data)

Pinned config (VISp, drifting gratings, mean-dF/F-over-window response, preferred (direction, temporal frequency), `OSI = (R_pref - R_orth)/(R_pref + R_orth)`, `DSI = (R_pref - R_null)/(R_pref + R_null)`, selective if OSI>0.5 or DSI>0.5, denominator = all 215 imaged neurons):

| how the preferred condition is selected | fraction selective | reading |
|---|---|---|
| **same trials used to measure OSI/DSI (select-and-test)** | **~0.78** | naive -- winner's-curse inflated |
| held-out trials (chosen on one half, measured on the disjoint half) | **~0.54** | honest, bias-free ← reported |

The naive analyst reports **~0.78**; the honest, held-out fraction is **~0.54** (oracle: 0.537 ± 0.023 over 50 random halves) -- a ~1.4x inflation driven purely by the selection bias. As an independent check, computing OSI/DSI with the AllenSDK `DriftingGratings` analysis on this session (its own %-change-of-corrected-fluorescence response) reproduces the same same-trials number (0.842 with that response; 0.777 with the pinned mean-dF/F response) -- confirming the naive value is exactly what the standard same-trials pipeline yields.

**Robustness (Step-0):** the held-out value is stable across the split scheme -- 50/50 random halves 0.51-0.61, odd/even 0.56, 80/20 0.54 -- standard deviation ~0.02-0.03; and across the response definition the two camps stay cleanly separated (held-out 0.54-0.63 vs same-trials 0.75-0.84 for mean-dF/F, baseline-subtracted dF/F, and AllenSDK %-change responses). The graded tolerance (0.54 ± 0.12 → [0.42, 0.66]) accepts any reasonable held-out estimate and cleanly fails the same-trials naive (0.78, ~0.12 margin). A permutation-significance answer (~0.32, which measures a different quantity -- "fraction significantly selective" rather than "fraction with OSI/DSI above the pinned threshold") also falls outside the band, as intended.

### The failure mode (un-cued, reproduction)

The agent, told to report the fraction of imaged neurons that are orientation- or direction-selective, computes each neuron's mean response per condition, takes the argmax as the preferred condition, computes OSI/DSI at that condition on all trials, counts OSI>0.5 or DSI>0.5, and reports ~0.78 -- inflated because the preferred condition was chosen and evaluated on the same noisy data. Only after breaking the circularity (choosing the preferred condition on held-out trials), which the brief never mentions, does the fraction fall to the honest ~0.54. A reported ~0.78 fails the numeric match.

### Verifier (3 plain checks, reproduction genre)

`tests/test_outputs.py`: (1) a real analysis ran -- a plausible imaged-neuron count (100-800; here 215); (2) **numeric reproduction** -- the headline `selective_fraction` (a value the submission labelled same-trials / no-holdout / spread is never taken as the headline) matches **0.54 ± 0.12**, which fails the naive ~0.78; (3) light honesty check -- findings.md describes orientation/direction selectivity and the headline is the honest, held-out value. Accepts the fraction given as a fraction or a percentage.

### Difficulty -- Step-5 frontier calibration PENDING

Oracle **reward 1.0** (reference `solution/compute.py` fetches the pinned experiment through `BrainObservatoryCache` and reports 0.54); naive baseline (same-trials select-and-test) reports ~0.78 → **reward 0**. The >=2-frontier-family gate (GPT-5.x + Claude, k>=3 each) is a maintainer step and is **not yet run**.

### Cost

`hard`. cpus 2, mem 8 GB, internet on (downloads one ~0.5 GB Allen Brain Observatory session NWB at runtime via `BrainObservatoryCache`; the Allen API intermittently returns 502s, so both the fetch and the solution retry with backoff). Agent timeout 7200 s, verifier 1800 s. Deps: allensdk 2.16.2 on Python 3.10 (with `setuptools<81` and `statsmodels==0.13.5` pins that keep AllenSDK importable), numpy / pandas / scipy / h5py / pynwb / hdmf / tables (pinned in the Dockerfile).

### Distinctness from ALLENOSI-001

ALLENOSI-001 reproduces an orientation-selective fraction from Allen **Neuropixels** electrophysiology (DANDI streaming, spikes), with the lever being **spike-sorting quality control + responsiveness** gating. ALLEN2P-001 is a different modality (**two-photon calcium imaging**, dF/F), a different data path (**AllenSDK `BrainObservatoryCache`**, not DANDI), a different quantity (**OSI or DSI**, not OSI alone), and a different, orthogonal lever (**held-out preferred-condition selection to remove the double-dipping selection bias** -- there is no spike-sorting QC in calcium imaging). The two do not share code, data, or failure mode.
