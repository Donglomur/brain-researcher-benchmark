"""Build the packaged EEG bundle for ALPHACONN-001 (route b: offline).

Ships the single raw EDF the task needs (PhysioNet EEG Motor Movement/Imagery, subject 1,
run 6) so the container needs no network. The agent still reads the raw EEG and does the whole
analysis (standardise montage -> average reference -> band-pass -> cross-spectral density ->
alpha-band coherence), so nothing that matters for the task is precomputed away — only the
download is removed.

Provenance (run once, with internet, to (re)generate data/S001R06.edf):

    import shutil
    from mne.datasets import eegbci
    fns = eegbci.load_data(subject=1, runs=[6, 10, 14])   # fetches to ~/mne_data, then caches
    shutil.copy(fns[0], "ALPHACONN-001/data/S001R06.edf")      # fns[0] is run 6 (S001R06.edf)

The EDF (~2.6 MB) is the untouched PhysioNet file; sfreq 160 Hz, 64 EEG channels, ~125 s.
"""
import shutil

from mne.datasets import eegbci

fns = eegbci.load_data(subject=1, runs=[6, 10, 14])
shutil.copy(fns[0], "ALPHACONN-001/data/S001R06.edf")
print(f"saved data/S001R06.edf from {fns[0]}")
