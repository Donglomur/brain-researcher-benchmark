"""Reference solution for N170PROFILE-001.

Characterise the ERP CORE N170 face effect exactly as Kappenman et al. (2021) do in their
Figure 2 / Tables 1-3: over the FULL N=37 analysis sample, at the a priori PO8 electrode,
from the face-minus-car difference wave. The two headline measurements are

  * the SIGNED face-minus-car MEAN amplitude at PO8 in the 110-150 ms window
    (the ERP CORE N170 amplitude score; group ~ -3 to -4 uV), and
  * the 50% FRACTIONAL-PEAK ONSET latency of the PO8 difference wave (ERPLAB `fpeaklat`,
    negative polarity, peak searched in 10-150 ms, onset = the pre-peak time at which the
    wave reaches 50% of its peak) -- the paper's onset-latency measure.

Both are measured PER SUBJECT (signed) and written to per_subject.csv, then aggregated to a
group mean + 95% CI. The whole-scalp spatio-temporal cluster-based permutation test is
reported ONLY as a DESCRIPTIVE summary of the temporal/scalp support of the effect
(corrected cluster p-values + cluster mass, membership labelled `cluster_level_only`); it is
cluster-level inference, NOT pointwise electrode-by-time significance. The naive uncorrected
point-wise map is reported only to note that its baseline / whole-scalp "significance" is
spurious.

Inputs: the per-subject face-minus-car difference waves produced by the pinned pipeline
(average reference, 0.1-30 Hz, epochs -200..400 ms, -200..0 baseline, 150 uV rejection;
faces = codes 1-40, cars = 41-80), baked into the image at /app/data/n170_diff_waves.npz
(subjects [37], diff_uv [37 x 30 x n_times] in microvolts, ch_names [30], times_ms, sfreq).
"""
import csv
import json
import os
import sys
import warnings
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)
DATA = Path(os.environ.get("N170_DATA_DIR", "/app/data"))
AMP_WIN = (110.0, 150.0)
ONSET_WIN = (10.0, 150.0)


