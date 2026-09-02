"""Reference solution for FACEERP-001.

Reproduce the ERP CORE N170 face effect: the face-minus-car difference-wave peak
amplitude at PO8, for subjects 1-12, with the whole pipeline pinned by the task EXCEPT
the montage reference.

The one open choice is the reference. The ERP CORE N170 dataset being reproduced is
referenced to the **average of the scalp electrodes** (Kappenman et al. 2021: "re-
reference the data to the average of all EEG sites"). The average reference preserves the
occipito-temporal N170 as a genuine negativity at PO8. A linked-mastoid reference (P9/P10)
sits right next to the N170 generators and roughly halves the measured amplitude (and
inverts the absolute face N170), so it gives a materially different, smaller number.

Validated peak amplitudes (110-150 ms, PO8, per-subject peak then mean over 12 subjects):
    average reference (correct ERP CORE convention) : -6.17 uV   <-- reported here
    P9/P10 linked-mastoid reference (naive)          : -3.15 uV
12/12 subjects show the same direction; paired t = -6.6, p = 4e-5.
"""
import json
import os
import sys
import tempfile
import urllib.request
import warnings
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)

SUBJECTS = list(range(1, 13))
FACE, CAR = range(1, 41), range(41, 81)
EOG = ["HEOG_left", "HEOG_right", "VEOG_lower"]
WIN = (0.110, 0.150)
# OSF file ids for <subj>_N170_shifted_ds.{set,fdt} (ERP CORE N170 node pfde9)
OSF = {
    1: ("5f161eb00596f601227a0103", "5f161ead0870f201320984de"),
    2: ("5f16272b0870f20133098a1a", "5f1627280596f6012179e75a"),
    3: ("5f1630c20596f6012179f5cb", "5f1630bc0596f6012179f5bc"),
    4: ("5f163c3a0596f6011d7a0609", "5f163c350870f2011709d6d2"),
    5: ("5f163e7d0870f2013309b91b", "5f163e790596f601217a11d3"),
    6: ("5f163fa16ef4400137bcf3da", "5f163f9d6ef4400137bcf3cc"),
    7: ("5f1640c50870f2013209dd22", "5f1640c00596f6011d7a0ef1"),
    8: ("5f1641f80870f2012709f785", "5f1641f20596f6011d7a1160"),
    9: ("5f16432d0596f6012c7997cd", "5f1643290870f2013309c548"),
    10: ("5f161f840596f601227a026b", "5f161f820596f6011d79dd0f"),
    11: ("5f1620590596f6011979d25b", "5f1620546ef4400130bd131b"),
    12: ("5f16211b6ef440012fbce9c8", "5f1621180596f6012179e0a0"),
}


def fail(reason):
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason, "dataset_id": "erpcore_n170"}, indent=2))
    (OUT / "n170.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


def data_dir():
    """Use a local cache if ERPCORE_N170_DIR points at the files; else fetch from OSF."""
    env = os.environ.get("ERPCORE_N170_DIR")
    if env and all((Path(env) / f"{s}_N170_shifted_ds.set").exists() for s in SUBJECTS):
        return Path(env)
    d = Path(tempfile.mkdtemp(prefix="erpcore_n170_"))
    for s in SUBJECTS:
        set_id, fdt_id = OSF[s]
        for fid, ext in ((set_id, "set"), (fdt_id, "fdt")):
            dst = d / f"{s}_N170_shifted_ds.{ext}"
            try:
                urllib.request.urlretrieve(f"https://osf.io/download/{fid}/", dst)
            except Exception as e:
                fail(f"OSF download failed for subject {s} .{ext}: {e}")
    return d


try:
    import mne
    mne.set_log_level("ERROR")
except Exception as e:  # pragma: no cover
    fail(f"mne import failed: {e}")

DDIR = data_dir()


def peak_amp(subj, ref):
    raw = mne.io.read_raw_eeglab(f"{DDIR}/{subj}_N170_shifted_ds.set", preload=True)
    raw.set_channel_types({c: "eog" for c in EOG})
    raw.filter(0.1, 30.0, picks="eeg", verbose=False)
    events, eid = mne.events_from_annotations(raw, verbose=False)
    id2d = {v: int(k) for k, v in eid.items()}
    ne = [[o, 0, 1] if id2d[c] in FACE else [o, 0, 2]
          for o, _, c in events if id2d[c] in FACE or id2d[c] in CAR]
    ep = mne.Epochs(raw, np.array(ne), {"face": 1, "car": 2}, tmin=-0.2, tmax=0.4,
                    baseline=None, reject=None, preload=True, verbose=False)
    if ref == "average":
        ep.set_eeg_reference("average", projection=False, verbose=False)
    else:
        ep.set_eeg_reference(["P9", "P10"], verbose=False)
    ep.apply_baseline((-0.2, 0.0), verbose=False)
    ep.drop_bad(reject=dict(eeg=150e-6), verbose=False)
    diff = mne.combine_evoked([ep["face"].average(), ep["car"].average()], weights=[1, -1])
    d = diff.copy().pick(["PO8"]).crop(*WIN).data[0] * 1e6
    return float(d[int(np.argmin(d))])


# CORRECT reference for the ERP CORE N170 reproduction: average of the scalp electrodes.
peaks = np.array([peak_amp(s, "average") for s in SUBJECTS])
mean_peak = float(peaks.mean())

(OUT / "n170.json").write_text(json.dumps({
    "n170_peak_amplitude_uv": mean_peak,
    "channel": "PO8",
    "window_ms": [110, 150],
    "n_subjects": len(SUBJECTS),
    "per_subject_peak_uv": [round(float(p), 3) for p in peaks],
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok",
    "dataset_id": "erpcore_n170",
    "n_subjects": len(SUBJECTS),
    "reference": "average of the 30 scalp electrodes (ERP CORE N170 convention)",
    "filter_hz": [0.1, 30.0],
    "measurement": "per-subject peak (most negative) of face-minus-car diff wave at PO8, 110-150 ms, then mean",
}, indent=2))

(OUT / "findings.md").write_text(f"""# FACEERP-001 — the ERP CORE N170 face effect at PO8

Reproducing the ERP CORE N170 paradigm on subjects 1-12, I referenced the montage to the
**average of the scalp electrodes** — the reference used by the ERP CORE N170 dataset.
The face-minus-car difference wave at PO8 is a clear negativity in the N170 window; its
peak (most negative) amplitude in 110-150 ms, measured per subject and averaged over the
12 subjects, is **{mean_peak:.2f} uV**.

The reference matters: with a P9/P10 linked-mastoid reference (adjacent to the
occipito-temporal N170 generators) the same measurement is only about -3.2 uV, roughly
half the amplitude, because the mastoids are not electrically neutral for this component.
The average-reference value reported here is the one consistent with the ERP CORE
convention being reproduced.
""")
print(f"OK: N170 face-car peak PO8 (avg ref) = {mean_peak:.3f} uV over {len(SUBJECTS)} subjects")
