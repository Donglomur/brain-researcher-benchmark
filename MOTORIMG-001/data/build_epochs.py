"""Build the packaged EEGBCI motor-imagery epoch bundle (route b: offline).

Precomputes the band-passed, epoched left-vs-right fist motor-imagery trials from the PhysioNet
EEG Motor Movement/Imagery database (eegbci) so the shipped task needs no network. Crucially, the
bundle carries the REAL run/trial provenance from the eegbci recording structure — each subject was
recorded in three separate runs (4/8/12), and every trial keeps the run it came from and a unique
trial id — so a solution can group the cross-validation by trial or by run (leave-one-run/trial-out)
rather than fabricating pseudo-runs from an index. The agent still does the windowing, the CSP+LDA
fit, and the cross-validation; nothing needed for the grouped-CV check has been removed.

Preprocessing baked into the bundle (the standard, method-specified choices):
  - concatenate the three motor-imagery runs' left/right-fist trials (T1 = left fist, T2 = right)
  - standardize the 10-05 montage (eegbci.standardize)
  - band-pass 7-30 Hz (firwin)
  - resample 160 -> 80 Hz (Nyquist-safe given the 30 Hz low-pass; halves the bundle size)
  - epoch tmin=0.5 s .. tmax=3.5 s (a 3 s motor-imagery window), no baseline

Stored arrays (eegbci_epochs.npz):
  X          float32 (n_trials, 64, 241)  band-passed, epoched trials
  y          int8    (n_trials,)          0 = left fist, 1 = right fist
  subject    int16   (n_trials,)          subject id (1..9)
  run        int16   (n_trials,)          REAL run id the trial came from (4, 8 or 12)
  trial      int32   (n_trials,)          unique trial id (grouping unit for leave-one-trial-out)
  ch_names, sfreq, tmin, tmax, label_names, runs, bandpass  (metadata)
"""
import warnings

import numpy as np

warnings.filterwarnings("ignore")
import mne  # noqa: E402
from mne.datasets import eegbci  # noqa: E402

mne.set_log_level("ERROR")

SUBJECTS = list(range(1, 10))
RUNS = [4, 8, 12]        # left- vs right-fist motor imagery (three separate recordings)
SFREQ = 80.0
TMIN, TMAX = 0.5, 3.5

Xall, yall, sall, rall, tall = [], [], [], [], []
gid = 0
ch_names = None
for sub in SUBJECTS:
    for run in RUNS:
        fn = eegbci.load_data(sub, [run], update_path=True)[0]
        raw = mne.io.read_raw_edf(fn, preload=True, verbose=False)
        eegbci.standardize(raw)
        raw.filter(7.0, 30.0, fir_design="firwin", verbose=False)
        raw.resample(SFREQ, verbose=False)
        ev, _ = mne.events_from_annotations(raw)
        epo = mne.Epochs(raw, ev, dict(left=2, right=3), tmin=TMIN, tmax=TMAX,
                         baseline=None, preload=True, verbose=False)
        X = epo.get_data(copy=True).astype(np.float32)
        y = (epo.events[:, -1] == 3).astype(np.int8)   # 0 = left fist (T1), 1 = right fist (T2)
        n = len(y)
        ch_names = epo.ch_names
        Xall.append(X)
        yall.append(y)
        sall.append(np.full(n, sub, np.int16))
        rall.append(np.full(n, run, np.int16))
        tall.append(np.arange(gid, gid + n, dtype=np.int32))
        gid += n

X = np.concatenate(Xall)
y = np.concatenate(yall)
subject = np.concatenate(sall)
run = np.concatenate(rall)
trial = np.concatenate(tall)

out = "MOTORIMG-001/data/eegbci_epochs.npz"
np.savez_compressed(
    out, X=X, y=y, subject=subject, run=run, trial=trial,
    ch_names=np.array(ch_names), sfreq=np.float32(SFREQ),
    tmin=np.float32(TMIN), tmax=np.float32(TMAX),
    label_names=np.array(["left_fist", "right_fist"]),
    runs=np.array(RUNS, np.int16), bandpass=np.array([7.0, 30.0], np.float32),
)
print(f"saved {out}: X={X.shape} y(0=left/1=right)={np.bincount(y)} "
      f"subjects={np.unique(subject)} runs={np.unique(run)} n_trials={len(trial)}")
