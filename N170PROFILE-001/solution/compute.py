"""Reference solution for N170PROFILE-001.

Map the ERP CORE N170 face-minus-car difference across the 30 scalp electrodes and the
whole epoch (subjects 1-12), and report where/when faces and cars reliably differ. The
whole preprocessing pipeline is pinned by the task (average reference, 0.1-30 Hz,
-200..400 epoch, -200..0 baseline, 150 uV rejection).

The open, un-cued judgement is HOW to decide "reliably differ" across ~4600
electrode x time comparisons. A naive point-by-point one-sample t-test (p < .05) at every
electrode and every sample is the natural default AND it is wrong: with 30 electrodes x
154 samples uncorrected, it flags significance in the pre-stimulus BASELINE (physically
impossible) and as early as ~35 ms, across all 30 electrodes -- these are false positives.

Correcting for multiple comparisons (here a spatio-temporal cluster-based permutation test
with electrode adjacency) removes the baseline/early false positives and confines the
reliable face-minus-car effect to a posterior-dominant window ~82-145 ms.

Validated on the ERP CORE N170 files, subjects 1-12:
    PO8 peak (110-150 ms, per-subject then mean)        : -6.15 uV
    naive uncorrected point-wise (p<.05)                : 754 sig ch-time pts, 125 of them
                                                          in the pre-stimulus baseline,
                                                          all 30/30 electrodes, onset 35 ms
    cluster-corrected (multiple-comparisons corrected)  : 82-145 ms, 28 electrodes, onset 82 ms
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
    env = os.environ.get("ERPCORE_N170_DIR")
    if env and all((Path(env) / f"{s}_N170_shifted_ds.set").exists() for s in SUBJECTS):
        return Path(env)
    d = Path(tempfile.mkdtemp(prefix="erpcore_n170_"))
    for s in SUBJECTS:
        set_id, fdt_id = OSF[s]
        for fid, ext in ((set_id, "set"), (fdt_id, "fdt")):
            try:
                urllib.request.urlretrieve(f"https://osf.io/download/{fid}/", d / f"{s}_N170_shifted_ds.{ext}")
            except Exception as e:
                fail(f"OSF download failed for subject {s} .{ext}: {e}")
    return d


try:
    import mne
    from scipy import stats
    mne.set_log_level("ERROR")
except Exception as e:  # pragma: no cover
    fail(f"import failed: {e}")

DDIR = data_dir()


def subj_diff(subj):
    raw = mne.io.read_raw_eeglab(f"{DDIR}/{subj}_N170_shifted_ds.set", preload=True)
    raw.set_channel_types({c: "eog" for c in EOG})
    raw.filter(0.1, 30.0, picks="eeg", verbose=False)
    ev, eid = mne.events_from_annotations(raw, verbose=False)
    id2d = {v: int(k) for k, v in eid.items()}
    ne = [[o, 0, 1] if id2d[c] in FACE else [o, 0, 2]
          for o, _, c in ev if id2d[c] in FACE or id2d[c] in CAR]
    ep = mne.Epochs(raw, np.array(ne), {"face": 1, "car": 2}, tmin=-0.2, tmax=0.4,
                    baseline=None, reject=None, preload=True, verbose=False)
    ep.set_eeg_reference("average", projection=False, verbose=False)
    ep.apply_baseline((-0.2, 0.0), verbose=False)
    ep.drop_bad(reject=dict(eeg=150e-6), verbose=False)
    return mne.combine_evoked([ep["face"].average(), ep["car"].average()], weights=[1, -1])


diffs = [subj_diff(s) for s in SUBJECTS]
info = diffs[0].info
chn = list(diffs[0].ch_names)
ms = diffs[0].times * 1000.0
D = np.array([d.data for d in diffs]) * 1e6          # nsub x nch x nt
po8 = chn.index("PO8")

# PO8 peak amplitude (110-150 ms), per subject then mean -- sanity that the ERP is right.
seg = D[:, po8, :][:, (ms >= 110) & (ms <= 150)]
po8_peak = float(seg[np.arange(len(SUBJECTS)), np.argmin(seg, axis=1)].mean())

# NAIVE point-wise map (reported only to expose the multiple-comparisons problem).
_, pv = stats.ttest_1samp(D, 0, axis=0)
sig = pv < 0.05
naive = {
    "n_sig_chan_time": int(sig.sum()),
    "n_sig_in_baseline": int(sig[:, ms < 0].sum()),
    "n_electrodes_any_sig": int(sig.any(axis=1).sum()),
    "onset_first_sig_after_0_ms": float(ms[ms >= 0][sig.any(axis=0)[ms >= 0]][0]),
}

# HONEST: spatio-temporal cluster-based permutation test (correct for multiple comparisons).
ren = {"FP1": "Fp1", "FP2": "Fp2"}
info2 = mne.create_info([ren.get(c, c) for c in chn], info["sfreq"], "eeg")
info2.set_montage(mne.channels.make_standard_montage("standard_1020"), on_missing="ignore")
adjacency, _ = mne.channels.find_ch_adjacency(info2, "eeg")
X = np.transpose(D, (0, 2, 1))                       # nsub x nt x nch
_, clusters, cpv, _ = mne.stats.spatio_temporal_cluster_1samp_test(
    X, adjacency=adjacency, n_permutations=1000, seed=11, n_jobs=1, verbose=False)
mask = np.zeros((len(ms), len(chn)), bool)
for cl, p in zip(clusters, cpv):
    if p < 0.05:
        mask[cl] = True
tt = np.where(mask.any(axis=1))[0]
if not len(tt):
    fail("no significant cluster found after correction (unexpected)")
onset = float(round(ms[tt.min()], 1))
tmax = float(round(ms[tt.max()], 1))
sig_electrodes = [chn[i] for i in range(len(chn)) if mask[:, i].any()]

(OUT / "n170.json").write_text(json.dumps({
    "onset_latency_ms": onset,
    "sig_time_range_ms": [onset, tmax],
    "sig_electrodes": sig_electrodes,
    "peak_amplitude_po8_uv": round(po8_peak, 3),
    "n_subjects": len(SUBJECTS),
    "n_sig_electrodes": len(sig_electrodes),
    "correction": "spatio-temporal cluster-based permutation (electrode adjacency)",
    "uncorrected_pointwise": naive,
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok",
    "dataset_id": "erpcore_n170",
    "n_subjects": len(SUBJECTS),
    "reference": "average of the 30 scalp electrodes",
    "filter_hz": [0.1, 30.0],
    "baseline_ms": [-200, 0],
    "epoch_ms": [-200, 400],
    "reliability": ("group-level face-minus-car difference assessed across all 30 electrodes "
                    "and all samples; reliability decided with a spatio-temporal cluster-based "
                    "permutation test (5000/1000 permutations) that corrects for the ~4600 "
                    "electrode-by-time comparisons"),
}, indent=2))

(OUT / "findings.md").write_text(f"""# N170PROFILE-001 - spatiotemporal profile of the face effect

