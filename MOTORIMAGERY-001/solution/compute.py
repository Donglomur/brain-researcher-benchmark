"""Reference solution for MOTORIMAGERY-001.

Decode imagined movement (hands vs feet) from the mu/beta EEG of the PhysioNet EEGBCI
motor-imagery runs with CSP + LDA, per subject, and report the CROSS-VALIDATED decoding
accuracy averaged over a pinned set of subjects.

The pipeline is fully pinned (subjects, runs, band-pass, epoch window, all EEG channels,
4 CSP components, LDA, per-subject 5-fold stratified CV), so the group-mean accuracy
reproduces at ~0.673. Fitting CSP inside every fold (a scikit-learn Pipeline of CSP->LDA)
is the natural, leakage-free default and is what this reference does.

What the brief leaves to the analyst -- and what an honest write-up must VOLUNTEER -- is
how to judge that number. The group-mean accuracy (0.673) is only marginally above chance
(one-sample t vs 0.5 over the 10 subjects: p ~ 0.02), and, crucially, decoding is highly
UNRELIABLE at the individual level: with only ~45 trials per subject the finite-sample
chance distribution is wide (permutation null SD ~ 0.08, so accuracies up to ~0.65 are not
significant), and a per-subject permutation test shows only ~6/10 subjects decode
significantly above chance, with 2 subjects actually BELOW chance. Comparing each subject's
accuracy to the nominal 0.5 (rather than to a permutation null / confidence interval)
overstates how many "work" -- the "exceeding chance by chance" pitfall (Combrisson & Jerbi,
J Neurosci Methods 2015). For a BCI, which must work per user, the honest conclusion is that
a substantial fraction of users cannot drive this decoder ("BCI illiteracy"; Blankertz et
al. 2010; Vidaurre & Blankertz 2010) -- not the flat "motor imagery is decodable at 67%".
"""
import csv
import json
import os
import sys
import warnings
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)

SUBJECTS = list(range(1, 11))     # PINNED fixed subject set
RUNS = [6, 10, 14]                # imagined hands (both fists) vs feet (both feet)
FMIN, FMAX = 7.0, 30.0            # mu/beta band
TMIN, TMAX = 1.0, 2.0            # sustained-imagery window, s relative to cue
N_COMPONENTS = 4
N_SPLITS = 5
N_PERM = 200                      # per-subject permutation null
CHANCE = 0.5


def fail(reason):
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason,
         "dataset_id": "eegbci (PhysioNet EEG Motor Movement/Imagery)"}, indent=2))
    (OUT / "decoding_results.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason}))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    import mne
    from mne.datasets import eegbci
    from mne.decoding import CSP
    from sklearn.pipeline import Pipeline
    from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
    from sklearn.model_selection import (StratifiedKFold, cross_val_score,
                                         permutation_test_score)
    from sklearn.metrics import accuracy_score, cohen_kappa_score
    from scipy import stats
    mne.set_log_level("ERROR")
except Exception as e:  # pragma: no cover
    fail(f"import failed: {e}")


def subject_epochs(subj):
    """Band-passed hands-vs-feet epochs (all EEG channels) for one subject."""
    fnames = eegbci.load_data(subjects=[subj], runs=RUNS, verbose=False)
    raws = [mne.io.read_raw_edf(f, preload=True, verbose=False) for f in fnames]
    raw = mne.concatenate_raws(raws, verbose=False)
    eegbci.standardize(raw)                       # canonical 10-05 channel names
    raw.set_montage(mne.channels.make_standard_montage("standard_1005"), verbose=False)
    raw.filter(FMIN, FMAX, fir_design="firwin", skip_by_annotation="edge", verbose=False)
    # T1 = both fists (hands), T2 = both feet (feet); T0 (rest) is ignored
    events, _ = mne.events_from_annotations(raw, event_id=dict(T1=2, T2=3), verbose=False)
    picks = mne.pick_types(raw.info, eeg=True, exclude="bads")
    ep = mne.Epochs(raw, events, dict(hands=2, feet=3), TMIN, TMAX, proj=True,
                    picks=picks, baseline=None, preload=True, verbose=False)
    return ep.get_data(copy=False), ep.events[:, -1]


def csp_lda():
    return Pipeline([
        ("csp", CSP(n_components=N_COMPONENTS, reg=None, log=True, norm_trace=False)),
        ("lda", LinearDiscriminantAnalysis()),
    ])


try:
    data = {s: subject_epochs(s) for s in SUBJECTS}
except Exception as e:
    fail(f"could not build motor-imagery epochs from EEGBCI: {e}")

if any(len(y) < 20 or len(np.unique(y)) < 2 for _, y in data.values()):
    fail("insufficient epochs / classes in at least one subject")

rows = []
acc_sub, kappa_sub, p_sub, nulls = [], [], [], []
for s in SUBJECTS:
    X, y = data[s]
    cv = StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=42)

    # honest, leakage-free CV: CSP refit inside every fold (sklearn Pipeline does this)
    yt, yp = [], []
    for tr, te in cv.split(X, y):
        clf = csp_lda().fit(X[tr], y[tr])
        yt.append(y[te]); yp.append(clf.predict(X[te]))
    yt = np.concatenate(yt); yp = np.concatenate(yp)
    a = float(accuracy_score(yt, yp)); k = float(cohen_kappa_score(yt, yp))

    # per-subject permutation null -> the finite-sample chance distribution & p-value
    _, perm, pval = permutation_test_score(
        csp_lda(), X, y, cv=StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=42),
        scoring="accuracy", n_permutations=N_PERM, random_state=0, n_jobs=1)

    acc_sub.append(a); kappa_sub.append(k); p_sub.append(float(pval)); nulls.append(perm)
    rows.append(dict(subject=s, n_epochs=int(len(y)), accuracy=round(a, 4),
                     kappa=round(k, 4), perm_p=round(float(pval), 4)))

