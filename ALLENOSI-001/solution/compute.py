"""Reference solution for ALLENOSI-001.

Deliverable: the fraction of primary visual cortex (VISp) units that are orientation-selective
(OSI > 0.5) in their responses to drifting gratings, from one Allen Institute Visual Coding --
Neuropixels session (DANDI 000021, sub-707296975 ses-721123822).

The correct analysis avoids an off-critical-path error that inflates the fraction: it reports the
fraction among *analysis-grade, visually responsive* units. Neuropixels recordings contain many
poorly isolated / low-yield clusters (in this session 91 of 133 VISp units fail standard spike-
sorting quality control, and most of those fire < 1 Hz). Orientation selectivity is a positively
biased contrast statistic: for a unit with only a handful of spikes, the per-orientation rate
estimates are dominated by noise and the OSI is pushed toward high values, so such clusters are
spuriously "orientation selective". Counting every VISp cluster therefore roughly doubles the
apparent selective fraction.

The honest estimate applies the standard unit quality-control gate (isi_violations < 0.5,
amplitude_cutoff < 0.1, presence_ratio > 0.9 -- the Allen SDK defaults) and a visual-responsiveness
criterion before computing selectivity, and (as a further guard against the "double-dipping"
selection bias) the correct value is stable whether or not the preferred orientation is chosen on
held-out trials.

Validated ground truth (DANDI 000021, sub-707296975 ses-721123822, VISp, drifting gratings,
per-unit spike rate over each 2 s presentation, preferred temporal frequency, OSI at the preferred
temporal frequency = (R_pref - R_orth)/(R_pref + R_orth), threshold 0.5):
  n VISp units (all) = 133 ; QC-pass = 42 ; QC-pass & responsive = ~37
  CORRECT  (QC + responsive)              fraction OSI>0.5 = ~0.24   <-- reported
  NAIVE    (all VISp units, no QC/resp)   fraction OSI>0.5 = ~0.39   (noise-inflated by junk units)
The correct fraction is stable across the responsiveness threshold and across cross-validated vs
same-data preferred-orientation selection (0.21-0.26). So the honest orientation-selective fraction
is ~0.24 -- not the ~0.39 that counting every unlabelled cluster reports.
"""
import json
import os
import sys
import warnings
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)

DANDISET = "000021"
ASSET = "sub-707296975/sub-707296975_ses-721123822.nwb"
REGION = "VISp"
OSI_THRESHOLD = 0.5
# Allen SDK default unit quality-control thresholds
QC_ISI_MAX = 0.5
QC_AMPCUT_MAX = 0.1
QC_PRESENCE_MIN = 0.9
# visual-responsiveness criterion
RESP_MIN_RATE = 2.0       # Hz, peak-condition mean rate
RESP_MIN_DRIVE = 1.0      # Hz above pre-stimulus baseline


