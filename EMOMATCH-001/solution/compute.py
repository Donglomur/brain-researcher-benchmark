"""Reference solution for EMOMATCH-001.

Reproduce the group-level activation for the emotion-matching (Hariri-style faces>shapes)
task in the AOMIC PIOP2 dataset (OpenNeuro ds002790, Snoek et al. 2021), using the released
fMRIPrep derivatives (volumetric MNI152NLin2009cAsym preproc BOLD), and report the
emotion-processing network.

The honest reference does what a mature analyst VOLUNTEERS but the task never asks: it checks
whether the "emotion" activation is confounded by TIME ON TASK / reaction time. In the
emotion-matching task the emotion (face) trials take much longer to respond to than the
orientation-control (shape) trials (mean RT ~1.76 s vs ~1.24 s; emotion slower in ~97% of
subjects, paired Cohen d ~1.8). Because the two conditions differ so strongly in response
time / difficulty, a first-level model that does not account for the reaction-time difference
(constant-duration epochs) attributes the extra "time on task" of the slower emotion trials to
the emotion regressor. The result is widespread apparent "emotion" activation in domain-general
cognitive-control / salience regions (fronto-parietal cortex, anterior insula, dorsal
attention). That activation is a difficulty / time-on-task confound (Grinband et al. 2008;
Yarkoni et al. 2009): when trial duration (reaction time) is modelled with a variable-epoch
GLM, the cognitive-control "emotion" effect collapses (and anterior insula reverses), whereas
the genuinely face/emotion-selective response in the AMYGDALA and FUSIFORM survives essentially
unchanged. So the broad "emotion network" is largely a reaction-time artifact; only the
amygdala/fusiform effect is emotion-specific.

Validated numbers (ds002790 fMRIPrep emomatching, Schaefer-100/7-network cortex + amygdala &
fusiform spheres, one-sample group t across the processed subjects; NAIVE = constant-epoch,
RT = variable-epoch [duration = reaction time]):
  PREMISE  emotion RT ~1.76 s vs control ~1.24 s (paired t ~9, d ~1.8; emotion slower ~97%)
  AMYGDALA emotion>control  survives  (naive t ~ +5..9  ->  RT t ~ +5..9, |change| < ~10%)
  FUSIFORM emotion>control  survives  (attenuates modestly, still strongly significant)
  CONTROL/SALIENCE/DORSATTN network emotion>control  collapses under RT control
           (naive: significantly positive  ->  RT: n.s. / reverses)
"""
import csv
import io
import json
import os
import sys
import tempfile
import time
import urllib.request
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)

S3 = "https://s3.amazonaws.com/openneuro.org/ds002790"
FP = S3 + "/derivatives/fmriprep"
TASK = "emomatching"
TR = 2.0
MAX_SUBJECTS = int(os.environ.get("EMOMATCH_MAX_SUBJECTS", "20"))
MIN_SUBJECTS = 14

# a priori face/emotion-selective ROIs (MNI mm) -- hypothesised to be emotion-specific and to
# SURVIVE reaction-time control
FACE_ROIS = {
    "amygdala_L": (-23, -5, -19), "amygdala_R": (23, -5, -19),
    "fusiform_L": (-40, -52, -18), "fusiform_R": (42, -52, -18),
}
# domain-general cognitive-control / salience / dorsal-attention ROIs (MNI mm) -- these are the
# regions whose apparent "emotion" response is a time-on-task (reaction-time) confound
CONTROL_ROIS = {
    "dACC": (0, 20, 38), "aInsula_L": (-34, 20, 4), "aInsula_R": (36, 22, 2),
    "dlPFC_L": (-44, 20, 30), "dlPFC_R": (46, 22, 28),
    "IPS_L": (-28, -58, 46), "IPS_R": (30, -56, 46),
}
ROIS = {**FACE_ROIS, **CONTROL_ROIS}
# nuisance regressors from the fMRIPrep confounds table
CONF_COLS = ["trans_x", "trans_y", "trans_z", "rot_x", "rot_y", "rot_z",
             "a_comp_cor_00", "a_comp_cor_01", "a_comp_cor_02", "a_comp_cor_03",
             "a_comp_cor_04", "white_matter", "csf"]


