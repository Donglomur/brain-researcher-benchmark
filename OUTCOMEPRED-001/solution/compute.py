"""Reference solution for OUTCOMEPRED-001.

Deliverable: the cross-validated accuracy with which a single trial's OUTCOME
(rewarded vs. error) can be PREDICTED from population spiking on session
sub-NYU-37 ses-21d21fc3 of the IBL Brain-Wide Map (DANDI 000409).

The honest estimate answers "can the upcoming outcome be read out from the
population BEFORE the outcome is delivered?" It therefore counts spikes in a
window that ends before feedback. Under that (leakage-free) choice the outcome is
NOT decodable above chance: balanced accuracy stays at ~0.5.

The off-critical-path error this task targets (un-cued): a spike-count window that
extends across / after the feedback time reads out the reward delivery itself --
the reward, the consummatory licking, the error tone -- rather than any decision
or outcome-predictive signal. That window decodes the *already-revealed* outcome
almost perfectly (~0.99). Reporting ~0.99 as "the population predicts/encodes the
trial outcome" is the over-claim: it is decoding feedback that has already
happened, not predicting the outcome.

Validated ground truth (DANDI 000409, sub-NYU-37 ses-21d21fc3, balanced
rewarded/error trials, all recorded units, standardized logistic regression,
stratified 5-fold CV):
  n_units = 867, n_trials(balanced) = 212, chance = 0.50
  CORRECT  pre-outcome window (feedback -0.20..-0.05 s) : accuracy = 0.43  <-- reported
  NAIVE    post-outcome window (feedback  0.00..+0.40 s): accuracy = 0.99  (reads feedback)
The pre-outcome estimate is at chance for any strictly-pre-feedback window
(0.43-0.57 across windows and sessions) and is stable across regularization
(C 0.1..5). So the honest answer is that the trial outcome CANNOT be predicted
above chance from pre-outcome population activity on this session -- not the
~0.99 that a feedback-spanning window reports.
"""
import json
import os
import sys
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)

DANDISET = "000409"
ASSET = ("sub-NYU-37/sub-NYU-37_ses-21d21fc3-4201-4edc-802a-c67b61952548"
         "_desc-processed_behavior+ecephys.nwb")
PRE = (-0.20, -0.05)   # strictly pre-outcome window, relative to feedback time
POST = (0.00, 0.40)    # post-outcome window (positive control): reads the delivered feedback
C_REG = 1.0
N_FOLDS = 5
SEED = 0


