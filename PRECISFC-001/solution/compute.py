"""Reference solution for PRECISFC-001.

Quantify the test-retest reliability of the individual resting-state functional connectome
across sessions in the Midnight Scan Club precision-fMRI dataset (OpenNeuro ds000224; Gordon
et al. 2017, Neuron), using the released volume-pipeline resting-state derivatives.

The honest reference does what a mature analyst VOLUNTEERS but the task never spells out:
it respects the data-quality controls that MSC precision mapping depends on. Each processed
resting run ships a temporal mask (`*_tmask.txt`) marking the low-motion frames to keep;
high-motion frames must be censored (FD scrubbing) before computing connectivity (Power et
al. 2012). And two subjects are documented as low quality -- MSC08 (pervasive self-reported
drowsiness -> unstable, aberrant networks) and MSC09 (excessive in-scanner motion -> little
usable low-motion data) -- and are excluded from analyses that require clean data (Gordon et
al. 2017; Laumann et al. 2015; Seitzman et al. 2019).

Ignoring either control deflates and contaminates the reliability estimate. The reference
reports reliability with frame-censoring applied and the two low-quality subjects excluded,
and states that the naive estimate (all frames, all subjects) is substantially lower for
those reasons.

Validated numbers (ds000224 volume_pipeline, Power-264 5 mm spheres, sub-MSC01/02/05/06/08/09,
ses-func01/02/03; cross-session reliability = mean pairwise correlation of session connectomes):
  per subject  reliability (all frames -> censored), frame retention
    MSC01  0.625 -> 0.660  (80%)     MSC02  0.542 -> 0.543  (86%)
    MSC05  0.679 -> 0.686  (84%)     MSC06  0.751 -> 0.754  (93%)
    MSC08  0.085 -> 0.300  (24%)     MSC09  0.514 -> 0.531  (60%)   # documented low-quality
  GROUP mean reliability
    naive   (all frames, all 6 subjects)              0.533
    correct (censored + exclude MSC08 & MSC09)        0.660
"""
import json
import os
import sys
import tempfile
import urllib.request
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)

B = "https://s3.amazonaws.com/openneuro.org"
DERIV = "ds000224/derivatives/volume_pipeline"
SUBJECTS = ["MSC01", "MSC02", "MSC05", "MSC06", "MSC08", "MSC09"]
SESSIONS = ["func01", "func02", "func03"]
# documented low-quality subjects (Gordon 2017: MSC08 drowsy; MSC09 high motion / little data)
LOW_QUALITY = ["MSC08", "MSC09"]