def fail(reason):
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason, "dataset_id": "ds002790"}, indent=2))
    (OUT / "group_stats.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


def fetch(url, dest=None, timeout=300, retries=5):
    if dest and os.path.exists(dest) and os.path.getsize(dest) > 0:
        return dest
    for a in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
            if dest:
                with open(dest, "wb") as f:
                    f.write(data)
                return dest
            return data
        except Exception:
            time.sleep(2 * (a + 1))
    return None


try:
    import pandas as pd
    from nilearn import datasets
    from nilearn.glm.first_level import make_first_level_design_matrix
    from nilearn.maskers import NiftiLabelsMasker, NiftiSpheresMasker
    from scipy import stats
except Exception as e:  # pragma: no cover
    fail(f"import failed: {e}")

# ---- cohort ----
part = fetch(S3 + "/participants.tsv")
if part is None:
    fail("could not fetch ds002790 participants.tsv")
rows = list(csv.DictReader(io.StringIO(part.decode()), delimiter="\t"))
subjects = [r["participant_id"] for r in rows]


def has_task(sub):
    url = f"{FP}/{sub}/func/{sub}_task-{TASK}_acq-seq_space-MNI152NLin2009cAsym_desc-preproc_bold.nii.gz"
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "curl/8"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status == 200
    except Exception:
        return False


# pick the first MAX_SUBJECTS subjects that actually have an emomatching run
usable = []
for s in subjects:
    if has_task(s):
        usable.append(s)
    if len(usable) >= MAX_SUBJECTS:
        break
if len(usable) < MIN_SUBJECTS:
    fail(f"too few subjects with an {TASK} run ({len(usable)})")

# ---- atlases ----
sch = datasets.fetch_atlas_schaefer_2018(n_rois=100, yeo_networks=7, resolution_mm=2)
labels = [l.decode() if isinstance(l, bytes) else l for l in sch["labels"]]
# some nilearn versions prepend a "Background" entry; drop it so labels align 1:1 with the
# 100 parcels the masker extracts (map integers 1..100).
if labels and str(labels[0]).lower() == "background":
    labels = labels[1:]


def net_of(label):
    # labels look like '7Networks_LH_Cont_Par_1'
    parts = label.split("_")
    return parts[2] if len(parts) > 2 else "Other"


networks = [net_of(l) for l in labels]
cortex_masker = NiftiLabelsMasker(sch["maps"], standardize=False, detrend=False)
roi_masker = NiftiSpheresMasker(list(ROIS.values()), radius=6, standardize=False, detrend=False)


def load_events(sub):
    b = fetch(f"{S3}/{sub}/func/{sub}_task-{TASK}_acq-seq_events.tsv")
    if b is None:
        return None
    rd = list(csv.DictReader(io.StringIO(b.decode()), delimiter="\t"))
    ev = []
    for r in rd:
        tt = r["trial_type"]
        if tt not in ("emotion", "control"):
            continue
        rt = r.get("response_time", "n/a")
        rt = float(rt) if rt not in ("n/a", "", "NaN", None) else np.nan
        ev.append((float(r["onset"]), tt, rt))
    return ev


def design(ev, nvol, model, medrt):
    frame_times = np.arange(nvol) * TR
    onsets = [e[0] for e in ev]
    ttypes = [e[1] for e in ev]
    rts = [e[2] for e in ev]
    if model == "naive":       # constant-duration epoch: ignores the RT difference
        durs = [medrt] * len(ev)
    else:                      # variable epoch: duration = per-trial reaction time
        durs = [(r if not np.isnan(r) else medrt) for r in rts]
    events = pd.DataFrame({"onset": onsets, "trial_type": ttypes, "duration": durs})
    dm = make_first_level_design_matrix(frame_times, events, hrf_model="spm",
                                        high_pass=0.008, drift_model="cosine")
    return dm


CACHE = os.environ.get("EMOMATCH_CACHE")  # dev only: keep BOLD files to allow fast re-runs


def process(sub):
    if CACHE:
        os.makedirs(CACHE, exist_ok=True)
        tmp = os.path.join(CACHE, f"{sub}_emo_bold.nii.gz")
    else:
        tmp = tempfile.NamedTemporaryFile(suffix=".nii.gz", delete=False).name
    bold = fetch(f"{FP}/{sub}/func/{sub}_task-{TASK}_acq-seq_space-MNI152NLin2009cAsym_desc-preproc_bold.nii.gz", dest=tmp)
    cb = fetch(f"{FP}/{sub}/func/{sub}_task-{TASK}_acq-seq_desc-confounds_regressors.tsv")
    ev = load_events(sub)
    if bold is None or cb is None or ev is None:
        if not CACHE and os.path.exists(tmp):
            os.unlink(tmp)
        return None
    rd = list(csv.DictReader(io.StringIO(cb.decode()), delimiter="\t"))
    nvol = len(rd)
    conf = np.array([[float(r[c]) if r.get(c, "n/a") not in ("n/a", "", "NaN", None) else np.nan
                      for c in CONF_COLS] for r in rd])
    for j in range(conf.shape[1]):
        m = np.nanmean(conf[:, j])
        conf[np.isnan(conf[:, j]), j] = m if not np.isnan(m) else 0.0
    try:
        Yc = cortex_masker.fit_transform(tmp)          # nvol x 100
        Yr = roi_masker.fit_transform(tmp)             # nvol x len(ROIS)
    except Exception:
        if not CACHE and os.path.exists(tmp):
            os.unlink(tmp)
        return None
    if not CACHE and os.path.exists(tmp):
        os.unlink(tmp)
    Y = np.hstack([Yc, Yr])                              # nvol x (100+len(ROIS))
    # standardise each column to make the emotion-control effect comparable across regions
    Y = (Y - Y.mean(0)) / (Y.std(0) + 1e-8)
    valid_rt = [e[2] for e in ev if not np.isnan(e[2])]
    medrt = float(np.median(valid_rt)) if valid_rt else 1.5
    emo_rt = np.mean([e[2] for e in ev if e[1] == "emotion" and not np.isnan(e[2])])
    con_rt = np.mean([e[2] for e in ev if e[1] == "control" and not np.isnan(e[2])])
    out = {"rt_emotion": float(emo_rt), "rt_control": float(con_rt)}
    for model in ("naive", "rt"):
        dm = design(ev, nvol, model, medrt)
        C = pd.DataFrame(conf, columns=CONF_COLS, index=dm.index)
        X = pd.concat([dm.drop(columns=[c for c in dm.columns if c == "constant"]), C], axis=1)
        X["constant"] = 1.0
        cols = list(X.columns)
        cvec = np.zeros(len(cols))
        cvec[cols.index("emotion")] = 1.0
        cvec[cols.index("control")] = -1.0
        beta, _, _, _ = np.linalg.lstsq(X.values, Y, rcond=None)
        out[model] = cvec @ beta                        # (100+len(ROIS),) emotion-control effect
    return sub, out


results = []
with ThreadPoolExecutor(max_workers=3) as ex:
    for r in ex.map(process, usable):
        if r is not None:
            results.append(r)
            sys.stderr.write(f"processed {r[0]}\n")

if len(results) < MIN_SUBJECTS:
    fail(f"only {len(results)} subjects processed")

pids = [r[0] for r in results]
naive = np.array([r[1]["naive"] for r in results])      # nsub x 104
rt = np.array([r[1]["rt"] for r in results])
emo_rt = np.array([r[1]["rt_emotion"] for r in results])
con_rt = np.array([r[1]["rt_control"] for r in results])
n = len(pids)
roi_idx = {k: len(labels) + j for j, k in enumerate(ROIS)}
FACE_KEYS = list(FACE_ROIS.keys())
CONTROL_KEYS = list(CONTROL_ROIS.keys())


def group_t(mat, idx):
    v = mat[:, idx].mean(1) if len(idx) > 1 else mat[:, idx[0]]
    t, p = stats.ttest_1samp(v, 0.0)
    return float(v.mean()), float(t), float(p)


# ---- per-subject required output (naive-model emotion>control in the a priori face ROIs and in
#      the cognitive-control ROIs) -- no reaction-time column, so the confound stays un-cued ----
with open(OUT / "activation.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["subject_id", "amygdala_emotion_gt_control", "fusiform_emotion_gt_control",
                "control_rois_emotion_gt_control"])
    for i, p in enumerate(pids):
        amy = np.mean([naive[i, roi_idx["amygdala_L"]], naive[i, roi_idx["amygdala_R"]]])
        ffa = np.mean([naive[i, roi_idx["fusiform_L"]], naive[i, roi_idx["fusiform_R"]]])
        ctl = np.mean([naive[i, roi_idx[k]] for k in CONTROL_KEYS])
        w.writerow([p, f"{amy:.5f}", f"{ffa:.5f}", f"{ctl:.5f}"])