acc = float(np.mean(acc_sub))
kappa = float(np.mean(kappa_sub))
n_epochs_total = int(sum(len(y) for _, y in data.values()))
p_sub = np.array(p_sub); acc_sub_a = np.array(acc_sub)
n_sig = int((p_sub < 0.05).sum())
n_below = int((acc_sub_a < CHANCE).sum())
null_sd = float(np.mean([n.std() for n in nulls]))
# empirical upper chance ceiling ~ 0.5 + 2*SD of the finite-sample null
chance_ceiling = float(CHANCE + 2 * null_sd)
t_stat, p_group = stats.ttest_1samp(acc_sub_a, CHANCE)

(OUT / "decoding_results.json").write_text(json.dumps({
    "accuracy": acc,
    "cohen_kappa": kappa,
    "n_subjects": len(SUBJECTS),
    "n_epochs_total": n_epochs_total,
    "n_classes": 2,
    "classes": ["hands", "feet"],
    "chance_level": CHANCE,
    # reliability summary (what the honest write-up is built from)
    "group_p_vs_chance": float(p_group),
    "n_subjects_significant_perm_p05": n_sig,
    "n_subjects_below_chance": n_below,
    "finite_sample_null_sd": round(null_sd, 4),
    "empirical_chance_ceiling_2sd": round(chance_ceiling, 4),
    "per_subject_accuracy": [round(x, 4) for x in acc_sub],
    "per_subject_perm_p": [round(x, 4) for x in p_sub.tolist()],
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok",
    "dataset_id": "eegbci (PhysioNet EEG Motor Movement/Imagery Dataset)",
    "subjects": SUBJECTS,
    "runs": RUNS,
    "contrast": "imagined hands (both fists) vs feet (both feet)",
    "band_hz": [FMIN, FMAX],
    "epoch_sec": [TMIN, TMAX],
    "channels": "all EEG channels",
    "decoder": f"CSP(n_components={N_COMPONENTS}) -> LinearDiscriminantAnalysis",
    "cv_scheme": "per-subject 5-fold stratified CV (CSP refit within each fold)",
}, indent=2))

(OUT / "findings.md").write_text(f"""# MOTORIMAGERY-001 - imagined hands-vs-feet CSP+LDA decoding (EEGBCI)

On the pinned EEGBCI motor-imagery set (subjects {SUBJECTS}, runs {RUNS}; band-pass
{FMIN:g}-{FMAX:g} Hz; {TMIN:g}-{TMAX:g} s epochs; all EEG channels; CSP with
{N_COMPONENTS} components + LDA; per-subject 5-fold cross-validation), the cross-validated
decoding accuracy averaged over the {len(SUBJECTS)} subjects is:

* **accuracy = {acc:.3f}** (Cohen kappa = {kappa:.3f}), chance = {CHANCE:.2f}
  ({n_epochs_total} epochs total).

## What this actually supports

Taken at face value 0.67 looks "above chance", but that number should not be read as a
working BCI:

* **The group effect is marginal.** A one-sample t-test of the 10 subject accuracies
  against {CHANCE:.2f} gives p = {p_group:.3f} (n = 10) -- statistically above chance at the
  group level, but only just.
* **Above 0.5 is not the same as significant.** With only ~45 trials per subject the
  finite-sample chance distribution is wide: the per-subject permutation null has
  SD ~ {null_sd:.3f}, so accuracies up to ~{chance_ceiling:.2f} are **not** significantly
  above chance. Comparing each subject to the nominal 0.5 rather than to this null
  overstates how many "decode" (the *exceeding-chance-by-chance* pitfall, Combrisson &
  Jerbi 2015).
* **Decoding is unreliable at the individual level.** A per-subject permutation test
  (200 permutations) finds only **{n_sig}/{len(SUBJECTS)}** subjects significantly above
  chance (p < 0.05), and **{n_below}** subject(s) actually **below** chance. Per-subject
  accuracies: {[round(x,2) for x in acc_sub]}.

For a motor-imagery BCI -- which has to work for the individual user -- the honest
conclusion is that a substantial fraction of these users cannot drive the decoder ("BCI
illiteracy"; Blankertz et al. 2010; Vidaurre & Blankertz 2010). The 0.67 group mean masks
that per-user reliability, so "imagined movement is decodable at 67%" over-claims what the
data support.
""")

print(f"OK: group acc={acc:.4f} kappa={kappa:.4f} | group p={p_group:.4f} | "
      f"n_sig={n_sig}/{len(SUBJECTS)} | n_below_chance={n_below} | "
      f"null_sd={null_sd:.4f} | n_epochs={n_epochs_total}")
