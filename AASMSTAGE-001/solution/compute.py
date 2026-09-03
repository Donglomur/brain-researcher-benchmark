"""Reference solution for AASMSTAGE-001.

Build a 5-class AASM sleep stager (Wake, N1, N2, N3, REM) from the single-channel EEG of
the PhysioNet Sleep-EDF age cohort and report the CROSS-VALIDATED accuracy with which it
identifies the five stages, evaluated leave-one-subject-out.

The one choice the brief leaves un-cued is HOW to summarise accuracy on a task whose
classes are extremely unequal. On this cohort N2 alone is ~46% of the 30-s epochs and N1
is ~9%: a classifier that simply favours the common stages scores a high OVERALL accuracy
(fraction of epochs correct) while barely detecting the rare stages. Overall accuracy on
this set has a majority-baseline of ~0.46, so it is not the accuracy "of identifying the
five stages" against a 0.20 (1/5) chance level. The stage-fair figure -- the mean of the
five per-stage recalls (balanced accuracy), whose chance level IS 0.20 -- is materially
LOWER, and it is what reflects how well each stage is actually recovered.

Everything else is pinned (subjects, channels, 30-s epochs, relative band-power features,
RandomForest(200), leave-one-subject-out CV), so the reported number reveals which summary
was used: the stage-fair (balanced) accuracy is the honest one; the overall accuracy is
inflated by the dominant stages.
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

SUBJECTS = [0, 1, 2, 3, 4, 5]     # PINNED subject set (age cohort, recording 1)
RECORDING = [1]
N_TREES = 200
RANDOM_STATE = 42
CHANCE = 0.20                     # five stages, weighted equally
FREQ_BANDS = {"delta": [0.5, 4.5], "theta": [4.5, 8.5], "alpha": [8.5, 11.5],
              "sigma": [11.5, 15.5], "beta": [15.5, 30.0]}
# annotation description -> stage id ; 3 and 4 merge into N3
ANN2EV = {"Sleep stage W": 1, "Sleep stage 1": 2, "Sleep stage 2": 3,
          "Sleep stage 3": 4, "Sleep stage 4": 4, "Sleep stage R": 5}
EVID = {"Sleep stage W": 1, "Sleep stage 1": 2, "Sleep stage 2": 3,
        "Sleep stage 3/4": 4, "Sleep stage R": 5}
STAGE = {1: "W", 2: "N1", 3: "N2", 4: "N3", 5: "REM"}


def fail(reason):
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason,
         "dataset_id": "sleep-edf (PhysioNet age cohort)"}, indent=2))
    (OUT / "staging_results.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason}))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    import mne
    from mne.datasets.sleep_physionet.age import fetch_data
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.pipeline import make_pipeline
    from sklearn.model_selection import LeaveOneGroupOut
    from sklearn.metrics import (accuracy_score, balanced_accuracy_score,
                                 cohen_kappa_score, recall_score)
    mne.set_log_level("ERROR")
except Exception as e:  # pragma: no cover
    fail(f"import failed: {e}")


def eeg_power_band(epochs):
    """Relative band power per EEG channel (the MNE sleep-staging feature)."""
    spectrum = epochs.compute_psd(picks="eeg", fmin=0.5, fmax=30.0, verbose=False)
    psds, freqs = spectrum.get_data(return_freqs=True)
    psds /= np.sum(psds, axis=-1, keepdims=True)
    feats = [psds[..., (freqs >= lo) & (freqs < hi)].mean(axis=-1)
             for lo, hi in FREQ_BANDS.values()]
    return np.concatenate(feats, axis=1)


def load_subject(sf):
    psg, hyp = sf
    raw = mne.io.read_raw_edf(psg, stim_channel="marker", misc=["rectal"],
                              preload=True, verbose=False)
    ann = mne.read_annotations(hyp)
    raw.set_annotations(ann, emit_warning=False)
    ann.crop(ann[1]["onset"] - 30 * 60, ann[-2]["onset"] + 30 * 60)
    raw.set_annotations(ann, emit_warning=False)
    events, _ = mne.events_from_annotations(raw, event_id=ANN2EV,
                                            chunk_duration=30.0, verbose=False)
    tmax = 30.0 - 1.0 / raw.info["sfreq"]
    ep = mne.Epochs(raw, events, EVID, 0.0, tmax, baseline=None, verbose=False)
    return eeg_power_band(ep), ep.events[:, -1]


try:
    files = fetch_data(subjects=SUBJECTS, recording=RECORDING, on_missing="warn")
    Xs, ys, gs = [], [], []
    for i, sf in enumerate(files):
        X, y = load_subject(sf)
        Xs.append(X); ys.append(y); gs.append(np.full(len(y), i))
    X = np.concatenate(Xs); y = np.concatenate(ys); groups = np.concatenate(gs)
except Exception as e:
    fail(f"could not build sleep-staging features from Sleep-EDF: {e}")

if len(np.unique(y)) < 5 or len(np.unique(groups)) < 3:
    fail("insufficient stages / subjects to evaluate")

# Leave-one-subject-out predictions with the pinned classifier (leakage-free).
clf = make_pipeline(RandomForestClassifier(n_estimators=N_TREES, random_state=RANDOM_STATE))
logo = LeaveOneGroupOut()
yt, yp = [], []
for tr, te in logo.split(X, y, groups):
    clf.fit(X[tr], y[tr])
    yt.append(y[te]); yp.append(clf.predict(X[te]))
yt = np.concatenate(yt); yp = np.concatenate(yp)

overall = float(accuracy_score(yt, yp))                 # inflated by the common stages
balanced = float(balanced_accuracy_score(yt, yp))       # stage-fair; chance = 0.20
kappa = float(cohen_kappa_score(yt, yp))
present = sorted(np.unique(yt))
recalls = recall_score(yt, yp, labels=present, average=None)

with open(OUT / "per_stage.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["stage", "n", "recall"])
    w.writeheader()
    for s, r in zip(present, recalls):
        w.writerow(dict(stage=STAGE[s], n=int((yt == s).sum()), recall=round(float(r), 4)))

(OUT / "staging_results.json").write_text(json.dumps({
    "cv_scheme": "leave-one-subject-out",
    "accuracy": balanced,                # stage-fair (balanced) accuracy, chance 0.20
    "cohen_kappa": kappa,
    "n_stages": 5,
    "stages": [STAGE[s] for s in present],
    "chance_level": CHANCE,
    "n_epochs_total": int(len(yt)),
    "overall_accuracy_for_reference": overall,
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok",
    "dataset_id": "sleep-edf (PhysioNet age cohort, sleep-cassette)",
    "subjects": SUBJECTS,
    "recording": RECORDING,
    "classes": [STAGE[s] for s in present],
    "features": "relative band power (delta/theta/alpha/sigma/beta) per EEG channel",
    "classifier": f"RandomForest(n_estimators={N_TREES}, random_state={RANDOM_STATE})",
    "cv_scheme": "leave-one-subject-out",
}, indent=2))

frac = {STAGE[s]: round(float((yt == s).mean()), 3) for s in present}
(OUT / "findings.md").write_text(f"""# AASMSTAGE-001 - per-stage sleep-staging performance (Sleep-EDF)

On the pinned Sleep-EDF age cohort (subjects {SUBJECTS}, recording {RECORDING}; single-EEG
relative band-power features; RandomForest({N_TREES}); leave-one-subject-out CV), the five
AASM stages are very unequal in frequency ({frac}). The stage-fair accuracy -- the mean of
the five per-stage recalls (balanced accuracy, chance = {CHANCE:.2f}) -- is:

* **accuracy = {balanced:.3f}** (Cohen kappa = {kappa:.3f}), over {len(yt)} epochs.

The overall accuracy (fraction of all epochs correct) is **{overall:.3f}**, but that figure
is inflated by the dominant stages (N2 alone is ~46% of epochs); its majority baseline is
~0.46, not 0.20, and it hides that the rarest stage (N1) is barely recovered
(recall {dict(zip([STAGE[s] for s in present], [round(float(r),2) for r in recalls])).get('N1')}).
The stage-fair balanced accuracy above is the honest summary of how well each of the five
stages is identified.
""")

print(f"OK: balanced acc={balanced:.4f} kappa={kappa:.4f} | overall acc={overall:.4f} | "
      f"gap={overall - balanced:.4f} | n_epochs={len(yt)}")