# ---- group statistics: naive vs RT-controlled, per a priori ROI and per network ----
stats_out = {"n_subjects": n,
             "model_naive": "constant-duration epoch (ignores reaction-time difference)",
             "model_rt": "variable-duration epoch (duration = per-trial reaction time)",
             "reaction_time": {}, "face_rois": {}, "control_rois": {}, "networks": {}}

# premise: the reaction-time difference between the two conditions
d = emo_rt - con_rt
tt = stats.ttest_rel(emo_rt, con_rt)
stats_out["reaction_time"] = {
    "emotion_mean_s": float(emo_rt.mean()), "control_mean_s": float(con_rt.mean()),
    "difference_s": float(d.mean()), "paired_t": float(tt.statistic), "paired_p": float(tt.pvalue),
    "frac_emotion_slower": float(np.mean(emo_rt > con_rt)), "cohen_d": float(d.mean() / d.std())}


def add_roi(dst, name, keys):
    idx = [roi_idx[k] for k in keys]
    mn_n, t_n, p_n = group_t(naive, idx)
    mn_r, t_r, p_r = group_t(rt, idx)
    pct = 100.0 * (mn_r - mn_n) / abs(mn_n) if mn_n != 0 else float("nan")
    dst[name] = {"naive": {"mean": mn_n, "t": t_n, "p": p_n},
                 "rt_controlled": {"mean": mn_r, "t": t_r, "p": p_r}, "pct_change": float(pct)}


