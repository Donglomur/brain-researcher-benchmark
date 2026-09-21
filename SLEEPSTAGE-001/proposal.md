## SLEEPSTAGE-001

**Proposal Title:** 5-class AASM sleep staging on Sleep-EDF — an un-cued cross-validation-leakage over-claim (does the write-up volunteer that a random epoch-wise k-fold inflates the accuracy?)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Sleep EEG / machine-learning evaluation (leakage)

**Source finding / benchmark:** Automatic 5-class AASM sleep staging on the **Sleep-EDF Expanded** database (Kemp et al. 2000; PhysioNet), reported as cross-validated accuracy / Cohen kappa. **Dataset:** `mne.datasets.sleep_physionet.age.fetch_data`, subjects `[0,1,2,3,4,5]`, recording 1. Genre: **reproduction reframed to an over-claim / leakage (judgement) grade**.

### The un-cued failure axis (PRIVATE — reviewers only)

**Axis: statistical inference — cross-validation leakage (circularity/leakage family, Kriegeskorte-style).** The deliverable ("report the **cross-validated** staging accuracy / Cohen kappa") names the metric but never says *how* to cross-validate. Consecutive 30-s epochs from one night are highly autocorrelated (sleep is piecewise-stationary) and share subject identity, so a **random epoch-wise k-fold leaks**: near-duplicate neighbours of each test epoch, and other epochs from the same subject, land in the training set → the accuracy is **inflated** (0.832 vs 0.775). The honest, subject-generalising estimate is **subject-wise (leave-one-subject-out)** CV. Everything else is pinned (subjects, recording, channels Fpz-Cz + Pz-Oz, 30-s epochs, the 5-class AASM mapping, relative band-power features, RandomForest(200, seed 0)), so only the CV scheme moves the number.

**Why this axis and not a "leak that survives LOSO":** the pinned pipeline is scale-invariant (RandomForest) and its features are per-epoch (per-epoch relative band power, per-epoch Welch PSD), so a feature-standardisation-fit-across-all-subjects leak produces **no measurable signal** (RF ignores feature scale; measured no-op). For this pipeline the only real, measured leakage lever is the **CV split** itself. Rather than change the pinned classifier to a scale-sensitive one (whose standardisation leak on band-power features is expected to be negligible), the task keeps the genuine, measured CV-scheme leak and hardens the *grade*.

**Distinct from AASMSTAGE-001** (same dataset): AASMSTAGE-001 pins LOSO and grades the **class-imbalance** over-claim (overall vs stage-fair accuracy). This task pins nothing about the CV scheme and grades the **leakage** over-claim (random epoch-wise vs subject-wise CV) — a different failure family, so the two are not a monoculture on the same lever.

### De-cued + reframed in this revision

- Prior version **point-matched** the subject-wise accuracy (`|acc-0.775|<0.03`), which effectively told the agent which CV scheme to use and reduced the task to a number.
- Now: the required `per_fold.csv` output (which nudged toward CV structure) is dropped; the instruction asks only for the cross-validated accuracy + kappa, and never mentions leakage, autocorrelation, subject-wise CV or generalisation.
- The verifier grades the **judgement**, not the number.

### Step-0 (validated, real data — mne 1.12.1, sklearn 1.8.0)

Pinned subject set `[0,1,2,3,4,5]`, recording 1; RandomForest(200, random_state=0) on relative band-power features; 5828 epochs:

| CV scheme | accuracy | Cohen kappa |
|---|---|---|
| **subject-wise (leave-one-subject-out) — honest** | **0.775** | 0.682 |
| random epoch-wise 5-fold — naive/leaky | 0.832 | 0.763 |

Gap (random − subject-wise) = **0.0575** accuracy, correctly signed (random inflated).

### Verifier — proof-of-work (3 pillars, NUMBERS not keywords)

The grade is carried against a reference (`tests/reference.npz`) built by running the oracle on
the pinned Sleep-EDF set (subjects [0..5], night 1); it is held out of the agent CONTAINER but
PUBLIC in this repo — burned, so a real eval needs fresh tasks / a server-side reference.
`tests/proof_of_work.py` + `tests/test_outputs.py`:

1. **Per-subject proof of work** — `per_subject.csv` must cover the 6-subject LOSO sample
   (real ids), be non-constant, and match the held-out per-subject leave-one-subject-out
   accuracy (tol 0.06) and kappa (tol 0.08), ≥80% of subjects.
2. **Recompute** — the epoch-weighted mean of the submitted `accuracy` must equal both the
   reference subject-wise accuracy (0.775) and the reported headline accuracy.
3. **Discriminating number (LOSO-vs-random)** — the reported headline must be the subject-wise
   accuracy (0.775 ± **0.045**) and kappa (0.682), the reported random-k-fold accuracy must match
   the reference (0.832 ± 0.05), and the subject-wise value must be at least 0.04 BELOW the
   random-k-fold value. A run that reports the leaky random-k-fold accuracy (0.832) as the
   headline fails (also on the recompute pillar).

**Fairness widening (GROUP_TOL 0.035 → 0.045).** ±0.035 on the group accuracy/kappa was thinner
than plausible pipeline / library-version drift (~5%). Validated by perturbing the committed
reference per-item values (`ref_acc`/`ref_kappa`/`subj_*`/`rand_*`) by a +0.04 shift: at ±0.035
that honest alternative FAILED the headline (pillar 3) and the recompute (pillar 2); at ±0.045 it
PASSES. **HONEST-LIMITATION:** the widening is CAPPED at 0.045 because it must stay below the
LOSO-vs-random-kfold gap (0.058) — otherwise reporting the leaky random-kfold accuracy (0.832) as
the headline would slip through. So this task can only absorb ~5% drift, at the low end of the
plausible range; a larger honest drift cannot be admitted without weakening the leakage
discriminator (`GAP_MIN` = 0.04 still independently blocks headline = random-kfold). Not widened:
`RAND_TOL`, `GAP_MIN`, per-subject tolerances. A constant/fabricated table and the leaky-headline
over-claim still fail.

Validation matrix (subprocess pytest per case): honest oracle → PASS; no-table → FAIL;
constant → FAIL; non-constant fabricated (right mean, wrong per-item) → FAIL; naive
(random-k-fold-as-headline) → FAIL. Reference-build: per-subject LOSO accuracy [0.76,0.83,
0.72,0.82,0.75,0.76]; subject-wise 0.775 / random 0.832 (5828 epochs).

### Validation (MEASURED locally)

- **Oracle** (`solution/compute.py`, unchanged — already contrasts the schemes and names the leakage): real run gives subject-wise 0.775 / random 0.832; new verifier **PASS (2/2)** on the actual output.
- **Naive / over-claim / hedge / terse-LOSO / pipeline-vocab** fixtures **FAIL**; **defensible** LOSO-with-rationale and contrast fixtures **PASS**.
- Data fetches at runtime via `sleep_physionet.age.fetch_data` (PhysioNet); `allow_internet=true`. **Caveat:** PhysioNet throttles downloads (~4 min/subject); the subject set is pinned small (6). Dev validation used the cached copy under `~/mne_data/physionet-sleep-data`.
- **Live gate (Step-5 frontier calibration, ≥2 families, k≥3, hand re-scored) = maintainer.**

### Cost

`hard`. cpus 2, mem 8 GB, internet on (downloads 6 subjects × 1 night of Sleep-EDF; PhysioNet is slow — generous timeouts). Deps: mne 1.12.1 + numpy/scipy/scikit-learn/pooch.
