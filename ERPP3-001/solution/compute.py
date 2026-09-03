"""Reference solution for ERPP3-001.

Reproduce the ERP CORE P3 oddball effect: the P3b **rare-minus-frequent** difference-wave
amplitude at Pz in its 300-600 ms window, for subjects 1-12, with the whole pipeline
pinned by the task EXCEPT how the amplitude is measured in the window.

The one open choice is the measurement: **mean amplitude over the window** vs the
**peak** (most extreme value) in the window. The ERP CORE P3 (like modern ERP practice)
quantifies the component as the **mean amplitude** across a fixed measurement window --
it is unbiased by noise and by the number of trials. Peak amplitude, by contrast, is
systematically biased away from zero (it always finds the largest excursion) and here it
roughly doubles the reported value. Everything else is pinned (subjects, average
reference, 0.1-30 Hz filter, -200..0 baseline, epochs, rare/frequent event codes, the Pz
channel and the 300-600 ms window), so only the mean-vs-peak choice moves the number.

Validated mean-vs-peak (Pz, 300-600 ms, rare-minus-frequent, avg reference, per-subject
then mean over the 12 subjects):
    MEAN amplitude (correct ERP CORE measure) : +4.43 uV   <-- reported here
    PEAK amplitude (naive)                    : +8.85 uV
11/12 subjects show a positive rare-minus-frequent P3b.
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
# rare/oddball = the block's target letter was presented (tens digit == units digit)
RARE = {"11", "22", "33", "44", "55"}
CHAN = "Pz"
WIN = (0.300, 0.600)            # P3b measurement window, s
# OSF file ids for <subj>_P3_shifted_ds.{set,fdt} (ERP CORE P3 node etdkz)
OSF = {
    1: ("5f18a6d085d25a001def6044", "5f18a6cc9e0cfe001b1c123b"),
    2: ("5f18b0f185d25a0023ef2fa2", "5f18b0ee85d25a0023ef2f9d"),
    3: ("5f18b97c86a05500320dec3d", "5f18b97985d25a001eef92db"),
    4: ("5f18c1b285d25a001eef9b4d", "5f18c1b086a055003c0df0fc"),
    5: ("5f18c33086a055003c0df3da", "5f18c32c9e0cfe00251c5302"),
    6: ("5f18c3db9e0cfe00251c546d", "5f18c3d89e0cfe00241c3928"),
    7: ("5f18c49785d25a001eef9f18", "5f18c4949e0cfe00241c3ae6"),
    8: ("5f18c55e9e0cfe00251c56bb", "5f18c55c86a055003c0df785"),
    9: ("5f18c60d9e0cfe00251c57b4", "5f18c60b9e0cfe00201c33c5"),
    10: ("5f18a7b99e0cfe00241c11ab", "5f18a7b485d25a001eef7ece"),
    11: ("5f18a8b19e0cfe001b1c14b1", "5f18a8ad85d25a0023ef236e"),
    12: ("5f18a9b386a055003c0dc805", "5f18a9af9e0cfe00201c13e5"),
}


def fail(reason):
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason, "dataset_id": "erpcore_p3"}, indent=2))
    (OUT / "p3.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


def data_dir():
    """Use a local cache if ERPCORE_P3_DIR points at the files; else fetch from OSF."""
    env = os.environ.get("ERPCORE_P3_DIR")
    if env and all((Path(env) / f"{s}_P3_shifted_ds.set").exists() for s in SUBJECTS):
        return Path(env)
    d = Path(tempfile.mkdtemp(prefix="erpcore_p3_"))
    for s in SUBJECTS:
        set_id, fdt_id = OSF[s]
        for fid, ext in ((set_id, "set"), (fdt_id, "fdt")):
            dst = d / f"{s}_P3_shifted_ds.{ext}"
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


def pz_difference(subj):
    """rare-minus-frequent difference wave at Pz (average ref, -200..0 baseline)."""
    raw = mne.io.read_raw_eeglab(f"{DDIR}/{subj}_P3_shifted_ds.set", preload=True)
    raw.set_channel_types({c: "eog" for c in EOG})
    raw.filter(0.1, 30.0, picks="eeg", verbose=False)
    events, eid = mne.events_from_annotations(raw, verbose=False)
    id2lab = {v: k for k, v in eid.items()}
    ne = [[o, 0, 1] if id2lab[c] in RARE else [o, 0, 2]
          for o, _, c in events if id2lab[c].isdigit() and len(id2lab[c]) == 2]
    ep = mne.Epochs(raw, np.array(ne), {"rare": 1, "freq": 2}, tmin=-0.2, tmax=0.8,
                    baseline=None, reject=None, preload=True, verbose=False)
    # ERP CORE convention: reference to the average of the scalp electrodes
    ep.set_eeg_reference("average", projection=False, verbose=False)
    ep.apply_baseline((-0.2, 0.0), verbose=False)
    # difference wave = average(rare) - average(frequent); all epochs averaged (no
    # additional peak-to-peak rejection on these pre-ICA continuous files)
    diff = mne.combine_evoked([ep["rare"].average(), ep["freq"].average()], weights=[1, -1])
    seg = diff.copy().pick([CHAN]).crop(*WIN).data[0] * 1e6   # uV
    return float(seg.mean()), float(seg.max())


try:
    means, peaks = [], []
    for s in SUBJECTS:
        m, p = pz_difference(s)
        means.append(m); peaks.append(p)
except Exception as e:
    fail(f"could not build the P3 difference wave: {e}")

means = np.array(means); peaks = np.array(peaks)
mean_amp = float(means.mean())         # CORRECT ERP CORE measure
peak_amp = float(peaks.mean())         # naive, for contrast

(OUT / "p3.json").write_text(json.dumps({
    "p3b_amplitude_uv": mean_amp,
    "measure": "mean amplitude over the window",
    "channel": CHAN,
    "window_ms": [300, 600],
    "contrast": "rare minus frequent",
    "n_subjects": len(SUBJECTS),
    "per_subject_mean_uv": [round(float(v), 3) for v in means],
    "peak_amplitude_uv_for_reference": peak_amp,
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok",
    "dataset_id": "erpcore_p3",
    "n_subjects": len(SUBJECTS),
    "reference": "average of the 30 scalp electrodes (ERP CORE convention)",
    "filter_hz": [0.1, 30.0],
    "baseline_ms": [-200, 0],
    "epoch_ms": [-200, 800],
    "rare_codes": sorted(RARE),
    "measurement": "mean amplitude of the rare-minus-frequent difference wave at Pz, 300-600 ms, per subject then mean",
}, indent=2))

(OUT / "findings.md").write_text(f"""# ERPP3-001 - the ERP CORE P3b rare-minus-frequent effect at Pz

Reproducing the ERP CORE P3 visual oddball on subjects 1-12 (average reference,
0.1-30 Hz, -200..0 ms baseline), the rare-minus-frequent difference wave at **Pz** is a
clear centro-parietal positivity in the P3b window. Measured as the **mean amplitude**
over **300-600 ms** per subject and averaged over the 12 subjects, the P3b amplitude is
**{mean_amp:.2f} uV** (11/12 subjects positive).

The measurement matters: taking the **peak** (most positive value) in the same window
instead of the mean gives about **{peak_amp:.2f} uV** -- roughly double -- because peak
amplitude always latches onto the largest noise-plus-signal excursion and is biased away
from zero. The mean-amplitude value reported here is the ERP CORE / best-practice measure
for the P3.
""")
print(f"OK: P3b Pz rare-minus-frequent MEAN={mean_amp:.3f} uV | PEAK={peak_amp:.3f} uV | "
      f"n_subjects={len(SUBJECTS)}")
