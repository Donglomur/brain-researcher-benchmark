"""Build the packaged PSD bundle for RESTALPHA-001 (route b: offline).

Precomputes, from the EEGBCI baseline runs (PhysioNet EEG Motor Movement/Imagery, via MNE), the
per-channel resting power spectral density for the two baseline states, so the shipped task needs
no network:

    run 1 = eyes-OPEN baseline   -> psd_eo
    run 2 = eyes-CLOSED baseline -> psd_ec

The agent still receives the full frequency-resolved, per-channel PSD, so it can select channels,
average, and (the scientifically central step) PARAMETERIZE the spectrum into aperiodic 1/f +
periodic peaks (FOOOF / specparam) to separate the oscillation from the broadband background.

PSD: MNE Welch, 2-second windows (n_per_seg = n_fft = 2*sfreq, 50% overlap), 1-45 Hz, linear power
(V^2/Hz). Subjects 1-20, standardized to the 10-20 montage, EEG channels only.

Run once (needs internet the first time to fetch/caches under ~/mne_data):
    python3 RESTALPHA-001/data/build_psd_bundle.py
"""
import warnings
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")
import mne
from mne.datasets import eegbci
from mne.io import read_raw_edf

mne.set_log_level("ERROR")

SUBJECTS = range(1, 21)
EO_RUN, EC_RUN = 1, 2          # EEGMMIDB baseline: R01 = eyes-open, R02 = eyes-closed
FMIN, FMAX = 1.0, 45.0
OUT = Path(__file__).resolve().parent / "eegbci_psd.npz"

psd_eo, psd_ec = [], []
freqs = ch_names = None
sfreq = None
kept = []
for sub in SUBJECTS:
    fns = eegbci.load_data(sub, [EO_RUN, EC_RUN], update_path=False)
    per_run = {}
    for run, fn in zip((EO_RUN, EC_RUN), fns):
        raw = read_raw_edf(fn, preload=True)
        eegbci.standardize(raw)                      # -> standard 10-20 channel names
        raw.set_montage("standard_1005", on_missing="ignore")
        raw.pick("eeg")
        n_per = int(round(2 * raw.info["sfreq"]))    # 2-second Welch windows
        spec = raw.compute_psd(method="welch", fmin=FMIN, fmax=FMAX,
                               n_fft=n_per, n_per_seg=n_per, n_overlap=n_per // 2, verbose=False)
        per_run[run] = spec.get_data().astype(np.float32)   # (n_ch, n_freq), linear power
        if freqs is None:
            freqs = spec.freqs.astype(np.float64)
            ch_names = list(spec.ch_names)
            sfreq = float(raw.info["sfreq"])
    if per_run[EO_RUN].shape == per_run[EC_RUN].shape:
        psd_eo.append(per_run[EO_RUN])
        psd_ec.append(per_run[EC_RUN])
        kept.append(sub)

psd_eo = np.asarray(psd_eo, np.float32)   # (n_subj, n_ch, n_freq)
psd_ec = np.asarray(psd_ec, np.float32)

np.savez_compressed(
    OUT,
    psd_eo=psd_eo, psd_ec=psd_ec, freqs=freqs,
    ch_names=np.array(ch_names), subjects=np.array(kept, int),
    sfreq=np.array(sfreq), band_hz=np.array([8, 12]),
    states=np.array(["eyes_open (run 1)", "eyes_closed (run 2)"]),
    psd_method=np.array("welch 2s windows 50% overlap, linear power V^2/Hz"),
)
print(f"saved {OUT.name}: psd_eo={psd_eo.shape} psd_ec={psd_ec.shape} "
      f"freqs[{freqs[0]:.1f}-{freqs[-1]:.1f} Hz] n_ch={len(ch_names)} n_subj={len(kept)} "
      f"({OUT.stat().st_size/1e6:.2f} MB)")
