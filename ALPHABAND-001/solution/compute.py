"""Reference solution for ALPHABAND-001.

Assess the Berger effect on the PhysioNet EEGBCI dataset (subjects 1-5, run 1 eyes
open, run 2 eyes closed): occipital alpha (8-13 Hz) power is much larger with eyes
closed than eyes open. The headline is the mean across subjects of the per-subject
eyes-closed / eyes-open OCCIPITAL alpha power ratio.

The public instruction specifies channel standardization and the full PSD recipe.
Read checksum-verified EDFs staged in the image, never download at runtime.
This is a modern descriptive replication, not the original Berger analysis sample.
"""
import csv
import hashlib
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
DATA = Path(os.environ.get("EEGBCI_DATA_DIR", "/app/data/eegmmidb"))


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
    psd = r.compute_psd(method="welch", fmin=1.0, fmax=45.0, picks=picks,
                        n_fft=n_fft, n_per_seg=n_fft, n_overlap=0, window="hamming",
                        average="mean", remove_dc=True, reject_by_annotation=False)
    freqs = psd.freqs
    data = psd.get_data()  # (n_channels, n_freqs)
    band = (freqs >= BAND[0]) & (freqs <= BAND[1])
    return float(data[:, band].mean())


try:
    manifest = json.loads((DATA / "data_manifest.json").read_text())
    expected_files = {f"S{s:03d}/S{s:03d}R{run:02d}.edf"
                      for s in SUBJECTS for run in (1, 2)}
    if manifest["version"] != "1.0.0" or set(manifest["files"]) != expected_files:
        raise ValueError("wrong EEGMMIDB version or analysis sample")
    for relative_path, expected_hash in manifest["files"].items():
        if hashlib.sha256((DATA / relative_path).read_bytes()).hexdigest() != expected_hash:
            raise ValueError(f"checksum mismatch: {relative_path}")
    rows = []
    for s in SUBJECTS:
        raw_eo = mne.io.read_raw_edf(DATA / f"S{s:03d}/S{s:03d}R01.edf", preload=True, verbose=False)
        raw_ec = mne.io.read_raw_edf(DATA / f"S{s:03d}/S{s:03d}R02.edf", preload=True, verbose=False)
        eo = band_alpha(raw_eo, OCCIPITAL)
        ec = band_alpha(raw_ec, OCCIPITAL)
        # All-EEG-channel ratio is a descriptive comparison, not the occipital estimand.
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
    "dataset_version": manifest["version"],
    "subjects": SUBJECTS,
    "runs": {"eyes_open": 1, "eyes_closed": 2},
    "band_hz": [BAND[0], BAND[1]],
    "psd_method": "Welch, n_fft = 2 s",
    "welch": {"segment_sec": 2, "n_fft": 320, "n_overlap": 0,
              "window": "hamming", "remove_dc": True, "average": "mean"},
    "power_units": "V^2/Hz",
    "reference": "common average",
    "channels": OCCIPITAL,
    "aggregation": "mean_of_subject_ratios",
}, indent=2))

(OUT / "findings.md").write_text(f"""# ALPHABAND-001 - the Berger effect

On the PhysioNet EEGBCI baseline recordings (subjects 1-5, run 1 eyes open, run 2 eyes
closed), **occipital** alpha-band (8-13 Hz) power is markedly larger with the eyes
closed than with the eyes open. Averaged over the {len(OCCIPITAL)} occipital electrodes
({", ".join(OCCIPITAL)}) with a common-average reference, the mean eyes-closed /
eyes-open occipital alpha power ratio is **{mean_ratio:.2f}** (per-subject:
{", ".join(f"{r['ratio']:.1f}" for r in rows)}). Per-subject occipital alpha power and
ratios are in `per_subject.csv`.

This small modern sample shows the direction associated with the historical Berger
effect; it is not a numerical reproduction of Berger's original cohort. The whole-head
mean ratio is {wholehead_mean:.2f}, showing that the spatial averaging choice changes
the summary. The runs have fixed order (EO then EC), so this descriptive contrast
does not isolate eye closure from order effects or establish a population-wide effect.
""")

print(f"OK: occipital EC/EO alpha ratio mean = {mean_ratio:.3f} "
      f"(per-subject {np.round(ratios, 2).tolist()}) | whole-head = {wholehead_mean:.3f}")
