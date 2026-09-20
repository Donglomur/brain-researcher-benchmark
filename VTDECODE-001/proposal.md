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

### Verifier — PROOF OF WORK (`tests/test_outputs.py` + `tests/proof_of_work.py`)

Rebuilt to the proof-of-work contract (`PROOF_OF_WORK_SPEC.md`): a passing submission must be
impossible to produce without running the real leave-one-run-out decoding on the real subject.
A **held-out reference** (`tests/reference.npz`, built by running `solution/compute.py` and kept
out of the agent's container) stores the per-run held-out accuracies keyed by acquisition run,
plus the discriminating LORO vs random-fold numbers. The single headline accuracy is made
non-guessable by requiring the **per-fold breakdown** (`per_fold.csv`, now a required output) —
one held-out accuracy per fold. Three pillars, all required:

1. **per-fold table matches the held-out reference** — the submitted per-fold accuracies are the
   REAL per-run held-out values (keyed by held-out run when present, else matched by sorted value;
   within-tol fraction ≥ 0.7 OR correlation ≥ 0.8), non-constant. A random-fold or fabricated
   breakdown cannot reproduce them.
2. **headline recomputes** — the reported `cv_accuracy` equals the mean of the submitted per-fold
   rows AND the run-blocked reference **0.722** (± 0.06).
3. **run-blocked, not leaky** — the reported accuracy is materially below the random-fold value
   (~0.958) by ≥ 0.10; any leaky/random contrast the submission reports must itself be the real
   ~0.958 (guards a fabricated contrast). A secondary negation-aware prose guard requires the
   write-up to describe the cross-validation and not headline the ~0.96 as the accuracy.

The `per_fold.csv` requirement is phrased neutrally (fold, n_test_samples, accuracy) so it does
NOT reveal that run-blocking is the fix — a random-fold submission still produces a per-fold table,
but it will not match the held-out per-run reference and its headline (~0.96) fails pillars 2–3.

### Discrimination — validated locally via SUBPROCESS pytest (uvx, container-matched)

| submission | verdict | why |
|---|---|---|
| reference oracle (leave-one-run-out; per_fold.csv + cv_accuracy 0.722) | **PASS** | all 4 checks |
| no per_fold.csv | **FAIL** | pillar 1 (+2) |
| constant per-fold table (all = 0.722) | **FAIL** | pillar 1 non-constant guard |
| non-constant fabricated table (right mean 0.722, wrong per-fold) | **FAIL** | pillar 1 (match 0.42, corr 0.31) |
| naive random 8-fold (cv_accuracy 0.958, 8-fold table) | **FAIL** | pillars 1, 2, 3, prose |

### Reference provenance / packaging

- **Held-out reference** `tests/reference.npz` built from `solution/compute.py` on the pinned
  `haxby2001` subject-1 data (nilearn 0.13.1 / scikit-learn 1.8.0): `ref_run_ids` = runs 0–11,
  `ref_fold_acc` = per-run held-out accuracies, `ref_stats.loro_accuracy` = 0.7222,
  `ref_stats.random_kfold_accuracy` = 0.9583. Never ships to the container.
- **Pinned inputs:** Haxby **subject 1**, `mask_vt`, drop `rest`, the pinned masker/classifier.
  `fetch_haxby` returns a fixed, deterministic dataset, so the per-run numbers reproduce exactly
  on the pinned stack.
- **Packaging follow-up (maintainer):** the raw subject fetch is ~300 MB (> the 90 MB bake
  threshold), so the task keeps runtime fetch + `allow_internet=true`. Baking the derived VT
  masked time series (`X`, ~2 MB) into `environment/` to set `allow_internet=false` is a cheap
  maintainer follow-up.

### Step 5 — frontier calibration: PENDING (maintainer)

Oracle-passes and naive-fails are validated locally. The ≥2-frontier-family (k≥3, hand-rescored) gate — that un-cued frontier agents actually reach for random k-fold and report the inflated ~0.96 — is a maintainer step. (Note: `nilearn`'s own Haxby decoding tutorials use run/session-blocked CV, so a tutorial-faithful agent may avoid the trap; the calibration will measure how often un-cued agents default to random k-fold.)

### Cost / data caveat

`hard`. cpus 2, mem 8 GB, internet on (fetches `haxby2001` for subject 1, ~250 MB, at runtime; timeouts 3600 s). Deps: nilearn 0.13.1 + scikit-learn 1.8.0 + scipy/pandas/nibabel/numpy (pinned in the Dockerfile to the versions the 0.722 ground truth was measured with). Runtime is dominated by 12 leave-one-run-out SVM fits (a few minutes). Data caveat: `fetch_haxby` pulls from a public mirror; on rare mirror hiccups the fetch can time out and should be retried (an infra artifact, not a task FAIL).
