## TIMEDECODE-001

**Proposal Title:** Single-trial MEG decoding of stimulus modality on the MNE sample dataset — an un-cued cross-validation-non-independence trap (pooling time samples with a random k-fold inflates the accuracy)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** MEG/EEG single-trial decoding / machine-learning evaluation

**Source finding / benchmark:** Single-trial sensor-level decoding of stimulus modality (auditory vs visual) from the MNE **sample** MEG dataset (`sample_audvis_filt-0-40`), reported as cross-validated decoding accuracy. **Dataset:** `mne.datasets.sample` (fetched at runtime, no credentials). Genre: **reproduction**.

> **HARDENING NOTE (de-cue, this revision).** The first cut's CV bullet read "Evaluate with **5-fold cross-validation**", which an agent can read as *endorsing* a plain `StratifiedKFold(5)` — i.e. the instruction telling it to do the leaky thing, which would make the fail unfair. Reworded so only the **fold count (5)** is pinned (for reproducibility) and the **fold-construction scheme is explicitly left to the analyst's judgement** ("should follow sound cross-validation practice"). A plain random k-fold is now a *choice the agent makes*, not one the brief dictates — the fail is a genuine un-cued judgement miss. Kept off-path: the brief still never mentions trials, grouping, independence, or leakage.

### The un-cued lever (PRIVATE — reviewers only)

The deliverable ("report the **cross-validated** decoding accuracy") names the metric but never says **how the cross-validation folds must be formed** (and now explicitly leaves the scheme to the analyst). The pipeline pools **each post-stimulus time sample of every trial** as a separate example, so every trial contributes many highly autocorrelated samples that all share one modality label. An ordinary random k-fold over the pooled (trial × time) samples puts samples from the **same trial** in both the training and the test fold → the classifier is scored on near-duplicates of trials it has already seen → the accuracy is **inflated**. The honest estimate keeps every trial wholly on one side of the split (**StratifiedGroupKFold / GroupKFold by trial**). Everything else is pinned — gradiometers, -0.2..0.5 s epochs, baseline (None, 0), grad reject 4000e-13, decim 2, the 0.05-0.45 s analysis window, StandardScaler + LogisticRegression, 5 folds — so only the fold grouping moves the number.

This is a different failure family from the shipped MOTORIMAGERY-001 (supervised CSP filter fit on all epochs) and from EEGLEAK/EEGVC: here the leak is **temporal non-independence of pooled samples**, the single most common mistake in "decode every time point" EEG/MEG pipelines.

### Step-0 (validated, real data — mne 1.12.1, sklearn 1.8.0)

Pinned pipeline (auditory {1,2} vs visual {3,4}; 288 trials; 8640 pooled samples):

| CV fold formation | accuracy |
|---|---|
| **grouped by trial (leakage-free) — correct** | **0.666** (StratifiedGroupKFold) / 0.689 (GroupKFold) |
| random k-fold over pooled samples — naive/leaky | **0.791** |

Gap (random − grouped) = **0.126** accuracy, correctly signed (pooling+random inflated). Chance = 0.5.

**Band re-validated on the real data across every defensible choice (this revision):** trial-grouped — StratifiedGroupKFold(5)=0.666, (10)=0.683; GroupKFold(5)=0.689, (10)=0.689; LeaveOneGroupOut=0.688; StratifiedGroupKFold(5)+LDA=0.667 → **0.665–0.689**. Pooled random k-fold — StratifiedKFold(5)=0.791, (10)=0.792; KFold(5)=0.789, (10)=0.790; StratifiedKFold(5)+LDA=0.794 → **≥0.789**. The verifier accepts `|reported − 0.67| < 0.055` (accept **[0.615, 0.725]**): it passes every trial-grouped estimate (≥0.036 margin to the upper edge) and fails every random-k-fold value (≥0.064 above it). Clean, fair separation.

### Verifier (2 plain checks)

`tests/test_outputs.py`: (1) a two-class decoding computed with a per-fold CV breakdown and a valid above-chance accuracy; (2) the reported headline accuracy is the leakage-free (trial-grouped) value (`|reported − 0.67| < 0.055`) — the inflated random-k-fold value (~0.79) fails. Numeric grader per the repo's numeric-grader discipline (grades the declared `accuracy` field, ignoring an explicitly-labelled random-k-fold/reference field).

### Validation (MEASURED locally, re-validated this revision)

- **Oracle** (`solution/compute.py`): trial-grouped accuracy = **0.666**; verifier **PASS (2/2)**.
- **Naive** plain-KFold fixture (0.791): verifier **FAIL** (`test_accuracy_is_leakage_free`).
- **Over-claim/hedge** fixture (reports 0.791 with a "may be optimistic" caveat — still the wrong headline number): verifier **FAIL**.
- **Defensible** trial-grouped variants — GroupKFold (0.689, the upper edge) and LeaveOneGroupOut (0.688): verifier **PASS**.
- Data fetches at runtime via `mne.datasets.sample.data_path()` (no credentials); `allow_internet=true`.
- **Step-5 frontier calibration PENDING** (maintainer step).

### Cost

`hard`. cpus 2, mem 8 GB, internet on (downloads the MNE sample dataset, ~1.5 GB, once). Deps: mne 1.12.1 + numpy/scipy/scikit-learn/pooch.
