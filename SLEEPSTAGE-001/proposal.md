## SLEEPSTAGE-001

**Proposal Title:** 5-class AASM sleep staging on Sleep-EDF — an un-cued cross-validation-leakage trap (random epoch-wise k-fold inflates the accuracy)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Sleep EEG / machine-learning evaluation

**Source finding / benchmark:** Automatic 5-class AASM sleep staging on the **Sleep-EDF Expanded** database (Kemp et al. 2000; PhysioNet), reported as cross-validated accuracy / Cohen kappa. **Dataset:** `mne.datasets.sleep_physionet.age.fetch_data`, subjects `[0,1,2,3,4,5]`, recording 1. Genre: **reproduction**.

### The un-cued lever (PRIVATE — reviewers only)

The deliverable ("report the **cross-validated** staging accuracy / Cohen kappa") names the metric but never says *how* to cross-validate. Consecutive 30-s epochs from one night are highly autocorrelated (sleep is piecewise-stationary) and share subject identity, so a **random epoch-wise k-fold leaks**: near-duplicate neighbours of each test epoch, and other epochs from the same subject, land in the training set → the accuracy is badly **inflated**. The honest estimate of generalisation to a new subject/night is **subject-wise (leave-one-subject-out)** CV. The instruction pins everything else — subjects, recording, channels (Fpz-Cz + Pz-Oz), 30-s epochs, the 5-class AASM mapping, relative band-power features, and a 200-tree random forest — so only the CV scheme moves the number.

### Step-0 (validated, real data — mne 1.12.1)

Pinned subject set `[0,1,2,3,4,5]`, recording 1; RandomForest(200, random_state=0) on relative band-power features:

| CV scheme | accuracy | Cohen kappa |
|---|---|---|
| **subject-wise (leave-one-subject-out) — correct** | **0.775** | 0.682 |
| random epoch-wise 5-fold — naive/leaky | 0.832 | 0.763 |

Gap (random − subject-wise) = **0.0575** accuracy, correctly signed (random inflated). (Earlier 2-subject cache Step-0: random 0.856 / kappa 0.804 vs subject-wise 0.701 / kappa 0.593 — same direction.)

The subject set is **PINNED** (a firm number requires exactly these subjects); the oracle re-measures the subject-wise accuracy on this fixed set at authoring time. The verifier accepts `|reported − 0.775| < 0.03`, sized to exclude the inflated random-k-fold value; a random-k-fold answer fails.

### Verifier (2 plain checks)

`tests/test_outputs.py`: (1) staging computed into the 5 AASM classes with a per-fold CV breakdown and a valid accuracy + kappa; (2) the reported headline accuracy is the subject-generalising (leave-one-subject-out) value (`|reported − 0.775| < 0.03`) — the inflated random-k-fold value (~0.832) fails. Numeric grader per the repo's numeric-grader discipline (grades the declared `accuracy` field, ignoring an explicitly-labelled reference/leaky field).

### Validation (MEASURED locally)

- **Oracle** (`solution/compute.py`, cached Sleep-EDF subjects 0–5): subject-wise accuracy = **0.775** (kappa 0.682); verifier **PASS (2/2)**.
- **Naive** random epoch-wise 5-fold fixture: accuracy = **0.832**; verifier **FAIL** (`test_crossvalidated_accuracy_is_subjectwise`). Task has teeth.
- Data fetches at runtime via `sleep_physionet.age.fetch_data` (PhysioNet); `allow_internet=true`. **Caveat:** PhysioNet throttles downloads (~4 min/subject); the subject set is pinned small (6) and fixed so the number reproduces. Dev validation used the cached copy under `~/mne_data/physionet-sleep-data`.
- **Step-5 frontier calibration PENDING** (maintainer step): oracle-passes + naive-fails validated locally; the ≥2-frontier-family difficulty gate is a maintainer step.

### Cost

`hard`. cpus 2, mem 8 GB, internet on (downloads 6 subjects × 1 night of Sleep-EDF; PhysioNet is slow — generous timeouts). Deps: mne 1.12.1 + numpy/scipy/scikit-learn/pooch.
