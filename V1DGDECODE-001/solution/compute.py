"""Reference solution for V1DGDECODE-001.

Deliverable: how accurately the drift *direction* of a drifting grating (8 directions, 45 deg
apart) can be read out from the single-trial two-photon population response of one Allen Brain
Observatory field of primary visual cortex (VISp), reported as the classification accuracy of a
linear population decoder (de Vries et al. 2020, ophys_experiment_id 501271265, VISp,
three_session_A, drifting-gratings block).

The correct analysis reports a *cross-validated* accuracy: the decoder is fit on one set of trials
and evaluated on a disjoint set of held-out trials (here 5-fold stratified cross-validation, so
every trial is predicted by a decoder that never saw it, averaged over folds and a few random
splits). With 215 neurons (features) and ~600 trials, a linear classifier can memorise the training
trials almost perfectly, so the *in-sample* (resubstitution / training-set) accuracy -- fitting the
decoder on all trials and scoring it on those same trials -- is a badly optimistic estimate of how
well direction can actually be read out: it runs ~0.9-1.0, essentially the model's capacity to
overfit 215-dimensional inputs, not its generalisation. The honest, generalising read-out accuracy
is the cross-validated one.

Validated ground truth (ophys_experiment_id 501271265, VISp, drifting gratings; per-trial response
= mean dF/F over the presentation window; all imaged neurons; 8-way drift-direction classification
pooled across temporal frequency; features standardised on the training split; linear SVM):
  n imaged neurons                                        = 215
  n grating trials                                        = 598
  chance (1/8)                                            = 0.125
  IN-SAMPLE (train == test, resubstitution) accuracy      = ~0.95-1.0   (overfit; optimistic)
  CROSS-VALIDATED accuracy (5-fold, held-out trials)      = ~0.62       <-- reported
The cross-validated value is stable across linear decoders (linear SVM ~0.62, logistic ~0.67,
LDA ~0.70) and folds; the in-sample value (~0.95+) fails the numeric match.
"""
import json
import os
import sys
import time
import warnings
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)

EXP_ID = 501271265
REGION = "VISp"
STIMULUS = "drifting_gratings"
N_FOLDS = 5
N_SPLITS = 5           # repeated stratified splits for a stable held-out estimate
SEED = 0
MANIFEST = os.environ.get("BOC_MANIFEST", "/app/boc_cache/manifest.json")


def fail(reason):
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason,
         "ophys_experiment_id": EXP_ID}, indent=2))
    (OUT / "results.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


def _retry(fn, what, n=8):
    """The Allen Institute API intermittently returns 502s; retry with backoff."""
    last = None
    for a in range(n):
        try:
            return fn()
        except Exception as ex:  # noqa: BLE001
            last = ex
            sys.stderr.write(f"[retry {a}] {what}: {type(ex).__name__}: {str(ex)[:90]}\n")
            time.sleep(4 + a * 3)
    raise RuntimeError(f"{what} failed after {n} attempts: {last}")


# ---- open the ONE experiment at runtime via the Allen Brain Observatory cache (no creds) ----
try:
    from allensdk.core.brain_observatory_cache import BrainObservatoryCache
    Path(MANIFEST).parent.mkdir(parents=True, exist_ok=True)
    boc = BrainObservatoryCache(manifest_file=MANIFEST)
    data_set = _retry(lambda: boc.get_ophys_experiment_data(EXP_ID), "get_ophys_experiment_data")
except Exception as e:  # noqa: BLE001
    fail(f"could not open Allen Brain Observatory experiment {EXP_ID}: {e}")

try:
    _, dff = data_set.get_dff_traces()          # (n_cells, n_frames)
    meta = data_set.get_metadata()
    stim = data_set.get_stimulus_table(STIMULUS)
except Exception as e:  # noqa: BLE001
    fail(f"experiment {EXP_ID} lacks dF/F traces or {STIMULUS} table: {e}")

nU = dff.shape[0]
if nU < 20:
    fail(f"too few imaged neurons ({nU})")

ori = stim["orientation"].values.astype(float)
tf = stim["temporal_frequency"].values.astype(float)
starts = stim["start"].values.astype(int)
ends = stim["end"].values.astype(int)
is_blank = np.isnan(ori) | np.isnan(tf)
if "blank_sweep" in stim.columns:
    is_blank = is_blank | (stim["blank_sweep"].values.astype(float) > 0)

g = np.where(~is_blank)[0]
if len(g) < 100:
    fail(f"too few {STIMULUS} presentations ({len(g)})")

# ---- single-trial population response: mean dF/F over each presentation window, all neurons ----
X = np.full((len(g), nU), np.nan)
for i, ti in enumerate(g):
    a, b = int(starts[ti]), int(ends[ti])
    if b <= a:
        b = a + 1
    X[i] = dff[:, a:b].mean(axis=1)
y = ori[g].astype(int)                            # drift direction label (0..315 deg)
n_dir = len(set(y.tolist()))
if n_dir < 8:
    fail(f"unexpected number of drift directions: {n_dir}")

try:
    from sklearn.svm import LinearSVC
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import StratifiedKFold
except Exception as e:  # noqa: BLE001
    fail(f"scikit-learn unavailable: {e}")


def cv_accuracy(seed):
    """5-fold stratified cross-validated accuracy; the scaler and decoder are fit ONLY on the
    training trials of each fold and evaluated on the held-out trials of that fold."""
    skf = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=seed)
    accs = []
    for tr, te in skf.split(X, y):
        sc = StandardScaler().fit(X[tr])
        clf = LinearSVC(C=0.05, max_iter=5000)
        clf.fit(sc.transform(X[tr]), y[tr])
        accs.append(float((clf.predict(sc.transform(X[te])) == y[te]).mean()))
    return float(np.mean(accs))


