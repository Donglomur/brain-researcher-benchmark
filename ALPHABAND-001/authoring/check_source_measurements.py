"""Independent SciPy Welch recomputation on actual staged EDFs, not reference copies.

Run in the task image with --data-dir and --reference. The EDF reader is shared
with the oracle, but PSD and aggregation do not call the oracle or MNE's PSD API.
"""
import argparse
import hashlib
import json
from pathlib import Path

import mne
import numpy as np
from scipy.signal import welch


def check(data_dir, reference_path):
    manifest = json.loads((data_dir / "data_manifest.json").read_text())
    reference = np.load(reference_path, allow_pickle=False)
    rows = []
    for subject in range(1, 6):
        measurements = {}
        for run in (1, 2):
            relative_path = f"S{subject:03d}/S{subject:03d}R{run:02d}.edf"
            path = data_dir / relative_path
            assert hashlib.sha256(path.read_bytes()).hexdigest() == manifest["files"][relative_path]
            raw = mne.io.read_raw_edf(path, preload=True, verbose=False)
            assert raw.info["sfreq"] == 160
            assert len(raw.ch_names) == 64
            values = raw.get_data()
            values -= values.mean(axis=0, keepdims=True)
            names = [name.rstrip(".").upper() for name in raw.ch_names]
            picks = [names.index(name) for name in ("O1", "OZ", "O2")]
            frequencies, densities = welch(values, fs=160, window="hamming", nperseg=320,
                                           noverlap=0, nfft=320, detrend="constant",
                                           scaling="density", average="mean", axis=-1)
            band = (frequencies >= 8) & (frequencies <= 13)
            measurements[run] = (float(densities[picks][:, band].mean()),
                                 float(densities[:, band].mean()))
        eo, eo_whole = measurements[1]
        ec, ec_whole = measurements[2]
        index = subject - 1
        for key, value in (("ec", ec), ("eo", eo), ("ratio", ec / eo)):
            assert np.isclose(value, reference["ref_" + key][index], rtol=1e-10, atol=0), (subject, key, value)
        rows.append(dict(subject=subject, ec=ec, eo=eo, ratio=ec / eo,
                         wholehead_ratio=ec_whole / eo_whole))
    for key, values in (("occ_mean", [row["ratio"] for row in rows]),
                        ("wholehead_mean", [row["wholehead_ratio"] for row in rows])):
        assert np.isclose(np.mean(values), reference[key], rtol=1e-10, atol=0)
    print(json.dumps({"status": "passed", "implementation": "scipy.signal.welch; MNE EDF reader",
                      "rows": rows, "occ_mean": float(np.mean([row["ratio"] for row in rows])),
                      "wholehead_mean": float(np.mean([row["wholehead_ratio"] for row in rows]))}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("/app/data/eegmmidb"))
    parser.add_argument("--reference", type=Path, required=True)
    args = parser.parse_args()
    check(args.data_dir, args.reference)
