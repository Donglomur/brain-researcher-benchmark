"""Reference solution for EVBOUND-001.

Deliverable: from the human medial-temporal-lobe (MTL) single-neuron recordings during the
cognitive-boundary video-encoding task (DANDI 000207, Zheng et al. 2022), report how well the MTL
population discriminates a cognitive-boundary cut from a no-boundary cut -- the mean cross-validated
population-decoding ROC AUC (boundary vs no-boundary), averaged over sessions.

During encoding the subject watches 90 short film clips. Each clip contains a single film cut. In a
"no-boundary" (NB) clip the cut continues the same ongoing event; in a "soft-boundary" (SB) clip the
cut moves to a new moment within the same scene; in a "hard-boundary" (HB) clip the cut jumps to an
entirely different scene. Soft and hard cuts are cognitive boundaries; the no-boundary cut is not.
`stimCategory` is 0 = NB, 1 = SB, 2 = HB, and `boundary1_time` is the time of the cut. For each
session we build a population feature vector -- one post-cut firing rate per MTL neuron -- for every
clip, and train a cross-validated linear decoder to classify boundary (SB or HB) vs no-boundary (NB).

The correct estimate keeps every step that looks at the class labels -- in particular any selection of
"the neurons that carry a boundary signal" -- INSIDE the cross-validation, fit on the training folds
only. If you instead rank/select the boundary-informative neurons on the FULL set of clips and then
cross-validate the decoder restricted to those neurons, the held-out folds have already been used to
choose the features: this selection leakage inflates the cross-validated AUC (Kriegeskorte et al.
2009; the classic "selection outside the CV loop" bias). Decoding from all MTL neurons, or selecting
neurons within each training fold, removes the leak.

Validated ground truth (DANDI 000207, per-session MTL population = hippocampus + amygdala units by
electrode location; encoding phase; per-clip firing rate over the [0.0, 1.5] s window after the cut;
standardized features; L2 logistic regression; repeated stratified 5-fold CV; ROC AUC of boundary vs
no-boundary from the held-out decision scores; mean over sessions):
  n sessions                            = 19
  CORRECT mean CV decoding AUC, all neurons / selection inside the CV   = ~0.60  <-- reported
  LEAKY   mean CV decoding AUC, boundary-informative neurons selected on ALL clips then CV = ~0.70
Boundary vs no-boundary is genuinely decodable: the honest AUC (~0.60) is clearly above chance (0.5).
But selecting the neurons on the same clips used to test the decoder inflates it to ~0.70. A reported
~0.70 fails the match.
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

DANDISET = "000207"
REGION_KEYS = ("hippocampus", "amygdala")   # medial temporal lobe (matched case-insensitively)
WIN = (0.0, 1.5)          # s after the cut (boundary1_time)
N_FOLDS = 5
N_REPEATS = 20
SEED = 0


def fail(reason):
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason, "dandiset": DANDISET}, indent=2))
    (OUT / "results.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    import h5py
    import remfile
    from dandi.dandiapi import DandiAPIClient
    from pynwb import NWBHDF5IO
    from scipy.stats import rankdata
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import StratifiedKFold
except Exception as e:  # pragma: no cover
    fail(f"missing dependency: {e}")


def roc_auc(y, score):
    """ROC AUC that class-1 (boundary) has higher decision score than class-0 (no-boundary)."""
    y = np.asarray(y).astype(int)
    npos = int(y.sum())
    nneg = len(y) - npos
    if npos == 0 or nneg == 0:
        return np.nan
    r = rankdata(score)
    return float((r[y == 1].sum() - npos * (npos + 1) / 2.0) / (npos * nneg))


def session_decode_auc(X, y, seed):
    """Repeated stratified 5-fold population-decoding AUC using ALL neurons (selection, if any, must
    stay inside the CV; here the honest reference uses the full neuron set)."""
    aucs = []
    for rep in range(N_REPEATS):
        skf = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=seed + rep)
        scores = np.zeros(len(y))
        for tr, te in skf.split(X, y):
            sc = StandardScaler().fit(X[tr])
            clf = LogisticRegression(max_iter=1000, C=1.0).fit(sc.transform(X[tr]), y[tr])
            scores[te] = clf.decision_function(sc.transform(X[te]))
        a = roc_auc(y, scores)
        if not np.isnan(a):
            aucs.append(a)
    return float(np.mean(aucs)) if aucs else np.nan


def collect_sessions():
    """Stream each session's encoding-phase MTL population. Return per-session (X, y): X = clips x
    MTL neurons post-cut firing rate, y = 1 for a boundary (SB/HB) clip, 0 for no-boundary (NB).
    Only the MTL units' spike_times and the encoding table are read, so streaming stays light."""
    sessions = []
    with DandiAPIClient() as client:
        ds = client.get_dandiset(DANDISET, "draft")
        paths = sorted(a.path for a in ds.get_assets() if a.path.endswith(".nwb"))
        if not paths:
            fail(f"no NWB assets in dandiset {DANDISET}")
        for p in paths:
            try:
                url = ds.get_asset_by_path(p).get_content_url(follow_redirects=1, strip_query=False)
                io = NWBHDF5IO(file=h5py.File(remfile.File(url), "r"), load_namespaces=True)
                nwb = io.read()
                enc = nwb.intervals["encoding_table"].to_dataframe()
                cut = enc["boundary1_time"].values.astype(float)
                cat = enc["stimCategory"].values.astype(int)
                ok = ~np.isnan(cut)
                cut, cat = cut[ok], cat[ok]
                keep = np.isin(cat, (0, 1, 2))
                cut, cat = cut[keep], cat[keep]
                y = (cat != 0).astype(int)   # SB or HB = boundary
                if len(y) < 20 or y.sum() < 5 or (len(y) - y.sum()) < 5:
                    continue
                el = nwb.electrodes.to_dataframe()
                u = nwb.units
                cols = []
                for i in range(len(u.id)):
                    eidx = u["electrodes"][i].index.values
                    locs = el.loc[eidx, "location"].values
                    loc = str(locs[0]).lower() if len(locs) else ""
                    if not any(k in loc for k in REGION_KEYS):
                        continue
                    st = np.asarray(u["spike_times"][i]).astype(float)
                    fr = (np.searchsorted(st, cut + WIN[1]) - np.searchsorted(st, cut + WIN[0])) \
                        / (WIN[1] - WIN[0])
                    cols.append(fr.astype(float))
                if len(cols) < 3:
                    continue
                X = np.array(cols).T   # clips x neurons
                sessions.append((p, X, y))
            except Exception:
                continue
    return sessions


