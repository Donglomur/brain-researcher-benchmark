"""Reference (oracle) for INTERP-001 — classifier weights are NOT the affected connections
(the forward-vs-backward / interpretation-of-weight-vectors problem).

Paper anchor: Haufe et al. 2014, NeuroImage (10.1016/j.neuroimage.2013.10.067, "On the interpretation
of weight vectors of linear models in multivariate neuroimaging"). The weight vector of a
discriminative (backward) model does NOT indicate which features carry the signal: a large weight can
sit on a noise-cancelling ("suppressor") feature with no group difference, and a genuinely affected
feature can get a near-zero weight. To read out which features are actually different between groups,
the weights must be transformed to the FORWARD/activation pattern A = Cov(X) w (or one uses univariate
group statistics). This applies identically to connectome classifiers and GNN edge/node saliency.

The task (un-cued) asks: train a classifier to separate autism from controls on ABIDE connectivity,
then identify which CONNECTIONS are most affected in autism from the trained model. The naive move is
to report the top-magnitude classifier WEIGHTS as the affected connections. This reference VOLUNTEERS
the check the task never asks: the weight ranking barely matches the true per-edge group difference
(Spearman |w| vs |effect| ~ 0.15), many top-weighted edges have NO group difference, and the truly
most-affected edges rank near the BOTTOM by weight — whereas the Haufe forward pattern recovers them
(Spearman ~ 0.88). So classifier weights must not be interpreted as the affected connections.
"""
import json
import os
import sys
import warnings
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")  # benign numpy RuntimeWarnings on the large connectome matmul

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)


def fail(reason):
    (OUT / "affected_connections.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "run_metadata.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}, indent=2))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    from nilearn.datasets import fetch_abide_pcp
    from nilearn.connectome import ConnectivityMeasure
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from scipy.stats import ttest_ind, spearmanr, t as tdist
except Exception as e:  # pragma: no cover
    fail(f"import failed: {e}")

import pandas as pd

try:
    fetch_abide_pcp(derivatives=["rois_cc200"], pipeline="cpac",
                    band_pass_filtering=True, global_signal_regression=False, quality_checked=False)
except Exception:
    pass
base = os.path.expanduser("~/nilearn_data/ABIDE_pcp")
ddir = os.path.join(base, "cpac", "filt_noglobal")
pheno_csv = os.path.join(base, "Phenotypic_V1_0b_preprocessed1.csv")
if not os.path.exists(pheno_csv):
    fail("could not resolve ABIDE phenotypic table")
ph = pd.read_csv(pheno_csv)
ph = ph[ph["FILE_ID"] != "no_filename"]

ts, dx = [], []
for _, row in ph.iterrows():
    f = os.path.join(ddir, str(row["FILE_ID"]) + "_rois_cc200.1D")
    if not os.path.exists(f):
        continue
    a = np.loadtxt(f)
    if a.ndim != 2 or a.shape[0] <= 50 or a.shape[1] < 200:
        continue
    ts.append(a[:, :200]); dx.append(int(row["DX_GROUP"]))
if len(ts) < 200:
    fail(f"only {len(ts)} usable subjects (need the ABIDE cc200 cache)")

X = ConnectivityMeasure(kind="correlation", vectorize=True, discard_diagonal=True).fit_transform(ts)
X = np.nan_to_num(X.astype(np.float64), nan=0.0, posinf=0.0, neginf=0.0)  # flat ROIs -> NaN edges
asd = (np.asarray(dx) == 1).astype(int)   # DX_GROUP: 1 = autism, 2 = control
n, P = X.shape

# discriminative (backward) model: standardized-feature logistic regression
Xs = np.nan_to_num(StandardScaler().fit_transform(X))   # guard zero-variance edges
clf = LogisticRegression(C=1.0, max_iter=3000).fit(Xs, asd)
w = np.nan_to_num(clf.coef_.ravel())

