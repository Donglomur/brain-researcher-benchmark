FROM ubuntu:24.04
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      ca-certificates python3 python3-venv python3-pip curl && \
    python3 -m pip install --break-system-packages --no-cache-dir \
      numpy==2.1.3 scipy==1.14.1 pooch==1.8.2 scikit-learn==1.5.2 mne==1.12.1 && \
    rm -rf /var/lib/apt/lists/*
# Build the analysis bundle at IMAGE-BUILD time (internet available here). It is written into the
# image so the agent runs fully OFFLINE (task.toml allow_internet=false); no derived data is committed
# to the repo. Source: PhysioNet EEG Motor Movement/Imagery database (eegbci), left- vs right-fist
# motor-imagery runs 4/8/12 for subjects 1-9, fetched via mne.datasets.eegbci.load_data and
# re-packaged (montage-standardized, 7-30 Hz band-pass, resampled to 80 Hz, epoched 0.5-3.5 s, with
# the REAL run/trial provenance carried per trial). Reproduces data/build_epochs.py exactly.
RUN mkdir -p /opt/bundle && python3 - <<'PY'
import warnings
import numpy as np
warnings.filterwarnings("ignore")
import mne
from mne.datasets import eegbci
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

out = "/opt/bundle/eegbci_epochs.npz"
np.savez_compressed(
    out, X=X, y=y, subject=subject, run=run, trial=trial,
    ch_names=np.array(ch_names), sfreq=np.float32(SFREQ),
    tmin=np.float32(TMIN), tmax=np.float32(TMAX),
    label_names=np.array(["left_fist", "right_fist"]),
    runs=np.array(RUNS, np.int16), bandpass=np.array([7.0, 30.0], np.float32),
)
print(f"built {out}: X={X.shape} y(0=left/1=right)={np.bincount(y)} "
      f"subjects={np.unique(subject)} runs={np.unique(run)} n_trials={len(trial)}")
PY
ENV BUNDLE_DIR=/opt/bundle
WORKDIR /app
