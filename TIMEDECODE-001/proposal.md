## TIMEDECODE-001

**Proposal Title:** Single-trial MEG decoding of stimulus modality on the MNE sample dataset — an un-cued cross-validation-non-independence trap (pooling time samples with a random k-fold inflates the accuracy)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** MEG/EEG single-trial decoding / machine-learning evaluation

**Source finding / benchmark:** Single-trial sensor-level decoding of stimulus modality (auditory vs visual) from the MNE **sample** MEG dataset (`sample_audvis_filt-0-40`), reported as cross-validated decoding accuracy. **Dataset:** `mne.datasets.sample` (fetched at runtime, no credentials). Genre: **reproduction**.

> **HARDENING NOTE (de-cue, this revision).** The first cut's CV bullet read "Evaluate with **5-fold cross-validation**", which an agent can read as *endorsing* a plain `StratifiedKFold(5)` — i.e. the instruction telling it to do the leaky thing, which would make the fail unfair. Reworded so only the **fold count (5)** is pinned (for reproducibility) and the **fold-construction scheme is explicitly left to the analyst's judgement** ("should follow sound cross-validation practice"). A plain random k-fold is now a *choice the agent makes*, not one the brief dictates — the fail is a genuine un-cued judgement miss. Kept off-path: the brief still never mentions trials, grouping, independence, or leakage.

> **HARDENING NOTE (second pass — finer neutral intermediate).** The prior verifier graded the
> per-fold table by BAND only (folds must sit ≤ 0.739) plus the public counts (n_trials=288,
> n_samples=8640). Those alone are fabricable: an agent that never runs a decoder can hand-write five
> in-band per-fold rows and echo the public counts. Added a **required `decoding_timecourse.csv`** —
> cross-validated decoding accuracy at each post-stimulus time sample (0.05–0.45 s). At a single time
> sample every trial contributes exactly one example, so this temporal-decoding curve is **identical
> whether the pooled folds would later be split leak-free or leakily** — it is a NEUTRAL intermediate
> that does NOT reveal the un-cued fold-scheme judgement, yet its **shape** (rapid post-onset rise,
> early ~0.09 s peak ≈0.96, structured decline to ≈0.72) cannot be produced without running a real
> decoder on the real evoked responses. The grader validates it by **magnitude-invariant Pearson
> correlation ≥ 0.8** against a held-out reference profile (stored in `reference.npz` as
> `ref_timecourse`/`ref_time_s`, built from `solution/compute.py`). Honest/defensible LR variants
> score corr ≥ 0.97; flat, monotone, random, reversed and gaussian-bump fabrications all score ≤ 0.57.
> The leakage-band discriminator on the per-fold table + headline is kept unchanged (the fold scheme
> is un-cued, so per-fold rows are band-checked, NOT element-matched — that would unfairly reject the
> reference's own GroupKFold/LOGO variants).
>
> **Residual (HONEST-LIMITATION).** The time course forces a real decoder run, closing the
> "passes with no decoder" hole. It does not, by itself, bind the pooled trial-grouped scalar (~0.67):
> an agent who has already run the real per-time decoder could in principle hand-fabricate an in-band
> per-fold table with guessed ~0.67 values. That residual attack requires doing the substantive real
> work (load → epoch → decode); the specific leak-free fold-scheme judgement then still relies partly
> on the frontier gate, as the brief accepts for this band-graded axis.

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

### Verifier — PROOF OF WORK (`tests/test_outputs.py` + `tests/proof_of_work.py`)

Rebuilt to the proof-of-work contract (`PROOF_OF_WORK_SPEC.md`). A **held-out reference**
(`tests/reference.npz`, kept out of the container) stores the trial-grouped per-fold accuracies,
the accept window, and the discriminating trial-grouped vs random-k-fold numbers, all re-measured
across every defensible grouped variant (SGKF/GKF/LOGO = 0.666–0.689) and every random-k-fold
variant (SKF/KF = 0.789–0.792). Pillars, all required:

1. **per-fold table in the leakage-free band** — `per_fold.csv` present, non-constant, and ≥ 80% of
   the per-fold accuracies are in the trial-grouped band (≤ 0.739, the midpoint between the grouped
   max 0.689 and the leaky min 0.789). A leaky per-fold table (folds ~0.79) fails here, not just on
   the mean. When trial counts are reported, they must match whole-trial hold-out
   (`n_test_samples ≈ n_test_trials × 30`).
2. **pipeline actually run** — the reported `n_trials` (288 epochs surviving the pinned
   grad=4000e-13 rejection) and `n_samples_total` (8640 pooled trial×time samples), and the per-fold
   test-sample total, must match the reference; a fabricator who did not build the epochs cannot
   know these. The reported headline recomputes from the per-fold rows and lands in the accept
   window [0.616, 0.724].
3. **trial-grouped, not leaky** — the reported accuracy is materially below the random-k-fold value
   (~0.791) by ≥ 0.05; any random-k-fold contrast reported must itself be the real ~0.791.

### Validation — via SUBPROCESS pytest (uvx, container-matched)

- **Oracle** (`solution/compute.py`): trial-grouped 0.666, 5 per-fold rows in band, counts 288/8640 → **PASS (5/5)**.
- **no per_fold.csv** → **FAIL**. **constant table** (all 0.666) → **FAIL** (non-constant guard).
- **fabricated, wrong counts** (honest-band folds but n_trials/n_samples guessed wrong) → **FAIL** (pillar 2 counts).
- **naive random-k-fold** (folds ~0.79, headline 0.79) → **FAIL** (pillars 1, 2, 3).
- **Defensible** trial-grouped variants GroupKFold (0.689) / LeaveOneGroupOut (0.688) sit inside the accept window → **PASS**.
- Data fetches at runtime via `mne.datasets.sample.data_path()` (no credentials); `allow_internet=true`.
- **Note (residual):** the honest headline (~0.67) is a single scalar, so its accept window is wider
  than a QSMDIPOLE-tight one; fabrication is closed by additionally pinning the epoch/sample counts
  (288/8640, hard to know without running) and the trial-grouped per-fold band. **Step-5 frontier
  calibration PENDING** (maintainer step).

### Reference provenance / packaging

- `tests/reference.npz`: `ref_fold_acc` (SGKF5 per-fold), `ref_stats.honest_accuracy` 0.666,
  `ref_stats.leaky_accuracy` 0.791, accept window [0.616, 0.724], `n_trials` 288,
  `n_samples_total` 8640. Built from `solution/compute.py` on the MNE `sample` data (mne 1.12.1).
- **Packaging follow-up (maintainer):** the MNE sample download is ~1.5 GB (>> 90 MB bake
  threshold), so runtime fetch + `allow_internet=true` are kept.

### Cost

`hard`. cpus 2, mem 8 GB, internet on (downloads the MNE sample dataset, ~1.5 GB, once). Deps: mne 1.12.1 + numpy/scipy/scikit-learn/pooch.