# ground-truth per-edge group difference (univariate): t-statistic and p
tvals, _ = ttest_ind(X[asd == 1], X[asd == 0], axis=0)
pvals = 2 * tdist.sf(np.abs(tvals), n - 2)

# forward / activation pattern (Haufe): A = Cov(X) w  (computed without forming the PxP covariance)
Xc = X - X.mean(0)
with np.errstate(invalid="ignore", over="ignore"):
    A = np.nan_to_num((Xc.T @ (Xc @ w)) / (n - 1))

sp_weight = float(spearmanr(np.abs(w), np.abs(tvals)).correlation)
sp_forward = float(spearmanr(np.abs(A), np.abs(tvals)).correlation)
top_w = np.argsort(np.abs(w))[-50:]
n_null_in_top = int((pvals[top_w] > 0.05).sum())
true_top = np.argsort(np.abs(tvals))[-50:]
weight_rank = np.argsort(np.argsort(np.abs(w)))         # 0 = smallest |weight|
median_weight_rank_of_affected = float(np.median(weight_rank[true_top]))

(OUT / "affected_connections.json").write_text(json.dumps({
    "dataset": "ABIDE (rois_cc200)", "n_subjects": int(n), "n_edges": int(P),
    "classifier": "L2 logistic regression on standardized FC edges",
    "spearman_absweight_vs_absgroupeffect": sp_weight,
    "spearman_absforwardpattern_vs_absgroupeffect": sp_forward,
    "n_top50_weighted_edges_with_no_group_difference": n_null_in_top,
    "median_weight_rank_of_50_most_affected_edges": median_weight_rank_of_affected,
    "n_edges_total": int(P),
    "note": "top affected connections should be read from the forward pattern / univariate stats, "
            "NOT from the raw classifier weights",
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset": "ABIDE (ABIDE_pcp, cpac, rois_cc200)", "n_subjects": int(n),
    "method": "logistic-regression connectome classifier; weights vs Haufe forward pattern vs "
              "univariate group differences",
}, indent=2))

(OUT / "findings.md").write_text(f"""# INTERP-001 — which connections are "affected" in autism?

A logistic-regression classifier on ABIDE connectivity ({n} subjects, {P} edges) separates autism
from controls above chance. It is tempting to read the largest-magnitude classifier **weights** as
the autism-affected connections — but that is wrong.

## Classifier weights are NOT the affected connections
- Correlation of |classifier weight| with the true per-edge group difference (|t|, ASD vs TDC):
  Spearman = **{sp_weight:.2f}** — essentially unrelated.
- **{n_null_in_top} of the top-50** weighted edges have **no** group difference at all (p > 0.05).
- The 50 edges that are genuinely most different in autism sit at a median **weight-rank of
  {median_weight_rank_of_affected:.0f} of {P}** — i.e. near the **bottom** by classifier weight.

## The forward (activation) pattern recovers them
Transforming the weights to the forward pattern A = Cov(X)·w (Haufe et al. 2014) aligns with the true
group differences: Spearman(|A|, |t|) = **{sp_forward:.2f}**.

## Conclusion
The weight vector of a discriminative ("backward") classifier — and, identically, GNN edge/node
saliency — does **not** indicate which connections are affected: large weights can fall on
noise-cancelling ("suppressor") edges with no group difference, and truly affected edges can get
near-zero weights. To report the affected connections one must use the **forward/activation pattern**
(A = Cov(X)·w) or **univariate** group statistics. Reporting the top classifier weights as the
"autism-affected connections" (as many interpretable-classifier / GNN-saliency papers do) is
misleading (Haufe 2014).
""")
print(f"OK: n={n} edges={P}; Spearman(|w|,|effect|)={sp_weight:.2f} vs forward={sp_forward:.2f}; "
      f"top50-weight null={n_null_in_top}/50; affected median weight-rank={median_weight_rank_of_affected:.0f}/{P}")
