"""Reference (oracle) for WEIGHTMAPS-001 — classifier weights are NOT the affected connections
(the forward-vs-backward / interpretation-of-weight-vectors problem; Haufe et al. 2014).

Paper anchor: Haufe et al. 2014, NeuroImage (10.1016/j.neuroimage.2013.10.067, "On the interpretation
of weight vectors of linear models in multivariate neuroimaging"). The weight vector of a
discriminative (BACKWARD) model does NOT indicate which features carry the signal: a large weight can
sit on a noise-cancelling ("suppressor") feature with no group difference, and a genuinely affected
feature can get a near-zero weight. To read out which features are actually different between groups,
the weights must be transformed to the FORWARD / activation pattern A = Cov(X) w (Haufe transform), or
one uses univariate group statistics. This applies identically to connectome classifiers and to GNN
edge/node saliency (a backward model in disguise).

The task (un-cued) asks: train a classifier to separate autism from controls on ABIDE connectivity,
then identify which CONNECTIONS are most affected in autism from the trained model. The naive move is
to report the top-magnitude classifier WEIGHTS as the affected connections. This reference does the
honest thing it is never told to do: it estimates classifier performance with NESTED cross-validation
(inner grid over C), then VOLUNTEERS the check the task never asks — the raw weight ranking barely
matches the true per-edge group difference (Spearman|w| vs |effect| ~ 0.17; many top-weighted edges
have NO group difference; the truly most-affected edges rank near the BOTTOM by weight), whereas the
Haufe FORWARD pattern A = Cov(X) w recovers the affected edges (Spearman ~ 0.96). It OUTPUTS the real
top affected connections (from the forward pattern) AND, for contrast, the misleading top-weighted
connections. Reads only the packaged local .npz (no network).

Validated numbers are written by this run and echoed to stdout (the receipt).
"""
import json
import os
import sys
import warnings
from collections import Counter
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")  # benign lbfgs/overflow warnings on the p>>n separable connectome fit

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)
DATA = Path(os.environ.get("BUNDLE_DIR", str(Path(__file__).resolve().parent.parent / "data"))) / "cc200_interp.npz"
K = 20          # how many top connections to list in each readout
NPARC = 200     # Craddock-200 parcellation


def fail(reason):
    (OUT / "affected_connections.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason, "dataset": "ABIDE"}, indent=2))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline
    from sklearn.model_selection import StratifiedKFold, GridSearchCV
    from sklearn.metrics import roc_auc_score
    from scipy.stats import ttest_ind, spearmanr, t as tdist
except Exception as e:  # pragma: no cover
    fail(f"import failed: {e}")

try:
    d = np.load(DATA, allow_pickle=True)
    X = np.nan_to_num(d["X"].astype(np.float64), nan=0.0, posinf=0.0, neginf=0.0)  # flat-ROI edges -> 0
    y = d["y"].astype(int)                                  # diagnosis: 1 = ASD, 2 = TD
except Exception as e:
    fail(f"could not load packaged connectomes: {e}")
if X.shape[0] < 200:
    fail(f"only {X.shape[0]} usable subjects")

asd = (y == 1).astype(int)                                  # 1 = autism, 0 = control
n, P = X.shape

# ---- honest classifier performance: NESTED cross-validation (inner grid over C) ----
Cs = [0.01, 0.1, 1.0]
outer = StratifiedKFold(5, shuffle=True, random_state=0)
aucs, picked = [], []
for tr, te in outer.split(X, asd):
    gs = GridSearchCV(
        make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000)),
        {"logisticregression__C": Cs},
        cv=StratifiedKFold(3, shuffle=True, random_state=1), scoring="roc_auc", n_jobs=-1)
    gs.fit(X[tr], asd[tr])
    aucs.append(float(roc_auc_score(asd[te], gs.predict_proba(X[te])[:, 1])))
    picked.append(gs.best_params_["logisticregression__C"])
cv_auc, cv_auc_sd = float(np.mean(aucs)), float(np.std(aucs))
Cbest = Counter(picked).most_common(1)[0][0]

# ---- discriminative (BACKWARD) model at the CV-selected C, on all subjects ----
scaler = StandardScaler().fit(X)
Xs = np.nan_to_num(scaler.transform(X), nan=0.0, posinf=0.0, neginf=0.0)
clf = LogisticRegression(C=Cbest, max_iter=3000).fit(Xs, asd)
w = np.nan_to_num(clf.coef_.ravel())

# ---- ground-truth per-edge group difference (univariate): t-statistic and p ----
tvals = np.nan_to_num(ttest_ind(X[asd == 1], X[asd == 0], axis=0).statistic)
pvals = 2 * tdist.sf(np.abs(tvals), n - 2)

# ---- FORWARD / activation pattern (Haufe): A = Cov(Xs) w, in the SAME (standardized) feature space
#      the weights live in; computed WITHOUT ever forming the P x P covariance ----
Xsc = Xs - Xs.mean(0)
with np.errstate(invalid="ignore", over="ignore"):
    A = np.nan_to_num((Xsc.T @ (Xsc @ w)) / (n - 1))

sp_weight = float(spearmanr(np.abs(w), np.abs(tvals)).correlation)     # backward: unrelated (~0.17)
sp_forward = float(spearmanr(np.abs(A), np.abs(tvals)).correlation)    # forward: recovers it (~0.96)