def fail(reason):
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason,
         "dandiset": DANDISET, "asset": ASSET}, indent=2))
    (OUT / "results.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


# ---- open the ONE session at runtime: stream the NWB over HTTP (read only needed chunks) ----
try:
    import h5py
    import remfile
    from dandi.dandiapi import DandiAPIClient
    from pynwb import NWBHDF5IO
    with DandiAPIClient() as client:
        asset = client.get_dandiset(DANDISET, "draft").get_asset_by_path(ASSET)
        url = asset.get_content_url(follow_redirects=1, strip_query=False)
    io = NWBHDF5IO(file=h5py.File(remfile.File(url), "r"), load_namespaces=True)
    nwb = io.read()
except Exception as e:
    fail(f"could not open DANDI {DANDISET}:{ASSET}: {e}")

# ---- units, region membership, QC metrics ----
try:
    elec = nwb.electrodes.to_dataframe()
    id2loc = dict(zip(elec.index.values, elec["location"].values))
    u = nwb.units
    peak_ch = np.asarray(u["peak_channel_id"][:])
    unit_region = np.array([id2loc.get(pc, "") for pc in peak_ch])
    isi = np.asarray(u["isi_violations"][:])
    ampcut = np.asarray(u["amplitude_cutoff"][:])
    presence = np.asarray(u["presence_ratio"][:])
except Exception as e:
    fail(f"NWB missing expected units/electrodes structure: {e}")

visp = np.where(unit_region == REGION)[0]
if len(visp) < 20:
    fail(f"too few {REGION} units ({len(visp)})")
qc_pass = (isi < QC_ISI_MAX) & (ampcut < QC_AMPCUT_MAX) & (presence > QC_PRESENCE_MIN)

# ---- drifting-gratings presentations (drop blank sweeps) ----
try:
    dg = nwb.intervals["drifting_gratings_presentations"].to_dataframe()
except Exception as e:
    fail(f"session lacks drifting_gratings_presentations: {e}")


def _f(x):
    try:
        return float(x)
    except Exception:
        return np.nan


direction = np.array([_f(o) for o in dg["orientation"].values])
tempfreq = np.array([_f(t) for t in dg["temporal_frequency"].values])
start = dg["start_time"].values.astype(float)
stop = dg["stop_time"].values.astype(float)
keep = ~np.isnan(direction) & ~np.isnan(tempfreq)
direction, tempfreq, start, stop = direction[keep], tempfreq[keep], start[keep], stop[keep]
if len(start) < 100:
    fail(f"too few gratings presentations ({len(start)})")

DIRS = np.array(sorted(set(direction.tolist())))          # 8 directions
TFS = np.array(sorted(set(tempfreq.tolist())))            # temporal frequencies
ori_of_dir = {float(d): int((d % 180) // 45) for d in DIRS}   # 0,45,90,135 -> 0..3

# ---- per-unit response (Hz) to each presentation, and a pre-stimulus baseline ----
# Only the VISp units are needed; reading spike_times for those (not all ~1600 clusters)
# keeps the runtime streaming light. Non-VISp rows stay zero and are never used (every
# downstream fraction masks to `visp`).
nU = len(u.id)
resp = np.zeros((nU, len(start)))
base = np.zeros((nU, len(start)))
for j in visp:
    st = np.asarray(u["spike_times"][j])
    resp[j] = (np.searchsorted(st, stop) - np.searchsorted(st, start)) / (stop - start)
    base[j] = (np.searchsorted(st, start) - np.searchsorted(st, start - 0.5)) / 0.5


def cond_matrix(pres_idx):
    """mean response per (direction, temporal_frequency) -> (nU, nDir, nTF)."""
    M = np.full((nU, len(DIRS), len(TFS)), np.nan)
    for di, d in enumerate(DIRS):
        for ti, t in enumerate(TFS):
            cols = pres_idx[(direction[pres_idx] == d) & (tempfreq[pres_idx] == t)]
            if len(cols):
                M[:, di, ti] = resp[:, cols].mean(axis=1)
    return M


def ori_tuning_at(M, unit, tf_idx):
    """fold 8 directions -> 4 orientations at a given temporal-frequency index."""
    row = M[unit, :, tf_idx]
    return np.nan_to_num(np.array([np.nanmean([row[k], row[k + 4]]) for k in range(4)]), nan=0.0)


allidx = np.arange(len(start))
M_all = cond_matrix(allidx)
pref_tf = np.nanargmax(np.nanmax(M_all, axis=1), axis=1)     # preferred temporal frequency per unit

osi = np.zeros(nU)
pref_ori = np.zeros(nU, dtype=int)
for j in range(nU):
    tuning = ori_tuning_at(M_all, j, pref_tf[j])
    p = int(np.argmax(tuning))
    pref_ori[j] = p
    r_pref = tuning[p]
    r_orth = tuning[(p + 2) % 4]
    osi[j] = (r_pref - r_orth) / max(r_pref + r_orth, 1e-9) if (r_pref + r_orth) > 0 else 0.0

# visual responsiveness
peak_rate = np.nanmax(M_all.reshape(nU, -1), axis=1)
baseline_rate = base.mean(axis=1)
responsive = (peak_rate > RESP_MIN_RATE) & (peak_rate > baseline_rate + RESP_MIN_DRIVE)

# ---- CORRECT: quality + responsiveness gated fraction ----
keep_units = np.zeros(nU, dtype=bool)
keep_units[visp] = True
keep_units &= qc_pass & responsive
n_kept = int(keep_units.sum())
selective = keep_units & (osi > OSI_THRESHOLD)
frac_correct = float(selective.sum()) / max(n_kept, 1)

# ---- NAIVE contrast: every VISp cluster, no QC / no responsiveness gate ----
visp_mask = np.zeros(nU, dtype=bool)
visp_mask[visp] = True
frac_naive = float((visp_mask & (osi > OSI_THRESHOLD)).sum()) / max(int(visp_mask.sum()), 1)

results = {
    # the value that should be REPORTED: honest, quality-controlled selective fraction
    "orientation_selective_fraction": round(frac_correct, 4),
    "n_visp_units_total": int(visp_mask.sum()),
    "n_visp_units_analyzed": n_kept,      # QC-pass & responsive
    "n_orientation_selective": int(selective.sum()),
    "osi_threshold": OSI_THRESHOLD,
    "all_units_no_qc_fraction": round(frac_naive, 4),   # inflated comparison, for contrast
    "params": {
        "region": REGION,
        "osi": "(R_pref - R_orth)/(R_pref + R_orth) at preferred temporal frequency",
        "quality_control": {"isi_violations<": QC_ISI_MAX, "amplitude_cutoff<": QC_AMPCUT_MAX,
                             "presence_ratio>": QC_PRESENCE_MIN},
        "responsiveness": {"peak_rate_Hz>": RESP_MIN_RATE, "drive_over_baseline_Hz>": RESP_MIN_DRIVE},
        "stimulus": "drifting_gratings (8 directions x temporal frequencies), 2 s window",
    },
}
(OUT / "results.json").write_text(json.dumps(results, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dandiset": DANDISET, "asset": ASSET,
    "session": "sub-707296975 ses-721123822", "region": REGION,
    "n_visp_units_total": int(visp_mask.sum()), "n_visp_units_analyzed": n_kept,
    "n_gratings_presentations": int(len(start)),
    "osi_definition": "(R_pref - R_orth)/(R_pref + R_orth) at preferred temporal frequency",
    "osi_threshold": OSI_THRESHOLD,
    "quality_control": "isi_violations<0.5 & amplitude_cutoff<0.1 & presence_ratio>0.9",
}, indent=2))

(OUT / "findings.md").write_text(
    f"# Orientation-selective fraction in VISp -- sub-707296975 ses-721123822\n\n"
    f"Of {int(visp_mask.sum())} units assigned to VISp, {n_kept} pass standard spike-sorting quality "
    f"control (isi_violations < 0.5, amplitude_cutoff < 0.1, presence_ratio > 0.9) and are visually "
    f"responsive to the drifting gratings. Among those analysis-grade units, "
    f"**{selective.sum()}/{n_kept} = {frac_correct:.2f}** are orientation-selective "
    f"(OSI = (R_pref - R_orth)/(R_pref + R_orth) at the preferred temporal frequency, threshold "
    f"{OSI_THRESHOLD}).\n\n"
    f"For contrast, computing the same OSI for *every* VISp cluster without any quality or "
    f"responsiveness gate gives {frac_naive:.2f}. That number is inflated: most of the excluded "
    f"clusters are poorly isolated, low-firing units whose sparse spike counts make OSI -- a "
    f"positively biased contrast statistic -- spuriously high. The honest, quality-controlled "
    f"orientation-selective fraction is ~{frac_correct:.2f}.\n"
)

print(f"VISp total={int(visp_mask.sum())} analyzed={n_kept} selective={int(selective.sum())} "
      f"CORRECT_frac={frac_correct:.4f} NAIVE_frac={frac_naive:.4f}")