def fail(reason):
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason, "dataset_id": "erpcore_n170"}, indent=2))
    (OUT / "n170.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


def frac_peak_onset(wave, ms, win=ONSET_WIN, frac=0.5):
    """50% fractional-peak ONSET latency (ERPLAB fpeaklat, negative polarity, PeakOnset).

    Peak = most-negative sample in `win`; onset = earliest pre-peak time at which the wave
    crosses frac*peak (linear interpolation between samples). Returns ms, or NaN if there is
    no negative peak / no crossing.
    """
    m = (ms >= win[0]) & (ms <= win[1])
    idx = np.where(m)[0]
    if idx.size < 2:
        return np.nan
    seg = wave[idx]
    ipk = idx[int(np.argmin(seg))]
    peak = wave[ipk]
    if peak >= 0:
        return np.nan
    target = frac * peak  # negative
    j = ipk
    while j > idx[0] and wave[j] <= target:
        j -= 1
    if wave[j] <= target:  # never rose above 50% within the window
        return float(round(ms[idx[0]], 3))
    a, b = wave[j], wave[j + 1]
    if b == a:
        return float(round(ms[j + 1], 3))
    fr = (target - a) / (b - a)
    return float(round(ms[j] + fr * (ms[j + 1] - ms[j]), 3))


def ci95(x):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    n = len(x)
    m = float(x.mean())
    if n < 2:
        return m, m, m
    # t-based 95% CI without SciPy dependency (use a small lookup / normal approx fallback)
    se = float(x.std(ddof=1) / np.sqrt(n))
    try:
        from scipy import stats
        h = float(stats.t.ppf(0.975, n - 1)) * se
    except Exception:
        h = 1.96 * se
    return m, m - h, m + h


npz = DATA / "n170_diff_waves.npz"
if not npz.exists():
    fail(f"baked difference-wave file not found at {npz}")
Z = np.load(npz, allow_pickle=False)
subjects = [str(s) for s in Z["subjects"]]
ch_names = [str(c) for c in Z["ch_names"]]
ms = np.asarray(Z["times_ms"], float)
D = np.asarray(Z["diff_uv"], float)  # nsub x nch x nt, microvolts
sfreq = float(Z["sfreq"])
if "PO8" not in ch_names:
    fail("PO8 not present in the baked difference waves")
po8 = ch_names.index("PO8")
nsub = len(subjects)

# ---- per-subject SIGNED measures at PO8 -------------------------------------------------
amp = np.array([float(np.mean(D[i, po8, (ms >= AMP_WIN[0]) & (ms <= AMP_WIN[1])]))
                for i in range(nsub)])
onset = np.array([frac_peak_onset(D[i, po8, :], ms) for i in range(nsub)])

with open(OUT / "per_subject.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["subject_id", "amp_po8_uv", "onset_ms"])
    for i, s in enumerate(subjects):
        on = onset[i]
        w.writerow([s, f"{amp[i]:.4f}", ("" if not np.isfinite(on) else f"{on:.3f}")])

amp_m, amp_lo, amp_hi = ci95(amp)
on_m, on_lo, on_hi = ci95(onset)

# ---- DESCRIPTIVE whole-scalp cluster test (cluster-level inference only) -----------------
cluster = {"method": "not_run"}
try:
    import mne
    from scipy import stats  # noqa: F401
    mne.set_log_level("ERROR")
    ren = {"FP1": "Fp1", "FP2": "Fp2"}
    info2 = mne.create_info([ren.get(c, c) for c in ch_names], sfreq, "eeg")
    info2.set_montage(mne.channels.make_standard_montage("standard_1020"), on_missing="ignore")
    adjacency, _ = mne.channels.find_ch_adjacency(info2, "eeg")
    X = np.transpose(D, (0, 2, 1))  # nsub x nt x nch
    tobs, clusters, cpv, _ = mne.stats.spatio_temporal_cluster_1samp_test(
        X, adjacency=adjacency, n_permutations=1000, seed=11, n_jobs=1, verbose=False)
    sig = [i for i, p in enumerate(cpv) if p < 0.05]
    cluster_pvals = sorted(float(cpv[i]) for i in sig)
    mass = 0.0
    tmin = tmax = None
    nelec = 0
    if sig:
        best = min(sig, key=lambda i: cpv[i])
        mask = np.zeros(tobs.shape, bool)
        mask[clusters[best]] = True
        mass = float(np.abs(tobs[mask]).sum())
        tt = np.where(mask.any(axis=1))[0]
        tmin = float(round(ms[tt.min()], 1))
        tmax = float(round(ms[tt.max()], 1))
        nelec = int(mask.any(axis=0).sum())
    cluster = {
        "method": "spatio-temporal cluster-based permutation (electrode adjacency, 1-sample)",
        "n_permutations": 1000,
        "cluster_pvals": [round(p, 4) for p in cluster_pvals],
        "min_cluster_pval": (round(min(cluster_pvals), 4) if cluster_pvals else None),
        "cluster_mass": round(mass, 2),
        "time_range_ms": ([tmin, tmax] if tmin is not None else None),
        "n_electrodes": nelec,
        "note": ("descriptive temporal/scalp support of the whole-scalp face-minus-car effect; "
                 "cluster-level inference ONLY -- the time range and electrode set are the "
                 "cluster's membership, NOT pointwise electrode-by-time significance"),
    }
except Exception as e:  # cluster is descriptive; never fail the task on it
    cluster = {"method": "cluster_failed", "error": str(e)}

# ---- naive uncorrected map (reported only to flag it as spurious) ------------------------
try:
    from scipy import stats
    _, pv = stats.ttest_1samp(D, 0, axis=0)  # nch x nt
    sigmap = pv < 0.05
    after = ms >= 0
    first = float(ms[after][sigmap.any(axis=0)[after]][0]) if sigmap.any(axis=0)[after].any() else None
    naive = {
        "n_sig_chan_time": int(sigmap.sum()),
        "n_sig_in_baseline": int(sigmap[:, ms < 0].sum()),
        "n_electrodes_any_sig": int(sigmap.any(axis=1).sum()),
        "first_sig_after_0_ms": first,
        "note": ("uncorrected point-wise significance is SPURIOUS -- it manufactures "
                 "'significant' differences in the pre-stimulus baseline and across the whole "
                 "scalp (multiple-comparisons false positives) and must not be interpreted"),
    }
except Exception:
    naive = {"note": "uncorrected map not computed"}

# ---- outputs ----------------------------------------------------------------------------
(OUT / "n170.json").write_text(json.dumps({
    "electrode": "PO8",
    "n_subjects": nsub,
    "amp_window_ms": list(AMP_WIN),
    "onset_window_ms": list(ONSET_WIN),
    "amp_po8_uv": round(amp_m, 4),
    "amp_po8_ci95": [round(amp_lo, 4), round(amp_hi, 4)],
    "onset_latency_ms": round(on_m, 3),
    "onset_ci95": [round(on_lo, 3), round(on_hi, 3)],
    "onset_method": ("50% fractional-peak latency of the PO8 face-minus-car difference wave "
                     "(negative peak in 10-150 ms; pre-peak crossing of 50% of the peak)"),
    "per_subject_csv": "per_subject.csv",
    "cluster_level_only": cluster,
    "uncorrected_pointwise": naive,
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok",
    "dataset_id": "erpcore_n170",
    "source": "ERP CORE N170 (Kappenman et al. 2021), baked per-subject difference waves",
    "analysis_sample": "N=37 (subjects 1-40 excluding 1, 5, 16 -- the ERP CORE N170 analysis sample)",
    "n_subjects": nsub,
    "electrode": "PO8 (a priori)",
    "reference": "average of the 30 scalp electrodes",
    "filter_hz": [0.1, 30.0],
    "baseline_ms": [-200, 0],
    "epoch_ms": [-200, 400],
    "amp_measure": "signed mean amplitude of face-minus-car at PO8 in 110-150 ms",
    "onset_measure": "50% fractional-peak latency (10-150 ms window, negative polarity), per subject",
    "cluster": ("whole-scalp spatio-temporal cluster-based permutation test reported as a "
                "DESCRIPTIVE summary (cluster-level inference only)"),
}, indent=2))

cl_txt = ""
if cluster.get("time_range_ms"):
    cl_txt = (f"A whole-scalp spatio-temporal cluster-based permutation test gives a single "
              f"corrected cluster (p={cluster['min_cluster_pval']}, cluster mass "
              f"{cluster['cluster_mass']}) whose membership spans "
              f"{cluster['time_range_ms'][0]:.0f}-{cluster['time_range_ms'][1]:.0f} ms over "
              f"{cluster['n_electrodes']} posterior-dominant electrodes. This is reported as a "
              f"**descriptive** summary of the effect's temporal and scalp support "
              f"(*cluster-level inference only* -- it does not license pointwise electrode- or "
              f"time-specific significance claims). ")

(OUT / "findings.md").write_text(f"""# N170PROFILE-001 - the ERP CORE N170 face effect

Over the full **N={nsub}** ERP CORE N170 analysis sample (subjects 1-40 excluding 1, 5 and
16), the face-minus-car difference wave was measured at the a priori **PO8** electrode.

The N170 face effect at PO8 is a clear posterior negativity. Its **signed mean amplitude in
110-150 ms**, measured per subject then averaged, is **{amp_m:.2f} uV**
(95% CI [{amp_lo:.2f}, {amp_hi:.2f}]). The **50% fractional-peak onset latency** of the PO8
difference wave (negative peak in 10-150 ms; the pre-peak time at which the wave reaches 50%
of its peak), measured per subject then averaged, is **{on_m:.1f} ms**
(95% CI [{on_lo:.1f}, {on_hi:.1f}]). Both measures were computed per subject and are listed
in `per_subject.csv`.

{cl_txt}Mapping the effect with an **uncorrected** point-by-point t-test across the 30
electrodes and every sample is misleading: it flags "significant" differences in the
pre-stimulus **baseline** ({naive.get('n_sig_in_baseline', 'NA')} electrode-time points, where
no effect can exist) and across the whole scalp -- these are **spurious** multiple-comparisons
false positives, not a real early/whole-scalp face effect, and are not interpreted here. The
warranted characterisation is the PO8 amplitude and 50%-fractional-peak onset above, with the
cluster result used only as a descriptive, cluster-level summary of the effect's support.
""")

print(f"OK: N={nsub}  PO8 mean amp {amp_m:.2f} uV (CI {amp_lo:.2f},{amp_hi:.2f})  "
      f"50% frac-peak onset {on_m:.1f} ms (CI {on_lo:.1f},{on_hi:.1f})  "
      f"cluster {cluster.get('min_cluster_pval')}/{cluster.get('cluster_mass')}")
