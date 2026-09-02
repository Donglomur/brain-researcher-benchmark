"""Reference solution for STEINMETZ-001.

Deliverable: cross-validated accuracy of decoding the mouse's UPCOMING left/right choice
from population spiking, session sub-Cori ses-20161214 (DANDI 000017, Steinmetz et al.
2019, "Distributed coding of choice, action and engagement across the mouse brain").

The correct analysis avoids two off-critical-path errors that both inflate the estimate:

  (1) Movement-window contamination. A window taken AROUND the response (peri-movement)
      reads out motor-execution activity, so the classifier decodes the movement that has
      already begun, not the upcoming choice. The honest window is strictly PRE-movement,
      aligned to the visual stimulus and ending before the wheel turn.

  (2) Cross-validation leakage. Trials are temporally structured (drift, stimulus blocks),
      so RANDOM k-fold lets neighbouring correlated trials sit in train and test at once,
      optimistically biasing accuracy. BLOCKED (contiguous) folds respect trial order.

Validated ground truth (DANDI 000017, sub-Cori ses-20161214, dataset-'included' left/right
trials, all recorded units, 250 ms spike-count window, standardized logistic regression,
5-fold CV):
  n_trials = 134, chance (majority) = 0.515
  CORRECT  pre-movement (stim..+0.25 s) + blocked CV : accuracy = 0.72   <-- reported
  NAIVE    peri-movement (resp +/-0.1 s) + random CV : accuracy = 0.95   (motor + leakage)
  (trap) pre + random = 0.76 ; (trap) peri + blocked = 0.94
The correct value is stable across regularization (C in 0.1..5 -> 0.72 +/- 0.01). So the
honest upcoming-choice decoder reaches ~0.72 (well above chance) -- not the ~0.95 that a
peri-movement window with random CV reports.
"""
import json
import os
import sys
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)

DANDISET = "000017"
ASSET = "sub-Cori/sub-Cori_ses-20161214T120000.nwb"
WIN = 0.25          # 250 ms spike-count window
C_REG = 1.0
N_FOLDS = 5
SEED = 0


def fail(reason):
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason, "dandiset": DANDISET, "asset": ASSET}, indent=2))
    (OUT / "results.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


# ---- fetch the ONE session's S3 blob at runtime (not the whole dandiset) ----
local = OUT / "cori.nwb"
try:
    from dandi.dandiapi import DandiAPIClient
    with DandiAPIClient() as client:
        asset = client.get_dandiset(DANDISET, "draft").get_asset_by_path(ASSET)
        url = asset.get_content_url(follow_redirects=1, strip_query=False)
    if not (local.exists() and local.stat().st_size > 3_00_000_000):
        import requests
        with requests.get(url, stream=True, timeout=120) as r:
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

for col in ("included", "response_choice", "visual_stimulus_time", "response_time"):
    if col not in tr.columns:
        fail(f"trials table missing column {col}")

# ---- pinned trial / unit / feature machinery ----
sel = tr[(tr["included"]) & (tr["response_choice"] != 0)].copy()
if len(sel) < 40:
    fail(f"too few included left/right trials ({len(sel)})")
y = (sel["response_choice"].values > 0).astype(int)
chance = float(max(y.mean(), 1 - y.mean()))


def spike_counts(t0col, a, b):
    t0 = sel[t0col].values
    X = np.zeros((len(sel), n_units))
    for j in range(n_units):
        st = spikes[j]
        X[:, j] = np.searchsorted(st, t0 + b) - np.searchsorted(st, t0 + a)
    return X


from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.model_selection import cross_val_score, StratifiedKFold, KFold


def cv_accuracy(X, scheme):
    clf = make_pipeline(StandardScaler(), LogisticRegression(C=C_REG, max_iter=2000))
    cv = (StratifiedKFold(N_FOLDS, shuffle=True, random_state=SEED) if scheme == "random"
          else KFold(N_FOLDS, shuffle=False))
    s = cross_val_score(clf, X, y, cv=cv, scoring="accuracy")
    return float(s.mean()), float(s.std())

# CORRECT: strictly pre-movement window (stimulus-aligned) + blocked CV
X_pre = spike_counts("visual_stimulus_time", 0.0, WIN)
acc_correct, std_correct = cv_accuracy(X_pre, "blocked")

# For the record / positive contrast: the peri-movement + random-CV estimate.
X_peri = spike_counts("response_time", -0.1, 0.1)
acc_naive, _ = cv_accuracy(X_peri, "random")

results = {
    # the value that should be REPORTED: the honest, pre-movement, held-out (blocked) accuracy
    "cross_validated_accuracy": round(acc_correct, 4),
    "accuracy_std_across_folds": round(std_correct, 4),
    "chance_level": round(chance, 4),
    "n_trials": int(len(sel)),
    "n_units": int(n_units),
    "peri_movement_random_cv_accuracy": round(acc_naive, 4),  # the inflated estimate, for contrast
    "params": {"window_s": WIN, "window_alignment": "visual_stimulus_time (strictly pre-movement)",
               "cv": "blocked 5-fold (contiguous, trial order preserved)",
               "classifier": "standardized logistic regression (C=1)", "seed": SEED},
}
(OUT / "results.json").write_text(json.dumps(results, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dandiset": DANDISET, "asset": ASSET,
    "session": "sub-Cori ses-20161214", "n_trials": int(len(sel)), "n_units": int(n_units),
    "choice": "response_choice sign (left=-1 vs right=+1; no-go excluded)",
    "window_s": WIN, "cv": "blocked 5-fold",
}, indent=2))

(OUT / "findings.md").write_text(
    f"# Decoding the mouse's upcoming left/right choice — sub-Cori ses-20161214\n\n"
    f"Decoded the upcoming choice from population spike counts ({n_units} units) on "
    f"{len(sel)} included left/right trials, using a 250 ms per-unit spike-count window and a "
    f"standardized logistic-regression classifier.\n\n"
    f"**Cross-validated accuracy = {acc_correct:.2f}** (chance = {chance:.2f}). This uses a "
    f"strictly **pre-movement** window aligned to visual-stimulus onset (0-250 ms, before the "
    f"wheel turn) and **blocked (contiguous) cross-validation** that respects trial order. The "
    f"decoder therefore reads out the *upcoming* choice, not motor execution, and the estimate is "
    f"not inflated by leakage between temporally adjacent trials.\n\n"
    f"For contrast, a peri-movement window (response +/-100 ms) with random k-fold CV gives "
    f"{acc_naive:.2f} -- but that number decodes the movement already underway and is optimistically "
    f"biased by CV leakage, so it overstates how well the *upcoming* choice can be predicted. The "
    f"honest, above-chance answer is ~{acc_correct:.2f}.\n"
)

print(f"n_trials={len(sel)} n_units={n_units} chance={chance:.3f} "
      f"CORRECT(pre+blocked)={acc_correct:.4f} NAIVE(peri+random)={acc_naive:.4f}")
