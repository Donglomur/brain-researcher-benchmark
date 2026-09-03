## AASMSTAGE-001

**Proposal Title:** Per-stage AASM sleep-staging performance on Sleep-EDF — an un-cued class-imbalance/metric trap (overall accuracy overstates how well the five stages are identified)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Sleep staging / machine-learning evaluation on imbalanced classes

**Source finding / benchmark:** 5-class AASM sleep staging (Wake/N1/N2/N3/REM) from the single-EEG relative band-power features of the PhysioNet **Sleep-EDF** age cohort (Kemp et al. 2000; the MNE sleep-staging pipeline). **Dataset:** `mne.datasets.sleep_physionet.age.fetch_data`, subjects `[0..5]`, recording 1 (fetched at runtime, no credentials). Genre: **reproduction**.

### The un-cued lever (PRIVATE — reviewers only)

The deliverable ("report the **accuracy with which the five stages are identified**, chance = 0.20") names the quantity but never says **how to summarise accuracy on extremely unequal classes**. On this cohort N2 alone is ~46% of the 30-s epochs and N1 ~9%. The naive summary is the **overall accuracy** (fraction of all epochs correct), which is dominated by the common stages — its majority baseline is ~0.46, **not** the 0.20 (1/5) chance level of a five-way problem — so it overstates how well the stages are recovered and hides that the rarest stage (N1) is barely detected (recall ~0.23). The stage-fair figure is the **mean of the five per-stage recalls (balanced accuracy)**, whose chance level **is** 0.20. Everything else is pinned (subjects, two EEG channels, 30-s epochs, relative band-power features, RandomForest(200, seed 42), leave-one-subject-out CV), so only the summary metric moves the number.

**Distinct from the shipped SLEEPSTAGE-001** (same dataset): SLEEPSTAGE-001's lever is the **cross-validation scheme** (subject-wise vs random-epoch k-fold — a leakage lever) and it grades the *overall* subject-wise accuracy (~0.775). This task **pins a leakage-free leave-one-subject-out CV** and the sole lever is the **summary metric** (overall vs stage-fair accuracy) — a class-imbalance/metric lever, a different failure family. (Precedent for one dataset, two levers: erpcore N170/P3 amplitude tasks; three eegbci tasks.)

### Step-0 (validated, real data — mne 1.12.1, sklearn 1.8.0)

Pinned set (subjects 0-5, recording 1; leave-one-subject-out; 5828 epochs):

| accuracy summary | value |
|---|---|
| **stage-fair balanced accuracy (mean per-stage recall) — correct** | **0.661** (kappa 0.664) |
| overall accuracy (fraction of epochs correct) — naive/inflated | **0.765** |

Gap (overall − balanced) = **0.105**, correctly signed. Per-stage recalls: W 0.86, N1 **0.23**, N2 0.88, N3 0.54, REM 0.79 — the imbalance is real and the rare stage is poorly recovered. Robustness of the **balanced** value across reasonable classifiers (RandomForest 100/200 trees & seeds, logistic regression, SVM): **0.640-0.663** (classifier-invariant, unlike a binary balanced accuracy which is threshold-dependent — this is why a 5-class target is used). Every overall-accuracy value is **≥ 0.73**. Chance = 0.20.

The verifier accepts `|reported − 0.66| < 0.05` (accept [0.610, 0.710]), sized to pass any genuine stage-fair estimate and to fail the inflated overall-accuracy value.

**Fairness note (reviewers):** grading the balanced value is defensible because the brief states chance = 0.20 — the chance level of the equal-weight (per-stage) accuracy; overall accuracy's chance on this imbalanced set is ~0.46, so a reported overall accuracy is inconsistent with the stated chance. The required `per_stage.csv` makes the imbalance and the N1 failure explicit in the outputs. The task tests the standard imbalanced-evaluation expertise (report a base-rate-fair metric), which is the intended difficulty.

### Verifier (2 plain checks)

`tests/test_outputs.py`: (1) a five-class staging computed with a per-stage breakdown and a valid above-chance accuracy; (2) the reported headline accuracy is the stage-fair (balanced) value (`|reported − 0.66| < 0.05`) — the inflated overall-accuracy value (~0.765) fails. Numeric grader per the repo's discipline (grades the declared `accuracy` field, ignoring an explicitly-labelled overall/reference field).

### Validation (MEASURED locally)

- **Oracle** (`solution/compute.py`): stage-fair accuracy = **0.661** (kappa 0.664); verifier **PASS (2/2)**.
- **Naive** overall-accuracy fixture: accuracy = **0.765**; verifier **FAIL** (`test_accuracy_is_stage_fair`). Task has teeth.
- Data fetches at runtime via `sleep_physionet.age.fetch_data` (PhysioNet, no creds); `allow_internet=true`.
- **Step-5 frontier calibration PENDING** (maintainer step).

### Cost

`hard`. cpus 2, mem 8 GB, internet on (downloads 6 subjects of Sleep-EDF). Deps: mne 1.12.1 + numpy/scipy/scikit-learn/pooch.
