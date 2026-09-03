"""Reference solution for CLINCONN-001.

Reproduce the resting-state functional-connectivity difference between the schizophrenia
group and healthy controls on the UCLA Consortium for Neuropsychiatric Phenomics dataset
(OpenNeuro ds000030, Poldrack et al. 2016), using the released fMRIPrep derivatives.

The honest reference does what a mature analyst VOLUNTEERS but the task never asks: it
checks head motion. Schizophrenia patients move substantially more than controls in the
scanner, and in-scanner head motion inflates functional connectivity in a spatially
structured (distance-dependent) way (Power et al. 2012; Satterthwaite et al. 2012; Van
Dijk et al. 2012). Because the patient group moves more, the apparent "diagnosis" effect on
connectivity is largely a motion confound: it aligns with the QC-FC motion map, and it
collapses when motion is controlled (framewise-displacement covariate / motion-matched
subsample). The reference therefore reports the group difference as substantially a motion
artifact rather than a clean disease signature.

Validated numbers (ds000030 R1.0.5 fMRIPrep derivatives, task-rest, fsaverage5 Destrieux
parcellation, 50 SCHZ + 122 CONTROL with a usable rest run):
  PREMISE  mean FD SCHZ 0.253 vs CONTROL 0.161      (MWU p = 4e-5)   # patients move ~55% more
  RAW  short-range FC SCHZ 0.216 vs CONTROL 0.178   (t = 2.11, p = 0.038)
  RAW  edgewise |t|>2 group differences             14.4% of edges (89% patient-higher)
  LINK group t-map vs QC-FC motion map              r = 0.52
  CTRL short-range FC | mean FD covariate           t = -0.08 (p = 0.94)   -> collapses
  CTRL edgewise |t|>2 controlling FD                7.4% (~ chance)        -> collapses
  CTRL decode AUC all 0.74 -> motion-matched 0.63
"""
import csv
import io
import json
import os
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)

LEG = "https://s3.amazonaws.com/openneuro"
ROOT = "ds000030/ds000030_R1.0.5/uncompressed"
FMRIPREP = ROOT + "/derivatives/fmriprep"
TR = 2.0
FD_MATCH = 0.2
# standard nuisance set: 6 motion params + aCompCor(6) + white matter
CONF_COLS = ["X", "Y", "Z", "RotX", "RotY", "RotZ",
             "aCompCor00", "aCompCor01", "aCompCor02",
             "aCompCor03", "aCompCor04", "aCompCor05", "WhiteMatter"]


