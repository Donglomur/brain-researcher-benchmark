## VTDECODE-001

**Proposal Title:** Reproduce the Haxby ventral-temporal object-decoding accuracy — an un-cued cross-validation-leakage trap

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Task-fMRI multi-voxel pattern analysis (MVPA)

**Source paper:** Haxby et al. (2001), *Science* 293:2425, https://doi.org/10.1126/science.1063736 (dataset: `nilearn.datasets.fetch_haxby`, cached under `~/nilearn_data`; ships to fetch at runtime).

**Status: FULL runnable task, oracle + naive validated locally. Step-5 frontier calibration PENDING (maintainer).**

### What this task is

A faithful, mostly-numeric **reproduction**: decode the eight Haxby object categories from ventral-temporal cortex (`mask_vt`) with a linear SVM and report the **cross-validated decoding accuracy**. The masker (`NiftiMasker`, `zscore_sample` + detrend), classifier (`SVC(kernel="linear", C=1)`), subject (1), and sample selection (drop `rest`) are all pinned. The **one thing left free is the cross-validation scheme**, and it is decisive.

### The un-cued lever (PRIVATE — never named in `instruction.md`)

**Random k-fold vs run-blocked (leave-one-run-out) cross-validation.** Each object category is presented as a sustained block within a run, so successive volumes from the same run are strongly temporally autocorrelated. A **random** k-fold split lets near-adjacent volumes from one block land in both train and test — the classifier is scored partly on samples that leak information from its training set, and the accuracy is badly inflated. Blocking the folds by acquisition run (`chunks`) — **leave-one-run-out** — is the correct, leakage-free estimate. The instruction never mentions folds, blocking, leakage, or `chunks`-as-CV-unit; it only asks for "the cross-validated decoding accuracy". The task ID is neutral (VTDECODE, not CVLEAK).

### Step-0 result (validated on cached `haxby2001`, nilearn 0.13.1 / scikit-learn 1.8.0)

Subject 1, `mask_vt` (577 voxels), 864 object volumes across 12 runs, chance = 0.125:

| cross-validation scheme | cv_accuracy |
|---|---|
| **leave-one-run-out (CORRECT)** | **0.722** |
| random 8-fold (LEAKY) | 0.958 |
| random stratified 5-fold (LEAKY) | 0.951 |

Gap **≈ +0.23** for the leaky choice. The correct value is stable: identical (0.722) across `standardize` in {`zscore_sample`, `zscore`, `True`} with detrend on, and across `C` ∈ {0.1 … 5.0}; drops only to 0.68 with detrend off. The leaky value is always ≈ 0.95–0.97. The subject-by-subject gap (subjects 1–4) is +0.24 to +0.36 (mean +0.25), so the lever is robust; subject 1 is pinned for a single reproducible number.

### Verifier (2 plain checks; `tests/test_outputs.py`)

Short reviewer-style pytest, schema-robust, no rubric:
1. **accuracy reported** — a parseable, above-chance decoding accuracy exists.
2. **run-blocked accuracy reproduced** — the reported cross-validated accuracy is within **0.06** of the leave-one-run-out value **0.722**. Accuracies are gathered at any depth from any JSON (accuracy/score-keyed scalars, with per-fold / chance / std / train / and explicitly-leaky|random|kfold|naive keys excluded) and from prose (numbers next to "accuracy", percentages normalised). A random-fold ~0.96 is 0.23 away → fails; the honest ~0.72 → passes.

### Discrimination (validated locally)

| submission | reported cv_accuracy | verdict |
|---|---|---|
| reference oracle (leave-one-run-out; also records the leaky value under a descriptive key) | 0.722 | **PASS** |
| naive random 5-fold (leaky, everything else identical) | 0.951 | **FAIL** |
| prose-only "72.2%" / "0.72" / "72% accuracy" | 0.72 | **PASS** |
| prose-only "95.8%" | 0.958 | **FAIL** |

Verifier robustness checked: a sophisticated submission that reports BOTH the honest 0.722 and a leaky comparison (0.958 under a `random_kfold`/`leaky` key) still passes, because the leaky value is excluded from the headline candidates; the honest value is what is graded.

### Step 5 — frontier calibration: PENDING (maintainer)

Oracle-passes and naive-fails are validated locally. The ≥2-frontier-family (k≥3, hand-rescored) gate — that un-cued frontier agents actually reach for random k-fold and report the inflated ~0.96 — is a maintainer step. (Note: `nilearn`'s own Haxby decoding tutorials use run/session-blocked CV, so a tutorial-faithful agent may avoid the trap; the calibration will measure how often un-cued agents default to random k-fold.)

### Cost / data caveat

`hard`. cpus 2, mem 8 GB, internet on (fetches `haxby2001` for subject 1, ~250 MB, at runtime; timeouts 3600 s). Deps: nilearn 0.13.1 + scikit-learn 1.8.0 + scipy/pandas/nibabel/numpy (pinned in the Dockerfile to the versions the 0.722 ground truth was measured with). Runtime is dominated by 12 leave-one-run-out SVM fits (a few minutes). Data caveat: `fetch_haxby` pulls from a public mirror; on rare mirror hiccups the fetch can time out and should be retried (an infra artifact, not a task FAIL).
