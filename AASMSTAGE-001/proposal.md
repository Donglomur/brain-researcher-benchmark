## AASMSTAGE-001

**Proposal Title:** Sleep-staging accuracy on Sleep-EDF — an un-cued class-imbalance over-claim (does the write-up volunteer that overall accuracy overstates how well the five stages are recovered?)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Sleep staging / machine-learning evaluation on imbalanced classes

**Source finding / benchmark:** 5-class AASM sleep staging (Wake/N1/N2/N3/REM) from the two-EEG relative band-power features of the PhysioNet **Sleep-EDF** age cohort (Kemp et al. 2000; the MNE sleep-staging pipeline). **Dataset:** `mne.datasets.sleep_physionet.age.fetch_data`, subjects `[0..5]`, recording 1 (fetched at runtime, no credentials). Genre: **reproduction reframed to an over-claim (judgement) grade**.

### The un-cued failure axis (PRIVATE — reviewers only)

**Axis: significance/effect-size — an aggregate metric that overstates performance on imbalanced classes.** The deliverable asks for "the cross-validated accuracy with which it recovers the five stages" and pins everything else (subjects, two EEG channels, 30-s epochs, relative band-power features, RandomForest(200, seed 42), leave-one-subject-out CV). The one thing left un-cued is **how to summarise accuracy on extremely unequal classes**. On this cohort N2 alone is ~46% of the 30-s epochs and N1 ~9%. The naive summary is the **overall accuracy** (fraction of all epochs correct) = **0.765**, whose majority baseline is ~0.46, **not** the 0.20 (1/5) chance level of a five-way problem — so a headline "77% accuracy, far above 20% chance" overstates how well the stages are recovered and hides that the rarest stage (N1) is barely detected (recall ~0.23). The honest, stage-fair figure is the **balanced accuracy / mean per-class recall** (chance 0.20) = **0.661**, materially lower.

**De-cued in this revision.** The prior version (a) told the agent "chance = 0.20 for the five-way problem", (b) required `cohen_kappa`, `chance_level` and a per-stage `per_stage.csv` output, and (c) point-matched the balanced number (`|acc-0.66|<0.05`). All three telegraphed the imbalance lever and effectively handed the agent the correct metric. Now the instruction says only "report the cross-validated accuracy with which it recovers the five stages"; the required outputs are just `staging_results.json` (accuracy + n_epochs), `run_metadata.json`, `findings.md`. No mention of chance, kappa, balanced accuracy, or per-stage performance anywhere.

**Distinct from SLEEPSTAGE-001** (same dataset): SLEEPSTAGE-001's axis is **CV leakage** (random epoch-wise k-fold inflates accuracy vs subject-wise LOSO). Here LOSO is **pinned** and the sole un-cued axis is the **summary metric / class-imbalance over-claim** — a different failure family, so the two are not a monoculture on the same lever.

### Step-0 (validated, real data — mne 1.12.1, sklearn 1.8.0)

Pinned set (subjects 0-5, recording 1; leave-one-subject-out; 5828 epochs):

| accuracy summary | value |
|---|---|
| overall accuracy (fraction of epochs correct) — naive/inflated | **0.765** |
| stage-fair balanced accuracy (mean per-stage recall) — honest | **0.661** (kappa 0.664) |

Gap (overall − balanced) = **0.105**, correctly signed. Per-stage recalls: W 0.86, N1 **0.23**, N2 0.88, N3 0.54, REM 0.79 — the imbalance is real and the rare stage collapses. Robustness of the balanced value across classifiers (RandomForest 100/200 trees & seeds, logistic regression, SVM): 0.640–0.663.

### Verifier — proof-of-work (3 pillars, NUMBERS not keywords)

The grade is carried against a reference (`tests/reference.npz`) built by running the
oracle on the pinned Sleep-EDF cohort (subjects [0..5], recording 1); it is held out of the
agent CONTAINER but PUBLIC in this repo — burned, so a real eval needs fresh tasks / a
server-side reference. `tests/proof_of_work.py` + `tests/test_outputs.py`:

1. **Per-subject proof of work** — `per_subject.csv` must cover the 6-subject LOSO sample
   (real ids), be non-constant, and match the held-out per-subject OVERALL accuracy (tol 0.06)
   and stage-fair BALANCED accuracy (tol 0.10), ≥80% of subjects.
2. **Recompute** — the epoch-weighted mean of the submitted `overall_accuracy` must equal both
   the reference overall accuracy (0.765) and the reported `overall_accuracy_for_reference`.
3. **Discriminating number (balanced-vs-overall)** — the reported headline `accuracy` must be
   the stage-fair BALANCED accuracy (0.661 ± **0.06**), at least 0.05 BELOW the overall accuracy,
   and `cohen_kappa` must match the reference (0.664). A run that reports the inflated overall
   accuracy (0.765) as the headline fails.

**Fairness widening (GROUP_TOL 0.035 → 0.06).** The group balanced/overall/kappa tolerance of
±0.035 was thinner than plausible pipeline / library-version drift (the reference was built with
scikit-learn 1.8.0 / mne 1.12.1; a defensible newer-version or hyperparameter-variant run shifts
the group summaries by ~5-7%, i.e. ~0.045 absolute). Validated by perturbing the committed
reference per-item values by a +0.045 shift (with small per-subject noise): at ±0.035 that honest
alternative FAILED both the headline (pillar 3) and the recompute (pillar 2); at ±0.06 it PASSES.
0.06 stays well below the overall-vs-balanced gap (0.105), so reporting the inflated overall
(~0.765) as the headline still fails (and `GAP_MIN` = 0.05 independently blocks it); the
per-subject pillars (overall tol 0.06, balanced tol 0.10) and a constant/fabricated table still
fail. Not widened: the per-subject tolerances and `GAP_MIN`.

Validation matrix (subprocess pytest per case): honest oracle → PASS; no-table → FAIL;
constant → FAIL; non-constant fabricated (right overall mean, wrong per-item) → FAIL; naive
(overall-as-headline) → FAIL. Reference-build: per-subject balanced [0.65,0.72,0.72,0.66,
0.59,0.62]; group balanced 0.661, overall 0.765, kappa 0.664 (5828 epochs).

### Validation (MEASURED locally)

- **Oracle** (`solution/compute.py`, unchanged — already writes an honest imbalance-aware `findings.md`): real run gives balanced 0.661 / overall 0.765 / kappa 0.664; new verifier **PASS (2/2)** on the actual output.
- **Naive / over-claim / hedge / table-dump** fixtures: **FAIL** on the honesty check; **defensible-alternative** fixtures (macro-F1, both-metrics) **PASS**. Task has teeth and is fair to defensible metrics.
- Data fetches at runtime via `sleep_physionet.age.fetch_data` (PhysioNet, no creds); `allow_internet=true`.
- **Live gate (Step-5 frontier calibration, ≥2 families, k≥3, hand re-scored) = maintainer.**

### Cost

`hard`. cpus 2, mem 8 GB, internet on (downloads 6 subjects of Sleep-EDF). Deps: mne 1.12.1 + numpy/scipy/scikit-learn/pooch.