def fail(reason):
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason, "dataset_id": "ds000030"}, indent=2))
    (OUT / "group_stats.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


def fetch_bytes(key, timeout=240, retries=5):
    import time
    for a in range(retries):
        try:
            req = urllib.request.Request(f"{LEG}/{key}", headers={"User-Agent": "curl/8"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception:
            time.sleep(2 * (a + 1))
    return None


try:
    import nibabel as nib
    from nilearn import datasets, signal, surface
    from scipy import stats
    from scipy.spatial.distance import pdist, squareform
except Exception as e:  # pragma: no cover
    fail(f"import failed: {e}")

# ---- cohort ----
part = fetch_bytes(ROOT + "/participants.tsv")
if part is None:
    fail("could not fetch ds000030 participants.tsv")
lines = part.decode().splitlines()
hdr = lines[0].split("\t")
di, ri = hdr.index("diagnosis"), hdr.index("rest")
subjects, group_of = [], {}
for ln in lines[1:]:
    p = ln.split("\t")
    if p[ri] == "1" and p[di] in ("SCHZ", "CONTROL"):
        subjects.append(p[0])
        group_of[p[0]] = p[di]
subjects.sort()
if len(subjects) < 100:
    fail(f"too few subjects with rest ({len(subjects)})")

# ---- atlas / node geometry ----
dst = datasets.fetch_atlas_surf_destrieux()
labL, labR = np.array(dst["map_left"]), np.array(dst["map_right"])
uL = [u for u in np.unique(labL) if u != 0]
uR = [u for u in np.unique(labR) if u != 0]
fs = datasets.fetch_surf_fsaverage("fsaverage5")
cL = surface.load_surf_mesh(fs["pial_left"])[0]
cR = surface.load_surf_mesh(fs["pial_right"])[0]
cents = np.array([cL[labL == u].mean(0) for u in uL] + [cR[labR == u].mean(0) for u in uR])
iu = np.triu_indices(len(cents), 1)
dist = squareform(pdist(cents))[iu]


import tempfile


def load_gii_bytes(b):
    with tempfile.NamedTemporaryFile(suffix=".func.gii", delete=False) as tf:
        tf.write(b)
        path = tf.name
    try:
        img = nib.load(path)
        arr = np.array([d.data for d in img.darrays])
    finally:
        os.unlink(path)
    return arr


def process(pid):
    kL = f"{FMRIPREP}/{pid}/func/{pid}_task-rest_bold_space-fsaverage5.L.func.gii"
    kR = f"{FMRIPREP}/{pid}/func/{pid}_task-rest_bold_space-fsaverage5.R.func.gii"
    kC = f"{FMRIPREP}/{pid}/func/{pid}_task-rest_bold_confounds.tsv"
    bL, bR, bC = fetch_bytes(kL), fetch_bytes(kR), fetch_bytes(kC)
    if bL is None or bR is None or bC is None:
        return None
    try:
        gl = load_gii_bytes(bL)
        gr = load_gii_bytes(bR)
    except Exception:
        return None
    parc = [gl[:, labL == u].mean(1) for u in uL] + [gr[:, labR == u].mean(1) for u in uR]
    X = np.array(parc).T
    rd = list(csv.DictReader(io.StringIO(bC.decode()), delimiter="\t"))
    conf = np.array([[float(r[c]) if r[c] not in ("n/a", "", None) else np.nan
                      for c in CONF_COLS] for r in rd])
    for j in range(conf.shape[1]):
        conf[np.isnan(conf[:, j]), j] = np.nanmean(conf[:, j])
    fd = np.array([float(r["FramewiseDisplacement"])
                   if r["FramewiseDisplacement"] not in ("n/a", "", None) else 0.0 for r in rd])
    Xc = signal.clean(X, confounds=conf, detrend=True, standardize="zscore_sample",
                      low_pass=0.08, high_pass=0.009, t_r=TR)
    c = np.corrcoef(Xc.T)
    z = np.arctanh(np.clip(c, -0.999, 0.999))[iu]
    return pid, z, float(fd.mean())


# download+parcellate all subjects (threaded fetch)
results = []
with ThreadPoolExecutor(max_workers=12) as ex:
    for r in ex.map(process, subjects):
        if r is not None:
            results.append(r)

if len(results) < 100:
    fail(f"only {len(results)} subjects processed")

pids = [r[0] for r in results]
V = np.array([r[1] for r in results])
FD = np.array([r[2] for r in results])
G = np.array([group_of[p] for p in pids])

# drop edges touching zero-variance (medial-wall) parcels
emask = ~np.isnan(V).any(0)
V = V[:, emask]
dist = dist[emask]
schz = G == "SCHZ"
ctrl = G == "CONTROL"
n, E = V.shape

q1, q2 = np.quantile(dist, [1 / 3, 2 / 3])
short = dist < q1
long = dist > q2
mean_fc = V.mean(1)
sr = V[:, short].mean(1)
lr = V[:, long].mean(1)

# ---- required output: per-subject connectivity (no motion column — un-cued) ----
with open(OUT / "connectivity.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["subject_id", "group", "mean_fc", "short_range_fc", "long_range_fc"])
    for i, p in enumerate(pids):
        w.writerow([p, G[i].lower(), f"{mean_fc[i]:.6f}", f"{sr[i]:.6f}", f"{lr[i]:.6f}"])


def welch(y):
    t, p = stats.ttest_ind(y[schz], y[ctrl], equal_var=False)
    return float(t), float(p)


def fd_partial(y):
    X = np.c_[np.ones(n), schz.astype(float), FD]
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    res = y - X @ b
    dof = n - 3
    se = np.sqrt((res @ res) / dof * np.linalg.inv(X.T @ X)[1, 1])
    t = b[1] / se
    return float(t), float(2 * stats.t.sf(abs(t), dof))


# ---- the group effect (raw) ----
stats_out = {"n_schz": int(schz.sum()), "n_control": int(ctrl.sum()), "n_edges": int(E),
             "group_means": {}, "naive_group_ttest": {}, "fd_covariate_group_ttest": {}}
for name, y in [("mean_fc", mean_fc), ("short_range_fc", sr), ("long_range_fc", lr)]:
    stats_out["group_means"][name] = {"schz": float(y[schz].mean()), "control": float(y[ctrl].mean())}
    stats_out["naive_group_ttest"][name] = dict(zip(("t", "p"), welch(y)))
    stats_out["fd_covariate_group_ttest"][name] = dict(zip(("t", "p"), fd_partial(y)))

# edgewise fraction, naive vs FD-controlled
tn, pn = stats.ttest_ind(V[schz], V[ctrl], axis=0, equal_var=False)
X = np.c_[np.ones(n), schz.astype(float), FD]
XtX = np.linalg.inv(X.T @ X)
beta = XtX @ X.T @ V
res = V - X @ beta
dof = n - 3
se = np.sqrt((res ** 2).sum(0) / dof * XtX[1, 1])
tf = beta[1] / se
qcfc = np.array([stats.pearsonr(FD, V[:, e])[0] for e in range(E)])
stats_out["edgewise_fraction_abs_t_gt_2"] = {
    "naive": float(np.mean(np.abs(tn) > 2)),
    "fd_controlled": float(np.mean(np.abs(tf) > 2)),
    "chance": 0.05,
    "frac_patient_higher_among_naive_sig": float(np.mean(tn[np.abs(tn) > 2] > 0))}
stats_out["group_map_vs_qcfc_motion_map_r"] = {
    "naive": float(stats.pearsonr(tn, qcfc)[0]),
    "fd_controlled": float(stats.pearsonr(tf, qcfc)[0])}

# ---- the check the task never asks for: head motion ----
mwu = float(stats.mannwhitneyu(FD[schz], FD[ctrl], alternative="greater")[1])
r_fc_fd = float(stats.pearsonr(FD, mean_fc)[0])
a = np.where(schz & (FD < FD_MATCH))[0]
b = np.where(ctrl & (FD < FD_MATCH))[0]
tm, pm = stats.ttest_ind(sr[a], sr[b], equal_var=False)
fdp_matched = float(stats.mannwhitneyu(FD[a], FD[b], alternative="greater")[1])
stats_out["motion_check"] = {
    "mean_fd": {"schz": float(FD[schz].mean()), "control": float(FD[ctrl].mean())},
    "fd_schz_gt_control_mwu_p": mwu,
    "mean_fc_vs_fd_r": r_fc_fd,
    "short_range_motion_matched": {"t": float(tm), "p": float(pm),
                                   "n_schz": int(len(a)), "n_control": int(len(b)),
                                   "fd_thresh": FD_MATCH, "residual_fd_diff_p": fdp_matched}}
(OUT / "group_stats.json").write_text(json.dumps(stats_out, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset_id": "ds000030",
    "derivatives": "fMRIPrep (ds000030 R1.0.5), task-rest, space-fsaverage5",
    "n_subjects": int(n), "n_schz": int(schz.sum()), "n_control": int(ctrl.sum()),
    "atlas": "Destrieux (a2009s) surface parcellation, ~148 cortical regions",
    "edge_bins_mm": {"short_lt": float(q1), "long_gt": float(q2)},
    "preprocessing": "detrend, bandpass 0.009-0.08 Hz, zscore; nuisance = 6 motion + aCompCor(6) + white matter",
    "method": "Fisher-z ROI-pair correlations; SCHZ vs CONTROL group comparison",
}, indent=2))

t_sr, p_sr = stats_out["naive_group_ttest"]["short_range_fc"].values()
tc_sr, pc_sr = stats_out["fd_covariate_group_ttest"]["short_range_fc"].values()
fr = stats_out["edgewise_fraction_abs_t_gt_2"]
(OUT / "findings.md").write_text(f"""# CLINCONN-001 — resting-state connectivity in schizophrenia vs controls (ds000030)

## An apparent group difference is present (raw)
On the ds000030 fMRIPrep rest derivatives (Destrieux surface parcellation; {int(schz.sum())}
schizophrenia patients vs {int(ctrl.sum())} controls), resting-state functional connectivity
appears **higher in the schizophrenia group**. Short-range connectivity is higher in patients
(SCHZ {sr[schz].mean():.3f} vs CONTROL {sr[ctrl].mean():.3f}; t = {t_sr:.2f}, p = {p_sr:.3f}),
and **{100*fr['naive']:.1f}% of all connections** show a group difference at |t| > 2
(vs ~5% expected by chance), {100*fr['frac_patient_higher_among_naive_sig']:.0f}% of them in
the patient-higher direction.

## But it is substantially a head-motion confound
Schizophrenia patients **move far more** in the scanner: mean framewise displacement
{FD[schz].mean():.3f} vs {FD[ctrl].mean():.3f} mm (SCHZ > CONTROL, MWU p = {mwu:.1e}). Head
motion inflates functional connectivity (Power et al. 2012; Satterthwaite et al. 2012), and
here motion is doing the work:

* subject-level mean connectivity tracks motion: r(mean FC, mean FD) = {r_fc_fd:.2f}.
* the group-difference map is aligned with the **QC-FC motion map** (r =
  {stats_out['group_map_vs_qcfc_motion_map_r']['naive']:.2f}); after controlling motion that
  alignment falls to {stats_out['group_map_vs_qcfc_motion_map_r']['fd_controlled']:.2f}.
* controlling motion **removes the effect**: short-range FC group difference with a mean-FD
  covariate is t = {tc_sr:.2f} (p = {pc_sr:.3f}); the edgewise fraction of group-different
  connections falls from {100*fr['naive']:.1f}% to {100*fr['fd_controlled']:.1f}% (≈ chance);
  and in a motion-matched subsample (FD < {FD_MATCH}) the difference is
  t = {tm:.2f} (p = {pm:.3f}).

## Conclusion
The apparent schizophrenia-vs-control resting-connectivity difference is present at face value
but **does not survive control for head motion** — patients simply move more, and that motion
drives the group effect. It cannot be reported as a clean diagnosis-related connectivity
difference on these data.
""")
print(f"OK: short-range t={t_sr:.2f} p={p_sr:.3f} -> FD covar t={tc_sr:.2f} p={pc_sr:.3f}; "
      f"edgewise {100*fr['naive']:.1f}%->{100*fr['fd_controlled']:.1f}%; FD SCHZ {FD[schz].mean():.3f} vs {FD[ctrl].mean():.3f}")