cv_by_split = [cv_accuracy(SEED + s) for s in range(N_SPLITS)]
decoding_accuracy = float(np.mean(cv_by_split))
decoding_accuracy_sd = float(np.std(cv_by_split))

# in-sample (resubstitution) accuracy -- reported only as the optimistic contrast, never the headline
sc_all = StandardScaler().fit(X)
clf_all = LinearSVC(C=0.05, max_iter=5000).fit(sc_all.transform(X), y)
in_sample_accuracy = float((clf_all.predict(sc_all.transform(X)) == y).mean())

chance = 1.0 / n_dir

results = {
    # the value that should be REPORTED: cross-validated (generalising) decoding accuracy
    "decoding_accuracy": round(decoding_accuracy, 4),
    "chance_level": round(chance, 4),
    "n_neurons": int(nU),
    "n_trials": int(len(g)),
    "n_directions": int(n_dir),
    "cross_validation": f"{N_FOLDS}-fold stratified, averaged over {N_SPLITS} random splits",
    "decoding_accuracy_sd_across_splits": round(decoding_accuracy_sd, 4),
    "in_sample_training_accuracy": round(in_sample_accuracy, 4),   # optimistic contrast, for reference
    "params": {
        "region": REGION,
        "stimulus": "drifting_gratings (8 drift directions, pooled across temporal frequency)",
        "response": "mean dF/F over the presentation window",
        "decoder": "linear SVM on standardised single-trial population response vectors",
        "features": "all imaged neurons",
    },
}
(OUT / "results.json").write_text(json.dumps(results, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok",
    "ophys_experiment_id": EXP_ID,
    "targeted_structure": meta.get("targeted_structure"),
    "session_type": meta.get("session_type"),
    "cre_line": meta.get("cre_line"),
    "n_neurons": int(nU),
    "n_grating_trials": int(len(g)),
    "n_directions": int(n_dir),
    "chance_level": round(chance, 4),
    "decoder": "linear SVM (standardised single-trial population response)",
    "accuracy_estimation": f"{N_FOLDS}-fold stratified cross-validation, held-out trials, "
                           f"averaged over {N_SPLITS} random splits",
}, indent=2))

(OUT / "findings.md").write_text(
    f"# Decoding drift direction from a VISp two-photon population -- Allen Brain Observatory {EXP_ID}\n\n"
    f"From the single-trial population response of {nU} simultaneously imaged VISp neurons (mean "
    f"dF/F over each grating presentation), a linear decoder predicts which of the {n_dir} drift "
    f"directions was shown with a **cross-validated accuracy of {decoding_accuracy:.2f}** "
    f"(chance {chance:.3f}), estimated by {N_FOLDS}-fold stratified cross-validation on held-out "
    f"trials and averaged over {N_SPLITS} random splits (standard deviation "
    f"{decoding_accuracy_sd:.02f} across splits). Every trial is scored by a decoder that was fit "
    f"only on other trials.\n\n"
    f"For contrast, fitting the decoder on all {len(g)} trials and scoring it on those same trials "
    f"gives an in-sample accuracy of {in_sample_accuracy:.2f}. That number is not a measure of how "
    f"well direction can be read out: with {nU} neurons as features and only {len(g)} trials, the "
    f"linear decoder can nearly memorise the training set, so the in-sample figure mostly reflects "
    f"overfitting capacity. The honest, generalising read-out accuracy of this field is "
    f"~{decoding_accuracy:.2f}.\n"
)

print(f"EXP={EXP_ID} nCells={nU} nTrials={len(g)} nDir={n_dir} "
      f"CV(held-out)={decoding_accuracy:.4f}+/-{decoding_accuracy_sd:.4f} "
      f"in-sample={in_sample_accuracy:.4f} chance={chance:.4f}")
