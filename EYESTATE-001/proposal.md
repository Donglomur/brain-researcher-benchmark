## EYESTATE-001

**Proposal Title:** Reproduce the ABIDE eyes-open-vs-closed decoding accuracy — an un-cued acquisition-site leakage trap

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Resting-state functional-connectivity decoding (multi-site)

**Source paper:** ABIDE Preprocessed / PCP (Craddock et al. 2013; Di Martino et al. 2014, *Mol Psychiatry*, 10.1038/mp.2013.78), dataset `nilearn.datasets.fetch_abide_pcp` (cached under `~/nilearn_data`; ships to fetch at runtime). Methodological basis: acquisition-site / scanner effects dominate multi-site connectivity and inflate naive cross-validation (e.g. site-harmonisation literature; Yan et al. 2013 on eyes-open/closed resting connectivity).

**Status: FULL runnable task, oracle + naive validated locally. Step-5 frontier calibration PENDING (maintainer).**

### What this task is

A faithful, mostly-numeric **reproduction**: decode eyes-open vs eyes-closed from ABIDE resting-state CC200 correlation connectivity with a linear SVM and report the **cross-validated balanced accuracy**. The fetch parameters (`cpac`, `band_pass_filtering=True`, `global_signal_regression=False`, `rois_cc200`), subject inclusion, label, connectivity (Pearson correlation, vectorised), classifier (`StandardScaler` + `LinearSVC(C=1)`) and metric (balanced accuracy) are all pinned. The **one thing left free is the cross-validation scheme**, and it is decisive.

### The un-cued lever (PRIVATE — never named in `instruction.md`)

**Random k-fold vs site-blocked (leave-one-site-out) cross-validation.** In ABIDE each acquisition site used a single eyes-open/closed protocol, so eye status is almost perfectly aligned with `SITE_ID`, and connectivity carries a strong site-specific fingerprint. A **random** k-fold split puts subjects from a site in both train and test, so the classifier reads a held-out subject's eye status off its site fingerprint and the accuracy is inflated. Blocking the folds by acquisition **site** (leave-one-site-out) forces the model to generalise to sites it never saw, leaving only the genuine, transferable eyes-open/closed effect. The instruction never mentions folds, blocking, sites-as-a-nuisance, leakage, or the eye-status↔site confound; it only asks for "the cross-validated balanced accuracy". The task ID is neutral (EYESTATE, not SITELEAK).

### Step-0 result (validated on cached ABIDE `cpac/filt_noglobal/rois_cc200`, nilearn 0.13.1 / scikit-learn 1.8.0)

N = 1035 participants (700 eyes-open, 335 eyes-closed), 20 sites, 19 900 connectivity edges, chance = 0.5:

| cross-validation scheme | balanced accuracy |
|---|---|
| **leave-one-site-out (CORRECT)** | **0.737** |
| stratified site-grouped 10-fold (site-blocked) | 0.751 |
| random 10-fold (LEAKY) | 0.867 |

Gap **≈ +0.13** for the leaky choice. The correct value is stable: site-blocked schemes give 0.737–0.774 across `LinearSVC`/`LogisticRegression` and across leave-one-site-out vs stratified-group-K-fold; the random-fold value is 0.867–0.878 across three seeds and both classifiers. Leave-one-site-out (0.737) is pinned as the single reproducible number; the verifier window admits the other site-blocked variants.

### Verifier (2 plain checks; `tests/test_outputs.py`)

Short reviewer-style pytest, schema-robust, no rubric:
1. **accuracy reported** — a parseable, above-chance balanced accuracy exists.
2. **site-blocked accuracy reproduced** — the reported balanced accuracy is within **0.09** of the leave-one-site-out value **0.737**. Accuracies are gathered at any depth from any JSON (balanced-accuracy/score-keyed scalars, with per-fold / chance / std / train / and explicitly-leaky|random|kfold|naive|unblocked keys excluded) and from prose. A random-fold ~0.87 is 0.13 away → fails; a site-blocked ~0.74–0.77 → passes.

### Discrimination (validated locally)

| submission | reported balanced accuracy | verdict |
|---|---|---|
| reference oracle (leave-one-site-out; also records the leaky value under a descriptive key) | 0.737 | **PASS** |
| naive random 10-fold (leaky, everything else identical) | 0.867 | **FAIL** |
| stratified site-grouped K-fold (site-blocked variant) | 0.751 | **PASS** |
| prose-only "balanced accuracy … 0.74" | 0.74 | **PASS** |

Verifier robustness: a submission that reports BOTH the honest 0.737 and a leaky comparison (0.867 under a `random_kfold`/`leaky` key) still passes, because the leaky value is excluded from the headline candidates.

### Distinctness

Different dataset (ABIDE multi-site resting-state FC) and different nuisance (acquisition **site/scanner** batch fingerprint) from the shipped Haxby within-subject temporal-autocorrelation CV task (VTDECODE/DECODE) and from OBJCAT's feature-selection circularity. Existing ABIDE tasks target group-difference multiple-comparisons (AUTCONN/AUTISMDMN) or significance-vs-effect-size (BWAS); none address cross-validation site leakage in a decoder. The mandate lists "scanner" as a valid TASK-1 confound.

### Step 5 — frontier calibration: PENDING (maintainer)

Oracle-passes and naive-fails are validated locally. The ≥2-frontier-family (k≥3, hand-rescored) gate — that un-cued frontier agents default to random k-fold and report the inflated ~0.87 — is a maintainer step. (Note: a submission aware of ABIDE site effects may reach for site-blocked CV and avoid the trap; the calibration measures how often un-cued agents default to random folds.)

### Cost / data caveat

`hard`. cpus 2, mem 8 GB, internet on (fetches ABIDE `cpac/filt_noglobal/rois_cc200`, ~0.2 GB of region time series, at runtime; timeouts 3600 s). Deps: nilearn 0.13.1 + scikit-learn 1.8.0 + scipy/pandas/nibabel/numpy (pinned in the Dockerfile to the versions the 0.737 ground truth was measured with). Runtime is dominated by the leave-one-site-out SVM fits over ~20 site folds on ~20 000 features (a few minutes). Data caveat: `fetch_abide_pcp` pulls from a public S3 mirror; on rare mirror hiccups the fetch can time out and should be retried (an infra artifact, not a task FAIL).
