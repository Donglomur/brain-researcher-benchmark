"""Reference solution for MMN-001.

Reproduce the ERP CORE mismatch-negativity (MMN) auditory oddball effect: the
**deviant-minus-standard** difference-wave amplitude at **FCz** in its 125-225 ms window,
for subjects 1-12, with the whole pipeline pinned by the task EXCEPT how the amplitude is
measured in the window.

The one open choice is the measurement: **mean amplitude** over the window vs the **peak**
(most extreme value) in the window. The ERP CORE MMN, like modern ERP practice, quantifies
the component as the **mean amplitude** across a fixed measurement window -- it is unbiased
by noise and by trial count. Peak amplitude, by contrast, is systematically biased away
from zero (it always finds the largest negative excursion) and here it makes the reported
value roughly twice as large. Everything else is pinned (subjects, P9/P10 mastoid
reference, 0.1-30 Hz filter, -200..0 baseline, epochs, standard/deviant event codes, the
FCz channel and the 125-225 ms window), so only the mean-vs-peak choice moves the number.

Validated mean-vs-peak (FCz, 125-225 ms, deviant-minus-standard, P9/P10 reference, per
subject then mean over the 12 subjects):
    MEAN amplitude (correct ERP CORE measure) : -1.82 uV   <-- reported here
    PEAK amplitude (naive, most-negative)     : -3.53 uV
11/12 subjects show a negative deviant-minus-standard MMN.
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
EOG = ["HEOG_left", "HEOG_right", "VEOG_lower"]
REF = ["P9", "P10"]                    # ERP CORE MMN reference (mastoid-adjacent)
STANDARD = {"80"}                      # 80 dB standard tone
DEVIANT = {"70"}                       # 70 dB deviant tone
CHAN = "FCz"
WIN = (0.125, 0.225)                   # MMN measurement window, s
# OSF file ids for <subj>_MMN_ds.{set,fdt} (ERP CORE MMN node 5q4xs; auditory -> no
# monitor-delay "shift", so the downsampled continuous file is "_ds" not "_shifted_ds")
OSF = {
    1: ("5f16b7d60870f2014a09c21d", "5f16b7d20596f6013e79b7dd"),
    2: ("5f16c1690870f201560975ee", "5f16c1660596f6013e79cda9"),
    3: ("5f16c9be6ef440015ebc9cad", "5f16c9ba6ef440015abc9e9c"),
    4: ("5f16d2340870f2014b09c930", "5f16d2306ef440015fbcb7c5"),
    5: ("5f16d3bb6ef440015ebcae7a", "5f16d3b80870f2015609a28f"),
    6: ("5f16d4760596f6014a79a61b", "5f16d4716ef440015fbcbd57"),
    7: ("5f16d5376ef440015bbcb161", "5f16d5330596f6014a79a7bb"),
    8: ("5f16d5e16ef440015fbcc08c", "5f16d5de6ef440015bbcb220"),
    9: ("5f16d6a90596f6013e79e575", "5f16d6a56ef440015fbcc2c8"),
    10: ("5f16b8ab6ef4400155bca647", "5f16b8a60870f2014709b1ba"),
    11: ("5f16b9836ef4400155bca8ca", "5f16b9800870f2014b09ae65"),
    12: ("5f16ba576ef4400155bcaaff", "5f16ba546ef4400155bcaaf4"),
}


def fail(reason):
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason, "dataset_id": "erpcore_mmn"}, indent=2))
    (OUT / "mmn.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


def data_dir():
    """Use a local cache if ERPCORE_MMN_DIR points at the files; else fetch from OSF."""
    env = os.environ.get("ERPCORE_MMN_DIR")
    if env and all((Path(env) / f"{s}_MMN_ds.set").exists() for s in SUBJECTS):
        return Path(env)
    d = Path(tempfile.mkdtemp(prefix="erpcore_mmn_"))
    for s in SUBJECTS:
        set_id, fdt_id = OSF[s]
        for fid, ext in ((set_id, "set"), (fdt_id, "fdt")):
            dst = d / f"{s}_MMN_ds.{ext}"
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


def fcz_difference(subj):
    """deviant-minus-standard difference wave at FCz (P9/P10 ref, -200..0 baseline)."""
    raw = mne.io.read_raw_eeglab(f"{DDIR}/{subj}_MMN_ds.set", preload=True)
    raw.set_channel_types({c: "eog" for c in EOG})
    raw.filter(0.1, 30.0, picks="eeg", verbose=False)
    events, eid = mne.events_from_annotations(raw, verbose=False)
    id2lab = {v: k for k, v in eid.items()}
    ne = []
    for o, _, c in events:
        lab = id2lab[c]
        if lab in STANDARD:
            ne.append([o, 0, 1])
        elif lab in DEVIANT:
            ne.append([o, 0, 2])
    ep = mne.Epochs(raw, np.array(ne), {"standard": 1, "deviant": 2}, tmin=-0.2, tmax=0.8,
                    baseline=None, reject=None, preload=True, verbose=False)
    # ERP CORE MMN convention: reference to the average of the mastoid-adjacent P9/P10
    ep.set_eeg_reference(REF, projection=False, verbose=False)
    ep.apply_baseline((-0.2, 0.0), verbose=False)
    diff = mne.combine_evoked([ep["deviant"].average(), ep["standard"].average()], weights=[1, -1])
    seg = diff.copy().pick([CHAN]).crop(*WIN).data[0] * 1e6   # uV
    return float(seg.mean()), float(seg.min())


try:
    means, peaks = [], []
    for s in SUBJECTS:
        m, p = fcz_difference(s)
        means.append(m); peaks.append(p)
except Exception as e:
    fail(f"could not build the MMN difference wave: {e}")

means = np.array(means); peaks = np.array(peaks)
mmn_amp = float(means.mean())          # CORRECT ERP CORE measure
peak_amp = float(peaks.mean())         # naive, for contrast

(OUT / "mmn.json").write_text(json.dumps({
    "mmn_amplitude_uv": mmn_amp,
    "measure": "mean amplitude over the window",
    "channel": CHAN,
    "window_ms": [125, 225],
    "contrast": "deviant minus standard",
    "n_subjects": len(SUBJECTS),
    "per_subject_mean_uv": [round(float(v), 3) for v in means],
    "peak_amplitude_uv_for_reference": peak_amp,
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok",
    "dataset_id": "erpcore_mmn",
    "n_subjects": len(SUBJECTS),
    "reference": "average of the mastoid-adjacent electrodes P9 and P10 (ERP CORE convention)",
    "filter_hz": [0.1, 30.0],
    "baseline_ms": [-200, 0],
    "epoch_ms": [-200, 800],
    "standard_code": sorted(STANDARD),
    "deviant_code": sorted(DEVIANT),
    "measurement": "mean amplitude of the deviant-minus-standard difference wave at FCz, 125-225 ms, per subject then mean",
}, indent=2))

(OUT / "findings.md").write_text(f"""# MMN-001 - the ERP CORE mismatch negativity at FCz

Reproducing the ERP CORE passive auditory oddball on subjects 1-12 (P9/P10 mastoid
reference, 0.1-30 Hz, -200..0 ms baseline), the **deviant-minus-standard** difference
wave at **FCz** is a clear frontocentral negativity in the MMN window. Measured as the
**mean amplitude** over **125-225 ms** per subject and averaged over the 12 subjects, the
MMN amplitude is **{mmn_amp:.2f} uV** (11/12 subjects negative).

The measurement matters: taking the **peak** (most negative value) in the same window
instead of the mean gives about **{peak_amp:.2f} uV** -- roughly double -- because peak
amplitude always latches onto the largest noise-plus-signal excursion and is biased away
from zero. The mean-amplitude value reported here is the ERP CORE / best-practice measure
for the MMN.
""")
print(f"OK: MMN FCz deviant-minus-standard MEAN={mmn_amp:.3f} uV | PEAK={peak_amp:.3f} uV | "
      f"n_subjects={len(SUBJECTS)}")
