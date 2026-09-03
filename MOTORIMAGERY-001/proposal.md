## MOTORIMAGERY-001

**Proposal Title:** Imagined hands-vs-feet CSP+LDA decoding on EEGBCI — an un-cued cross-validation-leakage trap (fitting CSP on all epochs inflates the accuracy)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Motor-imagery BCI / machine-learning evaluation

**Source finding / benchmark:** Common-Spatial-Patterns + LDA decoding of *imagined* movement from the sensorimotor rhythms of the **PhysioNet EEG Motor Movement/Imagery** dataset (Schalk et al. 2004; BCI2000), reported as cross-validated decoding accuracy. **Dataset:** `mne.datasets.eegbci.load_data`, subjects `1-10`, runs `[6, 10, 14]` (imagined "both fists" vs "both feet"). Genre: **reproduction**.

### The un-cued lever (PRIVATE — reviewers only)

The deliverable ("report the **cross-validated** decoding accuracy") names the metric but never says **where the CSP spatial filters are fit** relative to the train/test split. CSP is a **supervised** spatial filter: it uses the class labels to build the channel mixtures whose log-variance feeds the LDA. Fitting CSP **once on the whole recording** and cross-validating only the LDA leaks the held-out epochs into the spatial filters → the accuracy is badly **inflated** (near ceiling). The honest estimate refits CSP **inside every fold** on the training epochs only (a scikit-learn `Pipeline` of CSP→LDA does this). Everything else is pinned — subjects, runs, 7-30 Hz band, 1.0-2.0 s epochs, all EEG channels, 4 CSP components, LDA, 5-fold stratified CV — so only the placement of the CSP fit moves the number.

### Step-0 (validated, real data — mne 1.12.1)

Pinned set (subjects 1-10, runs 6/10/14); per-subject 5-fold stratified CV; accuracy = mean over subjects:

| CSP fit placement | accuracy |
|---|---|
| **within each fold (nested / leakage-free) — correct** | **0.673** (kappa 0.346) |
| fit once on ALL epochs, then CV the LDA — naive/leaky | **0.942** |

Gap (leaky − nested) = **0.269** accuracy, correctly signed (fit-on-all inflated). Robustness of the leakage-free value across un-pinned choices (CV fold count/seed, 4-6 CSP components, mu-band lower edge 7-8 Hz): **0.647-0.711**; every CSP-fit-on-all scheme is **>= 0.918** (near ceiling). Chance = 0.5.

The subject set is **PINNED**; the oracle re-measures the within-fold accuracy on this fixed set at authoring time. The verifier accepts `|reported − 0.673| < 0.10` (accept [0.573, 0.773]), sized to exclude the inflated fit-on-all value; a CSP-fit-on-all answer fails.

### Verifier (2 plain checks)

`tests/test_outputs.py`: (1) a two-class decoding computed with a per-subject CV breakdown and a valid above-chance accuracy; (2) the reported headline accuracy is the leakage-free (within-fold CSP) value (`|reported − 0.673| < 0.10`) — the inflated CSP-fit-on-all value (~0.942) fails. Numeric grader per the repo's numeric-grader discipline (grades the declared `accuracy` field, ignoring an explicitly-labelled reference/leaky field).

### Validation (MEASURED locally)

- **Oracle** (`solution/compute.py`, EEGBCI subjects 1-10): within-fold accuracy = **0.673** (kappa 0.346); verifier **PASS (2/2)**.
- **Naive** CSP-fit-on-all fixture: accuracy = **0.942**; verifier **FAIL** (`test_accuracy_is_leakage_free`). Task has teeth.
- Data fetches at runtime via `eegbci.load_data` (PhysioNet); `allow_internet=true`.
- **Step-5 frontier calibration PENDING** (maintainer step).

### Cost

`hard`. cpus 2, mem 8 GB, internet on (downloads 10 subjects × 3 runs of EEGBCI). Deps: mne 1.12.1 + numpy/scipy/scikit-learn/pooch.