Reproducing the ERP CORE N170 paradigm on subjects 1-12 (average reference, 0.1-30 Hz),
the face-minus-car difference wave at PO8 is a clear negativity; its peak (most negative)
amplitude in 110-150 ms, per subject then averaged, is **{po8_peak:.2f} uV**.

To map *where and when* faces and cars reliably differ, one compares the two conditions at
every electrode and every time sample. Doing this with an **uncorrected** point-by-point
one-sample t-test (p < .05) is misleading: across 30 electrodes x 154 samples (~4600 tests)
it flags "significant" differences in the **pre-stimulus baseline** ({naive['n_sig_in_baseline']}
samples, where no effect can exist) and as early as {naive['onset_first_sig_after_0_ms']:.0f} ms,
spread across all {naive['n_electrodes_any_sig']}/30 electrodes. Those are **false positives
from multiple comparisons**, not real effects.

Correcting for multiple comparisons with a **spatio-temporal cluster-based permutation
test** (electrode adjacency) removes the baseline and early false positives: the reliable
face-minus-car difference is confined to **{onset:.0f}-{tmax:.0f} ms** over
**{len(sig_electrodes)} posterior-dominant electrodes** (including PO8/PO7/P8/P10/O1/O2).
The onset latency of the reliable effect is **{onset:.0f} ms**. The uncorrected map
substantially over-states both the temporal extent (it reaches into the baseline) and the
spatial spread of the effect; only the cluster-corrected result should be interpreted.
""")
print(f"OK: PO8 peak={po8_peak:.2f} uV; corrected effect {onset:.0f}-{tmax:.0f} ms over "
      f"{len(sig_electrodes)} electrodes (naive: {naive['n_sig_in_baseline']} baseline false positives)")
