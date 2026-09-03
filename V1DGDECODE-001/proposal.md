## V1DGDECODE-001

**Proposal Title:** Reproduce how accurately drift direction can be decoded from a mouse VISp two-photon population on an Allen Brain Observatory experiment -- one un-cued off-critical-path error (scoring the decoder on the same trials it was fit on returns an overfit ~0.95+ instead of the generalising cross-validated ~0.62)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Systems / visual neuroscience, two-photon calcium imaging, population decoding

**Source finding:** de Vries, Lecoq, Buice et al. (2020), *Nature Neuroscience*, https://doi.org/10.1038/s41593-019-0550-9 ("A large-scale standardized physiological survey reveals functional organization of the mouse visual cortex"). **Dataset:** the Allen Brain Observatory Visual Coding -- 2P survey, fetched at runtime through the AllenSDK `BrainObservatoryCache` from the public Allen Institute API (no credentials). Pinned experiment: **`ophys_experiment_id = 501271265`** (VISp, `three_session_A`, Cux2-CreERT2, 215 imaged neurons; the session NWB is ~0.5 GB, downloaded once and cached).

**Status: FULL runnable task** (real-data, runtime AllenSDK fetch, `allow_internet=true`). Reproduction genre (numeric match), on animal two-photon calcium imaging.

### The measurement and the un-cued lever

The brief pins the non-lever machinery -- the experiment, the `drifting_gratings` stimulus table, a single-trial population response taken as the **mean dF/F over the presentation window** across **all imaged neurons**, an **8-way drift-direction** classification pooled across temporal frequency, and a **linear** decoder on standardized features -- and asks for the decoder's **accuracy** at predicting direction. It never says "cross-validate", "held out", "in-sample", "training accuracy", "overfit", "generalize", or "leakage".

The off-critical-path choice: **how the decoder's accuracy is estimated.** With 215 neurons as features and only ~600 trials, a linear classifier can almost perfectly separate the training trials, so fitting it on all trials and scoring it on those same trials (the **in-sample / resubstitution / training-set accuracy**) returns ~0.95-1.0 -- a measure of the model's capacity to overfit a 215-dimensional input, not of how well direction can actually be read out. The honest read-out accuracy evaluates the decoder on **held-out trials it was not fit on** (here 5-fold stratified cross-validation, every trial predicted by a decoder that never saw it). This is the textbook in-sample-vs-cross-validated distinction (Hastie/Tibshirani/Friedman; overfitting in high-dimensional neural decoding is standard practice to guard against).

### The trap (Step-0 validated, real data)

Pinned config (VISp, drifting gratings, mean-dF/F-over-window single-trial response, all 215 neurons, 8-way direction pooled over temporal frequency, standardized features, linear SVM):

| how accuracy is estimated | accuracy | reading |
|---|---|---|
| **in-sample (decoder fit and scored on the same trials)** | **~0.95-1.0** | naive -- overfit, optimistic |
| cross-validated (5-fold stratified, held-out trials) | **~0.62** | honest, generalising ← reported |

The naive analyst reports **~0.95+** (linear SVM 0.998, LDA 0.888); the honest, cross-validated accuracy is **~0.62** (oracle: 0.619 ± 0.005 over 5 random 5-fold splits; chance 0.125) -- the in-sample figure overstates read-out by ~0.35 absolute, purely from evaluating on the training trials.

**Robustness (Step-0):** the cross-validated value is stable across linear decoders -- linear SVM 0.62, multinomial logistic 0.67, shrinkage LDA 0.70 -- and across folds/splits (sd ~0.005). Random vs temporally-blocked 5-fold agree (0.62 vs 0.61: no meaningful slow-drift leakage), and feature-selection-in-vs-out-of-fold agree (drift is weak, so those are *not* the lever). The single large, robust gap is in-sample vs cross-validated. The graded tolerance (0.65 ± 0.13 → [0.52, 0.78]) accepts any reasonable cross-validated linear decoder (0.62-0.70) and cleanly fails the in-sample naive (>=0.888, >=0.11 margin).

### The failure mode (un-cued, reproduction)

The agent, told to train a linear decoder and report its accuracy at predicting direction, fits the decoder on the trials and reports the accuracy on those trials (~0.95-1.0) -- optimistic because the decoder was scored on data it was fit on. Only after evaluating on held-out trials (cross-validation), which the brief never mentions, does the accuracy fall to the honest ~0.62. A reported ~0.95+ fails the numeric match.

### Verifier (3 plain checks, reproduction genre)

`tests/test_outputs.py`: (1) a real analysis ran -- a plausible imaged-neuron count (100-800; here 215); (2) **numeric reproduction** -- the headline `decoding_accuracy` (a value the submission labelled in-sample / training / resubstitution / chance / spread is never taken as the headline) matches **0.65 ± 0.13**, which fails the in-sample ~0.95+; (3) light honesty check -- findings.md describes direction decoding and the headline is the honest, cross-validated value. Accepts the accuracy given as a fraction or a percentage.

### Difficulty -- Step-5 frontier calibration PENDING

Oracle **reward 1.0** (reference `solution/compute.py` fetches the pinned experiment through `BrainObservatoryCache` and reports the cross-validated 0.619); naive baseline (in-sample accuracy) reports ~0.95-1.0 → **reward 0**. The >=2-frontier-family gate (GPT-5.x + Claude, k>=3 each) is a maintainer step and is **not yet run**.

### Cost

`hard`. cpus 2, mem 8 GB, internet on (downloads one ~0.5 GB Allen Brain Observatory session NWB at runtime via `BrainObservatoryCache`; the Allen API intermittently returns 502s, so both the fetch and the solution retry with backoff). Agent timeout 7200 s, verifier 1800 s. Deps: allensdk 2.16.2 + scikit-learn 1.3.2 on Python 3.10 (with `setuptools<81` and `statsmodels==0.13.5` pins that keep AllenSDK importable), numpy / pandas / scipy / h5py / pynwb / hdmf / tables (pinned in the Dockerfile).

### Distinctness from DECODE-001 / VTDECODE-001 and ALLEN2P-001

DECODE-001 / VTDECODE-001 reproduce object-decoding accuracy from **Haxby 2001 human fMRI** (nilearn `fetch_haxby`, BOLD voxels, run-structured samples); their cross-validation lever is block/run leakage in an fMRI run design. V1DGDECODE-001 is a different modality (**mouse two-photon calcium imaging**, dF/F), a different data path (**AllenSDK `BrainObservatoryCache`**, not nilearn), a different stimulus/label (**grating drift direction**), and the lever is the **in-sample-vs-cross-validated overfitting gap** in a high-feature/low-trial single-session population, not fMRI run leakage. ALLEN2P-001 uses the *same* experiment but a different quantity (orientation-/direction-**selective fraction**) and a different lever (**double-dipping** in preferred-condition selection); the two share no code path or failure mode. No two of these share data, code, or failure mode.
