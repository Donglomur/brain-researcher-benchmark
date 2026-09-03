## MIYAWAKI-001

**Proposal Title:** Decode binary contrast patterns from early-visual-cortex fMRI (Miyawaki 2008) — an un-cued cross-validation-leakage trap

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Task-fMRI multi-voxel pattern analysis (MVPA) / visual image decoding

**Source paper:** Miyawaki et al. (2008), *Neuron* 60:915, https://doi.org/10.1016/j.neuron.2008.11.004 (dataset: `nilearn.datasets.fetch_miyawaki2008`, cached under `~/nilearn_data`; ships to fetch at runtime).

**Status: FULL runnable task, oracle + naive validated locally. Step-5 frontier calibration PENDING (maintainer).**

### What this task is

A faithful, mostly-numeric **reproduction**: decode the 10x10 binary contrast pattern a subject is viewing from early-visual-cortex BOLD (the 20 `random`-image runs) with a linear ridge decoder and report the **cross-validated mean pixel decoding accuracy**. The mask (`dataset.mask`), masker (`NiftiMasker`, per-run `zscore_sample` + detrend), hemodynamic alignment (label shifted +2 volumes), sample selection (drop rest volumes), decoder (`Ridge(alpha=1.0)`, threshold 0.5) and metric (mean pixel accuracy) are all pinned. The **one thing left free is the cross-validation scheme**, and it is decisive.

### The un-cued lever (PRIVATE — never named in `instruction.md`)

**Random k-fold vs run/block-blocked (leave-one-run-out) cross-validation.** Each random contrast pattern is held on screen for several seconds, so a block of consecutive BOLD volumes shares the *same* 100-pixel label and neighbouring volumes are strongly temporally autocorrelated. A **random** k-fold split over volumes lets near-duplicate volumes from one stimulus block (identical target, correlated activity) land in both train and test — the decoder is scored partly on samples that leak information from its training set, and the accuracy is inflated. Blocking the folds by acquisition run (**leave-one-run-out**), or equivalently by stimulus block, is the correct, leakage-free estimate. The instruction never mentions folds, blocking, leakage, or runs-as-CV-unit; it only asks for "the cross-validated mean pixel decoding accuracy". The task ID is neutral (MIYAWAKI, not CVLEAK).

### Step-0 result (validated on cached `miyawaki2008`, nilearn 0.13.1 / scikit-learn 1.8.0)

20 random-image runs, `dataset.mask` (5438 voxels), 1320 stimulus volumes, 100 pixels, chance ≈ 0.50 (on-pixel rate 0.499):

| cross-validation scheme | mean_pixel_accuracy |
|---|---|
| **leave-one-run-out (CORRECT)** | **0.593** |
| group-k-fold by run (leakage-free) | 0.592 |
| group-k-fold by stimulus block (leakage-free) | 0.589 |
| random 10-fold (LEAKY) | 0.639 |
| random 5-fold / 2-fold (LEAKY) | 0.639 / 0.632 |

Gap **≈ +0.05** for the leaky choice. The correct value is stable: every leakage-free scheme lands in **0.589–0.598** and every random-volume scheme in **0.632–0.654**, a clean dead-band. Robustness checks: the leakage-free value is 0.586–0.597 across ridge `alpha` ∈ {1 … 10⁴}, 0.598 for a per-pixel L2-logistic decoder, and 0.589 for block-grouped CV; the random-fold value is 0.632–0.654 across fold counts, seeds, ridge/logistic. The delay and decoder are pinned because they shift the *absolute* number (e.g. no hemodynamic shift + random CV drops to ~0.57), so the only choice that moves the number *within the pinned pipeline* is the CV unit.

### Verifier (2 plain checks; `tests/test_outputs.py`)

Short reviewer-style pytest, schema-robust, no rubric:
1. **accuracy reported** — a parseable, above-chance mean pixel decoding accuracy exists.
2. **run-blocked accuracy reproduced** — the reported cross-validated accuracy is within **0.025** of the leave-one-run-out value **0.593**. Accuracies are gathered at any depth from any JSON (accuracy/score-keyed scalars, with per-fold / chance / std / train / and explicitly-leaky|random|kfold|naive keys excluded) and from prose (numbers next to "accuracy", percentages normalised). A random-fold ~0.64 is 0.046 away → fails; the honest ~0.59 → passes.

### Discrimination (validated locally)

| submission | reported mean_pixel_accuracy | verdict |
|---|---|---|
| reference oracle (leave-one-run-out; also records the leaky value under a descriptive key) | 0.593 | **PASS** |
| naive random 10-fold (leaky, everything else identical) | 0.639 | **FAIL** |
| prose-only "0.59" / "59% accuracy" | 0.59 | **PASS** |
| prose-only "0.639" / "64%" | 0.639 | **FAIL** |

Verifier robustness checked: a sophisticated submission that reports BOTH the honest 0.593 and a leaky comparison (0.639 under a `random_kfold`/`leaky` key or in prose) still passes, because the leaky value is excluded from the headline JSON candidates and test 2 grades the candidate closest to the run-blocked estimate.

### Step 5 — frontier calibration: PENDING (maintainer)

Oracle-passes and naive-fails are validated locally. The ≥2-frontier-family (k≥3, hand-rescored) gate — that un-cued frontier agents actually default to a random k-fold over volumes and report the inflated ~0.64 — is a maintainer step. (Note: `nilearn`'s own Miyawaki reconstruction example trains and tests on *separate* run sets, so a tutorial-faithful agent may avoid the trap; the calibration will measure how often un-cued agents default to random k-fold.)

### Cost / data caveat

`hard`. cpus 2, mem 8 GB, internet on (fetches `miyawaki2008`, ~100 MB, at runtime; timeouts 3600 s). Deps: nilearn 0.13.1 + scikit-learn 1.8.0 + scipy/pandas/nibabel/numpy (pinned in the Dockerfile to the versions the 0.593 ground truth was measured with). Runtime is dominated by masking 20 runs (a few seconds) and 20 leave-one-run-out ridge fits (seconds). Data caveat: `fetch_miyawaki2008` pulls from a public mirror; on rare mirror hiccups the fetch can time out and should be retried (an infra artifact, not a task FAIL).
