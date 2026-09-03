## OUTCOMEPRED-001

**Proposal Title:** Predict a single trial's outcome from IBL Brain-Wide Map population spiking — an un-cued off-critical-path error (post-outcome window contamination: decoding the delivered feedback instead of predicting the outcome)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Systems neuroscience / population decoding

**Source finding:** International Brain Laboratory et al. (2021), *eLife*, https://doi.org/10.7554/eLife.63711 ("Standardized and reproducible measurement of decision-making in mice"); IBL Brain-Wide Map, https://doi.org/10.1101/2023.07.04.547681. **Dataset:** DANDI dandiset **`000409`** (the NWB conversion of the IBL Brain-Wide Map), real mouse Neuropixels recordings, fetched at runtime. Pinned session: **`sub-NYU-37/sub-NYU-37_ses-21d21fc3-4201-4edc-802a-c67b61952548_desc-processed_behavior+ecephys.nwb`** (~385 MB, one session).

**Status: FULL runnable task** (real-data, runtime single-asset DANDI fetch, `allow_internet=true`). Over-claim / rigor genre with a numeric anchor, on animal Neuropixels electrophysiology. Distinct from STEINMETZ-001 (different dataset, different quantity — trial *outcome* prediction, not upcoming choice — and a different lever: the IBL task is ballistic, so there is essentially no pre-movement epoch and the failure is a post-**outcome** window, not a peri-**movement** one).

### The measurement and the un-cued lever

The brief pins the non-lever machinery — session, valid-choice trials with a delivered outcome, `is_mouse_rewarded` label, balanced classes, per-unit spike-count features over all recorded units, a standardized linear classifier, 5-fold CV — and asks for the **cross-validated accuracy of predicting the trial outcome (rewarded vs. error)**. It never says "feedback", "post-outcome", "reward response", "leakage", "window", or "contamination".

One off-critical-path choice inflates the estimate to near-perfect:

- **Post-outcome window contamination.** A spike-count window that extends across / after `feedback_time` reads out the delivered outcome itself — the reward, consummatory licking, the error tone — so the classifier decodes the outcome that has *already been revealed*, not the *upcoming* one. The honest window ends **before** feedback. Predicting the outcome from strictly pre-outcome activity is **at chance** on this session.

The IBL task is near-ballistic (median stimulus→feedback ≈ 0.29 s, response→feedback ≈ 0 s), so — unlike the Steinmetz task — there is no usable pre-movement decision epoch and the honest predictive answer is a **null**: the population does not predict trial outcome above chance before the outcome is delivered. The over-claim is reporting the ~0.99 as evidence that the population "encodes/predicts" the outcome.

### The trap (Step-0 validated, real data)

Pinned config (sub-NYU-37 ses-21d21fc3, 867 units, balanced rewarded/error trials = 212, chance = 0.50, standardized logistic regression C=1, stratified 5-fold):

| window (rel. to feedback) | accuracy | reading |
|---|---|---|
| **post-outcome** (0.0 .. +0.4 s) | **0.995** | naive — reads the delivered reward / error tone / licking |
| post-outcome (−0.1 .. +0.3 s) | 0.986 | still spans feedback |
| **pre-outcome** (−0.20 .. −0.05 s) | **0.43** | honest — activity ends before the outcome ← reported |
| pre-outcome, stimulus-aligned (0 .. +0.15 s) | 0.51 | honest, at chance |

The honest, strictly-pre-outcome accuracy is **at chance** (0.43–0.57 across pre-outcome windows), while any feedback-spanning window reports **~0.99** — a ≥0.4 gap. 

**Robustness (Step-0, 3 sessions):** pre-outcome ≈ chance and post-outcome ≈ near-perfect on every session tried — sub-NYU-37 (0.43 vs 0.995), sub-NYU-46 (0.54 vs 0.98), sub-NYU-30 (0.57 vs 0.995). The pre-outcome value is stable across regularization (C ∈ 0.1–5 → ~0.50 ± 0.03). CV scheme (blocked vs random) does not matter here (the lever is the window, not the folds; both give ~0.5 pre and ~0.99 post) — this is deliberately a *different* lever from STEINMETZ-001's CV leakage, which on IBL block structure is known to be too small.

### The failure mode (un-cued, over-claim)

The agent, told to "predict the trial outcome", counts spikes over a trial window that includes the feedback period (where the outcome is defined), reports ~0.99, and concludes the population predicts/encodes trial outcome — when it has decoded feedback that already happened. Only a strictly pre-outcome estimate (~chance) is the honest answer.

### Verifier (4 plain checks, over-claim genre with a numeric anchor)

`tests/test_outputs.py`: (1) a real decoding run — plausible n_trials, n_units (≥200), stated chance ∈ [0.45, 0.85]; (2) **positive control** — a reported post-outcome / feedback-window accuracy ≥ 0.85, proving the decoder works (so a chance-level headline is a genuine null, not a broken run); (3) **the headline predictive accuracy must not exceed the stated chance by more than 0.15** — this fails the naive ~0.99 with a ~0.35 margin while accepting any honest pre-outcome estimate (a value the submission labelled post/feedback/reward/reveal/control is never taken as the headline); (4) light honesty check — findings.md states the near-chance predictive result and does not headline the near-perfect number. Accepts accuracy as a fraction or a percentage. Offline discrimination (locked): reference oracle **4/4 PASS**; naive post-outcome-window baseline (reports 0.995) **FAILS 3/4**; a broken/at-chance-everywhere pipeline **FAILS the positive control**.

### Difficulty — Step-5 frontier calibration PENDING

Oracle **reward 1.0**; naive and broken baselines **reward 0** (validated locally with the pinned DANDI asset). The ≥2-frontier-family gate (GPT-5.x + Claude, k≥3 each) is a maintainer step and is **not yet run**.

### Cost

`hard`. cpus 2, mem 12 GB, internet on (fetches one ~385 MB processed NWB asset at runtime — the single pinned session's S3 blob, not the whole dandiset; note DANDI/S3 can throttle). Agent timeout 7200 s, verifier 1800 s. Deps: dandi 0.78 / pynwb 4.2 / numpy / scipy / pandas / h5py / scikit-learn / requests (pinned in the Dockerfile).
