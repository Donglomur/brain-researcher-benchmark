"""Reference solution for ALPHABAND-001.

Reproduce the Berger effect on the PhysioNet EEGBCI dataset (subjects 1-5, run 1 eyes
open, run 2 eyes closed): occipital alpha (8-13 Hz) power is much larger with eyes
closed than eyes open. The headline is the mean across subjects of the per-subject
eyes-closed / eyes-open OCCIPITAL alpha power ratio.

The one choice the brief leaves un-cued is channel handling. The raw EDF channel labels
in this dataset are non-standard ("O1..", "Oz..", "O2.." with trailing dots and Fc/Cp
style casing), so a direct pick of the occipital electrodes silently misses them and a
careless pipeline falls back to a whole-head average, which dilutes the strongly
occipital effect. The honest reference standardizes the channel names and sets the
10-05 montage FIRST, then measures alpha over the occipital electrodes.

Validated (mne 1.12.1, subjects 1-5, band 8-13 Hz, common-average reference, Welch
n_fft = 2 s): occipital ratio mean = 19.64 (per-subject 16.5, 8.0, 24.3, 48.0, 1.3).
A whole-head average gives ~4.4 -- the trap this task is built on.

Proof-of-work deliverable: a PER-SUBJECT table (per_subject.csv) with each subject's
eyes-closed and eyes-open OCCIPITAL alpha power and their ratio. The headline is the
mean of the per-subject occipital ratios; the whole-head ratio (~4.4) is computed only
for contrast (the discriminating quantity a whole-head pipeline would report instead).
"""
import csv
import json
import os
import sys
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)

SUBJECTS = [1, 2, 3, 4, 5]
OCCIPITAL = ["O1", "O2", "Oz"]
BAND = (8.0, 13.0)


def fail(reason):
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason,
         "dataset_id": "eegbci (PhysioNet EEG Motor Movement/Imagery)"}, indent=2))
    (OUT / "alpha_ratio.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason}))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    import mne
    from mne.datasets import eegbci
    mne.set_log_level("ERROR")
except Exception as e:  # pragma: no cover
    fail(f"mne import failed: {e}")


def band_alpha(raw, picks):
    """Common-average referenced alpha (8-13 Hz) power, Welch 2-s segments, over `picks`."""
    r = raw.copy()
    eegbci.standardize(r)  # strip the trailing dots / fix casing on the channel labels
    r.set_montage(mne.channels.make_standard_montage("standard_1005"))
    r.set_eeg_reference("average", projection=False)
    n_fft = int(round(r.info["sfreq"] * 2.0))
    psd = r.compute_psd(method="welch", fmin=1.0, fmax=45.0, picks=picks, n_fft=n_fft)
    freqs = psd.freqs
    data = psd.get_data()  # (n_channels, n_freqs)
    band = (freqs >= BAND[0]) & (freqs <= BAND[1])
    return float(data[:, band].mean())


try:
    rows = []
    for s in SUBJECTS:
        fnames = eegbci.load_data(subjects=[s], runs=[1, 2], update_path=True)
        raw_eo = mne.io.read_raw_edf(fnames[0], preload=True, verbose=False)  # run 1 eyes open
        raw_ec = mne.io.read_raw_edf(fnames[1], preload=True, verbose=False)  # run 2 eyes closed
        eo = band_alpha(raw_eo, OCCIPITAL)
        ec = band_alpha(raw_ec, OCCIPITAL)
        # whole-head (all EEG channels) alpha -- the un-cued dilution trap, for contrast
        eo_wh = band_alpha(raw_eo, "eeg")
        ec_wh = band_alpha(raw_ec, "eeg")
        rows.append(dict(subject=s, ec_occipital_alpha=ec, eo_occipital_alpha=eo,
                         ratio=ec / eo, wholehead_ratio=ec_wh / eo_wh))
except Exception as e:
    fail(f"could not process EEGBCI recordings: {e}")

if len(rows) < 5:
    fail(f"only processed {len(rows)} of 5 subjects")

ratios = np.array([r["ratio"] for r in rows])
mean_ratio = float(ratios.mean())
wholehead_mean = float(np.mean([r["wholehead_ratio"] for r in rows]))

with open(OUT / "per_subject.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["subject", "ec_occipital_alpha",
                                      "eo_occipital_alpha", "ratio"])
    w.writeheader()
    for r in rows:
        w.writerow({k: r[k] for k in ["subject", "ec_occipital_alpha",
                                      "eo_occipital_alpha", "ratio"]})

(OUT / "alpha_ratio.json").write_text(json.dumps({
    "occipital_alpha_ratio_ec_over_eo": mean_ratio,
    "band_hz": [BAND[0], BAND[1]],
    "n_subjects": len(rows),
    "channels": OCCIPITAL,
    "per_subject_ratio": {str(r["subject"]): r["ratio"] for r in rows},
    "wholehead_alpha_ratio_for_reference": wholehead_mean,
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok",
    "dataset_id": "eegbci (PhysioNet EEG Motor Movement/Imagery)",
    "subjects": SUBJECTS,
    "runs": {"eyes_open": 1, "eyes_closed": 2},
    "band_hz": [BAND[0], BAND[1]],
    "psd_method": "Welch, n_fft = 2 s",
    "reference": "common average",
    "channels": OCCIPITAL,
    "aggregation": "mean across subjects of per-subject EC/EO occipital alpha power ratio",
}, indent=2))

(OUT / "findings.md").write_text(f"""# ALPHABAND-001 - the Berger effect

On the PhysioNet EEGBCI baseline recordings (subjects 1-5, run 1 eyes open, run 2 eyes
closed), **occipital** alpha-band (8-13 Hz) power is markedly larger with the eyes
closed than with the eyes open. Averaged over the {len(OCCIPITAL)} occipital electrodes
({", ".join(OCCIPITAL)}) with a common-average reference, the mean eyes-closed /
eyes-open occipital alpha power ratio is **{mean_ratio:.2f}** (per-subject:
{", ".join(f"{r['ratio']:.1f}" for r in rows)}). Per-subject occipital alpha power and
ratios are in `per_subject.csv`.

This reproduces Berger's classic result: eyes closure produces a large increase in
posterior alpha power. The effect is specifically occipital; averaging over the whole
head dilutes it to a ratio of ~{wholehead_mean:.1f}, so the ratio must be measured over
the occipital electrodes.
""")

print(f"OK: occipital EC/EO alpha ratio mean = {mean_ratio:.3f} "
      f"(per-subject {np.round(ratios, 2).tolist()}) | whole-head = {wholehead_mean:.3f}")