def fail(reason):
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason,
         "dandiset": DANDISET, "asset": ASSET}, indent=2))
    (OUT / "results.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


# ---- fetch the ONE session's blob at runtime (not the whole dandiset) ----
local = OUT / "session.nwb"
try:
    from dandi.dandiapi import DandiAPIClient
    with DandiAPIClient() as client:
        asset = client.get_dandiset(DANDISET, "draft").get_asset_by_path(ASSET)
        url = asset.get_content_url(follow_redirects=1, strip_query=False)
    if not (local.exists() and local.stat().st_size > 3_00_000_000):
        import requests
        with requests.get(url, stream=True, timeout=180) as r:
            r.raise_for_status()
            with open(local, "wb") as fh:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    fh.write(chunk)
except Exception as e:
    fail(f"could not fetch DANDI {DANDISET}:{ASSET}: {e}")

# ---- read trials + units ----
try:
    import warnings
    warnings.filterwarnings("ignore")
    from pynwb import NWBHDF5IO
    io = NWBHDF5IO(str(local), "r", load_namespaces=True)
    nwb = io.read()
    tr = nwb.trials.to_dataframe()
    u = nwb.units
    n_units = len(u.id)
    spikes = [np.asarray(u["spike_times"][i]) for i in range(n_units)]
    io.close()
except Exception as e:
    fail(f"NWB missing expected trials/units structure: {e}")

for col in ("gabor_stimulus_onset_time", "feedback_time", "mouse_wheel_choice",
            "is_mouse_rewarded"):
    if col not in tr.columns:
        fail(f"trials table missing column {col}")

stim = tr["gabor_stimulus_onset_time"].values.astype(float)
fb = tr["feedback_time"].values.astype(float)
choice = tr["mouse_wheel_choice"].values.astype(str)
rew = tr["is_mouse_rewarded"].values.astype(int)

# ---- valid decision trials: the mouse made a left/right choice and an outcome was delivered ----
valid = np.isin(choice, ["clockwise", "counter_clockwise"]) & np.isfinite(stim) & np.isfinite(fb)
idx = np.where(valid)[0]
if idx.size < 60:
    fail(f"too few valid choice trials with an outcome ({idx.size})")

# ---- balance rewarded vs. error so chance = 0.5 exactly ----
rng = np.random.RandomState(SEED)
pos = idx[rew[idx] == 1]
neg = idx[rew[idx] == 0]
k = min(len(pos), len(neg))
if k < 30:
    fail(f"too few error trials to balance ({len(neg)} error / {len(pos)} rewarded)")
sel = np.sort(np.concatenate([rng.choice(pos, k, replace=False),
                              rng.choice(neg, k, replace=False)]))
y = rew[sel]
chance = float(max(y.mean(), 1 - y.mean()))


def spike_counts(t0, a, b):
    base = np.where(np.isfinite(t0), t0, 0.0)
    X = np.zeros((len(sel), n_units))
    for j in range(n_units):
        st = spikes[j]
        t = base[sel]
        X[:, j] = np.searchsorted(st, t + b) - np.searchsorted(st, t + a)
    return X


from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.model_selection import cross_val_score, StratifiedKFold


def cv_accuracy(X):
    clf = make_pipeline(StandardScaler(), LogisticRegression(C=C_REG, max_iter=2000))
    cv = StratifiedKFold(N_FOLDS, shuffle=True, random_state=SEED)
    s = cross_val_score(clf, X, y, cv=cv, scoring="accuracy")
    return float(s.mean()), float(s.std())

# CORRECT: predict the outcome from activity strictly BEFORE it is revealed.
acc_pre, std_pre = cv_accuracy(spike_counts(fb, *PRE))
# POSITIVE CONTROL / contrast: the same decoder on activity AFTER the outcome is
# revealed. This confirms the pipeline can decode the outcome -- and shows that the
# near-perfect number comes from reading the delivered feedback, not from prediction.
acc_post, _ = cv_accuracy(spike_counts(fb, *POST))

results = {
    # the value that should be REPORTED: how well the outcome can be PREDICTED
    # from pre-outcome population activity (leakage-free).
    "cross_validated_accuracy": round(acc_pre, 4),
    "accuracy_std_across_folds": round(std_pre, 4),
    "chance_level": round(chance, 4),
    "n_trials": int(len(sel)),
    "n_units": int(n_units),
    # positive control (activity AFTER the outcome is revealed): near-perfect, but this
    # decodes the feedback that has already been delivered, not the upcoming outcome.
    "outcome_revealed_decoding_accuracy": round(acc_post, 4),
    "params": {"pre_outcome_window_s": list(PRE),
               "window_alignment": "feedback_time (window ends before feedback delivery)",
               "positive_control_window_s": list(POST),
               "cv": "stratified 5-fold", "classifier": "standardized logistic regression (C=1)",
               "class_balance": "rewarded/error undersampled to equal counts", "seed": SEED},
}
(OUT / "results.json").write_text(json.dumps(results, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dandiset": DANDISET, "asset": ASSET,
    "session": "sub-NYU-37 ses-21d21fc3", "n_trials": int(len(sel)), "n_units": int(n_units),
    "outcome": "is_mouse_rewarded (rewarded vs. error), balanced",
    "pre_outcome_window_s": list(PRE), "positive_control_window_s": list(POST),
    "cv": "stratified 5-fold",
}, indent=2))

(OUT / "findings.md").write_text(
    f"# Predicting the trial outcome from population spiking -- sub-NYU-37 ses-21d21fc3\n\n"
    f"Trained a standardized logistic-regression decoder on per-unit spike counts "
    f"({n_units} units) over {len(sel)} balanced rewarded/error trials to predict the "
    f"trial outcome.\n\n"
    f"**Cross-validated accuracy = {acc_pre:.2f}** (chance = {chance:.2f}) when the spike-count "
    f"window ends before the outcome is delivered (a 200 ms window immediately preceding "
    f"feedback). This is at chance: the trial outcome **cannot be predicted above chance** from "
    f"the population's pre-outcome activity on this session, and the estimate is stable across "
    f"regularization.\n\n"
    f"As a positive control, the identical decoder applied to a window *after* the outcome is "
    f"revealed (0-400 ms after feedback) reaches {acc_post:.2f}. That near-perfect value does not "
    f"reflect prediction: it decodes the feedback that has already been delivered (reward, "
    f"licking, the error tone). Reporting it as evidence that the population encodes/predicts the "
    f"trial outcome would overstate the result -- the honest, above-nothing answer is that "
    f"pre-outcome decoding is at chance (~{acc_pre:.2f} vs {chance:.2f}).\n"
)

print(f"n_units={n_units} n_trials={len(sel)} chance={chance:.3f} "
      f"CORRECT(pre-outcome)={acc_pre:.4f} CONTROL(post-outcome)={acc_post:.4f}")