for k in FACE_KEYS:
    add_roi(stats_out["face_rois"], k, [k])
add_roi(stats_out["face_rois"], "amygdala", ["amygdala_L", "amygdala_R"])
add_roi(stats_out["face_rois"], "fusiform", ["fusiform_L", "fusiform_R"])
for k in CONTROL_KEYS:
    add_roi(stats_out["control_rois"], k, [k])
add_roi(stats_out["control_rois"], "control_rois_mean", CONTROL_KEYS)

for nw in sorted(set(networks)):
    idx = [i for i, x in enumerate(networks) if x == nw]
    mn_n, t_n, p_n = group_t(naive, idx)
    mn_r, t_r, p_r = group_t(rt, idx)
    stats_out["networks"][nw] = {"n_parcels": len(idx),
                                 "naive": {"mean": mn_n, "t": t_n, "p": p_n},
                                 "rt_controlled": {"mean": mn_r, "t": t_r, "p": p_r}}
(OUT / "group_stats.json").write_text(json.dumps(stats_out, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset_id": "ds002790",
    "derivatives": "fMRIPrep (AOMIC PIOP2), task-emomatching, space-MNI152NLin2009cAsym preproc BOLD",
    "n_subjects": n, "TR_s": TR,
    "atlas": "Schaefer-2018 100-parcel / 7-network cortex + amygdala, fusiform and "
             "cognitive-control (dACC, anterior insula, dlPFC, IPS) 6mm spheres",
    "first_level": "SPM HRF; nuisance = 6 motion + aCompCor(5) + WM + CSF; cosine high-pass 0.008 Hz",
    "contrast": "emotion > control (emotion-matching > orientation-matching)",
    "models": {"naive": "constant-duration epochs", "rt": "variable-duration epochs (=reaction time)"},
}, indent=2))