def fail(reason):
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason, "dataset_id": "ds000224"}, indent=2))
    (OUT / "reliability_stats.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


def fetch_to_tmp(key, suffix, timeout=600, retries=5):
    import time
    for a in range(retries):
        try:
            req = urllib.request.Request(f"{B}/{key}", headers={"User-Agent": "curl/8"})
            fd, path = tempfile.mkstemp(suffix=suffix)
            with urllib.request.urlopen(req, timeout=timeout) as r, os.fdopen(fd, "wb") as f:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
            if os.path.getsize(path) > 0:
                return path
        except Exception:
            time.sleep(3 * (a + 1))
    return None


try:
    from nilearn import datasets
    from nilearn.maskers import NiftiSpheresMasker
except Exception as e:  # pragma: no cover
    fail(f"nilearn import failed: {e}")

try:
    power = datasets.fetch_coords_power_2011()
except Exception as e:
    fail(f"could not fetch Power-264 atlas: {e}")
coords = np.vstack([power.rois["x"], power.rois["y"], power.rois["z"]]).T
iu = np.triu_indices(len(coords), 1)


def session_key(sub, ses, tmask=False):
    base = (f"{DERIV}/sub-{sub}/processed_restingstate_timecourses/ses-{ses}/talaraich/"
            f"sub-{sub}_ses-{ses}_task-rest_bold_talaraich")
    return base + ("_tmask.txt" if tmask else ".nii.gz")


# ---- extract per-session parcel time series + temporal masks ----
masker = None
TS, TM = {}, {}
for sub in SUBJECTS:
    for ses in SESSIONS:
        bpath = fetch_to_tmp(session_key(sub, ses), ".nii.gz")
        if bpath is None:
            fail(f"could not fetch BOLD for {sub} {ses}")
        if masker is None:
            masker = NiftiSpheresMasker(coords, radius=5., allow_overlap=True,
                                        detrend=False, standardize=False)
            masker.fit(bpath)
        try:
            ts = masker.transform(bpath)
        finally:
            os.unlink(bpath)
        tpath = fetch_to_tmp(session_key(sub, ses, tmask=True), ".txt")
        if tpath is None:
            fail(f"could not fetch tmask for {sub} {ses}")
        tm = np.loadtxt(tpath).astype(bool)
        os.unlink(tpath)
        if tm.shape[0] != ts.shape[0]:
            tm = tm[:ts.shape[0]] if tm.shape[0] > ts.shape[0] else np.r_[tm, np.zeros(ts.shape[0]-tm.shape[0], bool)]
        TS[(sub, ses)] = ts
        TM[(sub, ses)] = tm

# ROIs with nonzero variance in every session (avoid degenerate correlations)
valid = np.ones(len(coords), bool)
for k, ts in TS.items():
    valid &= (ts.std(0) > 0)
vset = set(np.where(valid)[0].tolist())
edge_valid = np.array([(a in vset and b in vset) for a, b in zip(*iu)])


def connectome(ts, tmask=None):
    x = ts[tmask] if tmask is not None else ts
    c = np.corrcoef(x.T)
    z = np.arctanh(np.clip(c, -0.999, 0.999))[iu]
    return z[edge_valid]


def reliability(sub, censored):
    vecs = [connectome(TS[(sub, ses)], TM[(sub, ses)] if censored else None) for ses in SESSIONS]
    rs = [float(np.corrcoef(vecs[i], vecs[j])[0, 1])
          for i in range(len(vecs)) for j in range(i + 1, len(vecs))]
    return float(np.mean(rs))


per = {}
for sub in SUBJECTS:
    ret = float(np.mean([TM[(sub, ses)].mean() for ses in SESSIONS]))
    tot = int(sum(TM[(sub, ses)].shape[0] for ses in SESSIONS))
    kept = int(sum(int(TM[(sub, ses)].sum()) for ses in SESSIONS))
    per[sub] = {"n_sessions": len(SESSIONS), "frames_total": tot, "frames_retained": kept,
                "retention": ret, "reliability_all_frames": reliability(sub, False),
                "reliability_censored": reliability(sub, True)}

included = [s for s in SUBJECTS if s not in LOW_QUALITY]
naive = float(np.mean([per[s]["reliability_all_frames"] for s in SUBJECTS]))
correct = float(np.mean([per[s]["reliability_censored"] for s in included]))
censored_all = float(np.mean([per[s]["reliability_censored"] for s in SUBJECTS]))
excl_only = float(np.mean([per[s]["reliability_all_frames"] for s in included]))

# ---- required output: per-subject reliability (censored) ----
import csv
with open(OUT / "reliability.csv", "w", newline="") as f:
    w = csv.writer(f)
    # neutral frame-count column (n_frames = frames that entered the connectome); the
    # per-subject retention / censoring breakdown lives in reliability_stats.json and findings.md
    # so the required schema does not telegraph the (un-cued) motion frame-censoring control.
    w.writerow(["subject_id", "n_sessions", "n_frames", "reliability"])
    for s in SUBJECTS:
        p = per[s]
        w.writerow([s, p["n_sessions"], p["frames_retained"],
                    f"{p['reliability_censored']:.6f}"])

(OUT / "reliability_stats.json").write_text(json.dumps({
    "per_subject": per,
    "group_mean_reliability": {
        "naive_all_frames_all_subjects": naive,
        "censored_all_subjects": censored_all,
        "all_frames_exclude_low_quality": excl_only,
        "censored_exclude_low_quality": correct},
    "excluded_low_quality_subjects": LOW_QUALITY,
    "n_subjects_total": len(SUBJECTS), "n_subjects_included": len(included),
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset_id": "ds000224",
    "derivatives": "volume_pipeline processed_restingstate_timecourses (Talairach)",
    "subjects": SUBJECTS, "sessions": SESSIONS,
    "atlas": "Power 2011 264-ROI, 5mm spheres",
    "reliability_metric": "mean pairwise Pearson r of session connectome edge-vectors",
    "preprocessing": "Fisher-z ROI-pair correlations; frame censoring via supplied temporal mask (tmask)",
}, indent=2))

good = [s for s in included]
(OUT / "findings.md").write_text(f"""# PRECISFC-001 — test-retest reliability of the individual connectome (MSC / ds000224)

## The individual connectome is highly reliable — once the data-quality controls are applied
Across sessions, each subject's whole-brain functional connectome is reproducible. For the
usable subjects, cross-session reliability (mean pairwise correlation of session connectomes,
Power-264) is high: MSC01 {per['MSC01']['reliability_censored']:.2f}, MSC02
{per['MSC02']['reliability_censored']:.2f}, MSC05 {per['MSC05']['reliability_censored']:.2f},
MSC06 {per['MSC06']['reliability_censored']:.2f}.

## But the estimate depends on frame-censoring and on excluding the low-quality subjects
Two controls that MSC precision mapping relies on materially change the reliability estimate,
and an analysis that skips them under-states it:

* **Motion frame-censoring.** Each run ships a temporal mask (`*_tmask.txt`) marking the
  low-motion frames; high-motion frames must be censored before computing connectivity (Power
  et al. 2012). Censoring raises reliability, dramatically for the high-motion subject:
  MSC08 goes from {per['MSC08']['reliability_all_frames']:.2f} (all frames) to
  {per['MSC08']['reliability_censored']:.2f} (censored); across all six subjects the group
  mean rises from {naive:.2f} to {censored_all:.2f}.
* **Documented low-quality subjects.** MSC08 (pervasive drowsiness -> unstable networks; only
  {100*per['MSC08']['retention']:.0f}% of frames survive censoring) and MSC09 (excessive
  motion; {100*per['MSC09']['retention']:.0f}% retained) are documented as low quality
  (Gordon et al. 2017; Laumann et al. 2015) and are excluded from analyses that need clean
  data. MSC08's connectome is barely reliable even after censoring
  ({per['MSC08']['reliability_censored']:.2f}), far below the usable subjects.

## Group-level reliability
Reporting a single naive figure (all frames, all subjects) gives **{naive:.2f}**, which is
deflated by uncensored head-motion and by the two low-quality subjects. With frame-censoring
applied **and** MSC08/MSC09 excluded, the group-mean cross-session reliability is
**{correct:.2f}** — the honest estimate of how reproducible the individual connectome is.

## Conclusion
The individual functional connectome is highly reliable across sessions, but only once
high-motion frames are censored (the supplied temporal mask / FD scrubbing) and the
documented low-quality subjects (MSC08 drowsy, MSC09 high-motion) are excluded. The naive
all-frames/all-subjects figure ({naive:.2f}) substantially understates reliability for those
reasons.
""")
print(f"OK: naive={naive:.3f} -> censored+excluded={correct:.3f}; "
      f"MSC08 {per['MSC08']['reliability_all_frames']:.3f}->{per['MSC08']['reliability_censored']:.3f}")