top_w = np.argsort(np.abs(w))[::-1][:50]
n_null_in_top = int((pvals[top_w] > 0.05).sum())                       # top-weighted edges with NO group diff
true_top = np.argsort(np.abs(tvals))[::-1][:50]                        # the genuinely most-affected edges
weight_rank = np.argsort(np.argsort(np.abs(w)))                        # 0 = smallest |weight|
median_weight_rank_of_affected = float(np.median(weight_rank[true_top]))
overlap_w = int(len(set(top_w[:50]) & set(true_top)))                  # weight top-50 ∩ true top-50
overlap_A = int(len(set(np.argsort(np.abs(A))[::-1][:50]) & set(true_top)))  # forward top-50 ∩ true top-50

# edge index -> ROI pair (upper triangle of the 200x200 connectome)
iu = np.triu_indices(NPARC, 1)


def conn(k):
    return {"pair": [int(iu[0][k]), int(iu[1][k])], "group_t": float(tvals[k]),
            "group_p": float(pvals[k]), "weight_rank_of_19900": int(weight_rank[k])}


# the REAL top affected connections (read from the forward pattern) ...
top_A_idx = np.argsort(np.abs(A))[::-1][:K]
top_affected = [{**conn(k), "forward_pattern": float(A[k])} for k in top_A_idx]
# ... vs the MISLEADING top-weighted connections (the naive readout)
top_weighted = [{**conn(k), "weight": float(w[k])} for k in top_w[:K]]

(OUT / "affected_connections.json").write_text(json.dumps({
    "dataset": "ABIDE (rois_cc200), packaged bundle", "atlas": "Craddock-200 (cc200)",
    "n_subjects": int(n), "n_edges": int(P),
    "classifier": "L2 logistic regression on standardized FC edges (C via nested CV)",
    "cv_scheme": "nested (outer 5-fold; inner 3-fold grid over C)",
    "cv_mean_auc": cv_auc, "cv_auc_sd": cv_auc_sd, "selected_C": float(Cbest),
    "spearman_absweight_vs_absgroupeffect": sp_weight,
    "spearman_absforwardpattern_vs_absgroupeffect": sp_forward,
    "n_top50_weighted_edges_with_no_group_difference": n_null_in_top,
    "median_weight_rank_of_50_most_affected_edges": median_weight_rank_of_affected,
    "top50_weight_overlap_with_true_affected": overlap_w,
    "top50_forwardpattern_overlap_with_true_affected": overlap_A,
    "top_affected_connections": top_affected,     # <- the real answer (forward pattern / univariate)
    "top_weighted_connections": top_weighted,     # <- the misleading readout (raw weights)
    "note": "top affected connections are read from the FORWARD/activation pattern (Cov(X)*w, Haufe "
            "2014) or univariate group statistics, NOT from the raw classifier weights",
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset": "ABIDE (ABIDE_pcp, cpac, rois_cc200), packaged bundle",
    "atlas": "Craddock-200", "n_subjects": int(n),
    "cv_scheme": "nested (outer 5-fold, inner 3-fold grid over C); mean AUC reported",
    "method": "logistic-regression connectome classifier; raw weights (backward) vs Haufe forward "
              "pattern A=Cov(X)*w vs univariate per-edge group t-tests",
}, indent=2))

(OUT / "findings.md").write_text(f"""# WEIGHTMAPS-001 — which connections are "affected" in autism?

A logistic-regression connectome classifier on ABIDE ({n} subjects, {P} edges) separates autism from
controls above chance — nested-CV mean AUC = **{cv_auc:.2f}** (±{cv_auc_sd:.2f}). It is tempting to
read the largest-magnitude classifier **weights** as the autism-affected connections — but that is
wrong.

## Classifier weights are NOT the affected connections
- Correlation of |classifier weight| with the true per-edge group difference (|t|, ASD vs TDC):
  Spearman = **{sp_weight:.2f}** — essentially unrelated.
- **{n_null_in_top} of the top-50** weighted edges have **no** group difference at all (p > 0.05).
- The 50 edges that are genuinely most different in autism sit at a median **weight-rank of
  {median_weight_rank_of_affected:.0f} of {P}** — i.e. near the **bottom** by classifier weight
  (only {overlap_w} of those 50 are even in the top-50 by weight).

## The forward (activation) pattern recovers them
Transforming the weights to the Haufe forward pattern A = Cov(X)·w (in the standardized feature space
the weights live in) aligns with the true group differences: Spearman(|A|, |t|) = **{sp_forward:.2f}**
({overlap_A} of the 50 truly-affected edges are in its top-50). The reported `top_affected_connections`
are read from this forward pattern; `top_weighted_connections` (the naive readout) are shown alongside
to make the mismatch explicit.

## Conclusion
The weight vector of a discriminative ("backward") classifier — and, identically, GNN edge/node
saliency — does **not** indicate which connections are affected: large weights can fall on
noise-cancelling ("suppressor") edges with no group difference, and truly affected edges can carry
near-zero weights. To report the affected connections one must use the **forward/activation pattern**
(A = Cov(X)·w) or **univariate** group statistics. Reporting the top classifier weights as the
"autism-affected connections" (as many interpretable-classifier / GNN-saliency papers do) is
misleading (Haufe et al. 2014).
""")

print(f"OK: n={n} edges={P}; nested-CV AUC={cv_auc:.2f}+-{cv_auc_sd:.2f} (C={Cbest}); "
      f"Spearman(|w|,|effect|)={sp_weight:.2f} vs forward={sp_forward:.2f}; "
      f"top50-weight null={n_null_in_top}/50 overlap={overlap_w}/50 vs forward overlap={overlap_A}/50; "
      f"affected median weight-rank={median_weight_rank_of_affected:.0f}/{P}")
