## TIMEDECODE-001

**Proposal Title:** Single-trial MEG decoding of stimulus modality on the MNE sample dataset — an un-cued cross-validation-non-independence trap (pooling time samples with a random k-fold inflates the accuracy)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** MEG/EEG single-trial decoding / machine-learning evaluation

**Source finding / benchmark:** Single-trial sensor-level decoding of stimulus modality (auditory vs visual) from the MNE **sample** MEG dataset (`sample_audvis_filt-0-40`), reported as cross-validated decoding accuracy. **Dataset:** `mne.datasets.sample` (fetched at runtime, no credentials). Genre: **reproduction**.

### The un-cued lever (PRIVATE — reviewers only)

The deliverable ("report the **cross-validated** decoding accuracy") names the metric but never says **how the cross-validation folds must be formed**. The pipeline pools **each post-stimulus time sample of every trial** as a separate example, so every trial contributes many highly autocorrelated samples that all share one modality label. An ordinary random k-fold over the pooled (trial × time) samples puts samples from the **same trial** in both the training and the test fold → the classifier is scored on near-duplicates of trials it has already seen → the accuracy is **inflated**. The honest estimate keeps every trial wholly on one side of the split (**StratifiedGroupKFold / GroupKFold by trial**). Everything else is pinned — gradiometers, -0.2..0.5 s epochs, baseline (None, 0), grad reject 4000e-13, decim 2, the 0.05-0.45 s analysis window, StandardScaler + LogisticRegression, 5 folds — so only the fold grouping moves the number.

This is a different failure family from the shipped MOTORIMAGERY-001 (supervised CSP filter fit on all epochs) and from EEGLEAK/EEGVC: here the leak is **temporal non-independence of pooled samples**, the single most common mistake in "decode every time point" EEG/MEG pipelines.

### Step-0 (validated, real data — mne 1.12.1, sklearn 1.8.0)

Pinned pipeline (auditory {1,2} vs visual {3,4}; 288 trials; 8640 pooled samples):

| CV fold formation | accuracy |
|---|---|
| **grouped by trial (leakage-free) — correct** | **0.666** (StratifiedGroupKFold) / 0.689 (GroupKFold) |
| random k-fold over pooled samples — naive/leaky | **0.791** |

Gap (random − grouped) = **0.126** accuracy, correctly signed (pooling+random inflated). Robustness of the trial-grouped value across un-pinned choices (StratifiedGroupKFold vs GroupKFold, fold count 4/5/10, logistic vs LDA, small analysis-window shifts): **0.66–0.70**; every random-k-fold scheme is **≥ 0.77**. Chance = 0.5.

The verifier accepts `|reported − 0.67| < 0.055` (accept [0.615, 0.725]), sized to pass any genuine trial-grouped estimate and to fail the inflated random-k-fold value (~0.79).

### Verifier (2 plain checks)

`tests/test_outputs.py`: (1) a two-class decoding computed with a per-fold CV breakdown and a valid above-chance accuracy; (2) the reported headline accuracy is the leakage-free (trial-grouped) value (`|reported − 0.67| < 0.055`) — the inflated random-k-fold value (~0.79) fails. Numeric grader per the repo's numeric-grader discipline (grades the declared `accuracy` field, ignoring an explicitly-labelled random-k-fold/reference field).

### Validation (MEASURED locally)

- **Oracle** (`solution/compute.py`): trial-grouped accuracy = **0.666**; verifier **PASS (2/2)**.
- **Naive** random-k-fold fixture: accuracy = **0.791**; verifier **FAIL** (`test_accuracy_is_leakage_free`). Task has teeth.
- Data fetches at runtime via `mne.datasets.sample.data_path()` (no credentials); `allow_internet=true`.
- **Step-5 frontier calibration PENDING** (maintainer step).

### Cost

`hard`. cpus 2, mem 8 GB, internet on (downloads the MNE sample dataset, ~1.5 GB, once). Deps: mne 1.12.1 + numpy/scipy/scikit-learn/pooch.