sessions = collect_sessions()
if len(sessions) < 8:
    fail(f"too few sessions with MTL populations ({len(sessions)}) -- streaming may have failed")

per_session = []
n_neurons_total = 0
for p, X, y in sessions:
    a = session_decode_auc(X, y, SEED)
    if not np.isnan(a):
        per_session.append(a)
        n_neurons_total += X.shape[1]
decode_auc = float(np.mean(per_session)) if per_session else float("nan")

results = {
    # headline: honest cross-validated population decoding AUC, boundary vs no-boundary
    "boundary_decoding_auc": round(decode_auc, 4),
    "n_sessions": len(per_session),
    "n_mtl_neurons_total": int(n_neurons_total),
    "per_session_auc": [round(a, 4) for a in per_session],
    "params": {
        "region": "MTL (hippocampus + amygdala) by electrode location",
        "phase": "encoding",
        "response_window_s": list(WIN),
        "labels": "boundary = soft/hard-boundary clip (stimCategory 1 or 2); "
                  "no-boundary = stimCategory 0",
        "features": "one post-cut firing rate per MTL neuron; standardized within the CV",
        "decoder": "L2 logistic regression (C=1)",
        "cross_validation": "%d repeats of stratified %d-fold; AUC from held-out decision scores; "
                            "any neuron selection performed inside the CV (reference uses all neurons)"
                            % (N_REPEATS, N_FOLDS),
        "aggregation": "mean AUC across sessions",
    },
}
(OUT / "results.json").write_text(json.dumps(results, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dandiset": DANDISET, "n_sessions": len(per_session),
    "n_mtl_neurons_total": int(n_neurons_total),
    "region": "hippocampus + amygdala (MTL)", "phase": "encoding",
    "response_window_s": list(WIN),
    "decoder": "L2 logistic regression, standardized features",
    "cross_validation": "repeated stratified 5-fold, selection inside CV (reference uses all neurons)",
    "decoding_auc_definition": "mean over sessions of the cross-validated ROC AUC classifying "
                               "boundary (SB/HB) vs no-boundary (NB) clips from the MTL population",
}, indent=2))

(OUT / "findings.md").write_text(
    f"# Population decoding of cognitive boundaries in human MTL -- DANDI 000207\n\n"
    f"For each of {len(per_session)} encoding sessions we trained a cross-validated linear decoder to "
    f"classify boundary (soft/hard) vs no-boundary film cuts from the medial-temporal-lobe population "
    f"(hippocampus + amygdala), using one post-cut firing rate per neuron.\n\n"
    f"The mean cross-validated decoding ROC AUC is **{decode_auc:.3f}**, clearly above chance (0.5), "
    f"so the MTL population carries a genuine cognitive-boundary signal. This estimate keeps any "
    f"selection of boundary-informative neurons inside the cross-validation (or uses all neurons); "
    f"choosing the neurons on the full set of clips before cross-validating would inflate the AUC "
    f"through selection leakage.\n\n"
    f"Reported headline: mean cross-validated boundary-vs-no-boundary decoding AUC = "
    f"**{decode_auc:.3f}**.\n")

print(f"n_sessions={len(per_session)} n_neurons={n_neurons_total} decode_auc={decode_auc:.4f} "
      f"per_session={[round(a,3) for a in per_session]}")