amy = stats_out["face_rois"]["amygdala"]
ffa = stats_out["face_rois"]["fusiform"]
ctl = stats_out["control_rois"]["control_rois_mean"]
ains = stats_out["control_rois"]["aInsula_R"]
dlpfc = stats_out["control_rois"]["dlPFC_L"]
ips = stats_out["control_rois"]["IPS_R"]
rtd = stats_out["reaction_time"]
(OUT / "findings.md").write_text(f"""# EMOMATCH-001 — emotion-matching activation in AOMIC PIOP2 (ds002790)

## An apparent broad "emotion network" is present (naive model)
Fitting a standard first-level GLM (emotion-matching > orientation-control, i.e. faces>shapes)
with constant-duration epochs on the ds002790 fMRIPrep emomatching data ({n} subjects),
the emotion contrast activates not only the **amygdala** (group t = {amy['naive']['t']:.2f}) and
**fusiform** face region (t = {ffa['naive']['t']:.2f}), but also **domain-general cognitive-control
/ salience / dorsal-attention** regions — anterior insula (t = {ains['naive']['t']:.2f}), dorsolateral
prefrontal cortex (t = {dlpfc['naive']['t']:.2f}) and intraparietal sulcus (t = {ips['naive']['t']:.2f});
mean over the cognitive-control ROIs t = {ctl['naive']['t']:.2f} (effect {ctl['naive']['mean']:+.3f}).
Taken at face value this looks like a distributed "emotion network".

## But the broad activation is a time-on-task (reaction-time) confound
The emotion (face) trials take **far longer** to respond to than the orientation-control (shape)
trials: mean RT {rtd['emotion_mean_s']:.2f} s vs {rtd['control_mean_s']:.2f} s (difference
{rtd['difference_s']:.2f} s; emotion slower in {100*rtd['frac_emotion_slower']:.0f}% of subjects;
paired t = {rtd['paired_t']:.1f}, Cohen d = {rtd['cohen_d']:.2f}). A constant-duration model does
not absorb this difference, so the extra time-on-task of the slower emotion trials is attributed
to the emotion regressor and shows up as "emotion" activation in exactly the domain-general
regions that track task difficulty/effort (Grinband et al. 2008; Yarkoni et al. 2009).

Re-fitting with a **variable-epoch model (trial duration = reaction time)** dissociates the two:

* the **cognitive-control** ROIs **collapse**: mean t {ctl['naive']['t']:.2f} ->
  {ctl['rt_controlled']['t']:.2f} (effect {ctl['naive']['mean']:+.3f} -> {ctl['rt_controlled']['mean']:+.3f});
  e.g. IPS t {ips['naive']['t']:.2f} -> {ips['rt_controlled']['t']:.2f}, dlPFC t {dlpfc['naive']['t']:.2f} ->
  {dlpfc['rt_controlled']['t']:.2f}, and the anterior-insula effect **reverses**
  (t {ains['naive']['t']:.2f} -> {ains['rt_controlled']['t']:.2f}).
* the **amygdala** effect is essentially unchanged (t {amy['naive']['t']:.2f} ->
  {amy['rt_controlled']['t']:.2f}; {amy['pct_change']:+.0f}% change) and the **fusiform**
  face effect survives (t {ffa['naive']['t']:.2f} -> {ffa['rt_controlled']['t']:.2f}).

## Conclusion
The amygdala/fusiform response is a genuine, emotion/face-selective effect that is robust to
reaction-time control. The broader fronto-parietal / insular "emotion network", however, is
**largely a time-on-task (reaction-time) artifact** — emotion trials simply take longer — and it
does not survive modelling the reaction-time difference. It should not be reported as an
emotion-specific network on these data.
""")
print(f"OK n={n}: amygdala t {amy['naive']['t']:.2f}->{amy['rt_controlled']['t']:.2f} ; "
      f"control-ROIs t {ctl['naive']['t']:.2f}->{ctl['rt_controlled']['t']:.2f} ; "
      f"aIns_R {ains['naive']['t']:.2f}->{ains['rt_controlled']['t']:.2f} ; "
      f"RT emo {rtd['emotion_mean_s']:.2f} vs con {rtd['control_mean_s']:.2f}")
