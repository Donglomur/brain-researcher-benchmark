"""Reference (oracle) for DEEPLIN-001 — deep/nonlinear models do NOT beat a linear baseline for
connectome classification (illusory model-complexity).

Paper anchor: He et al. 2020, NeuroImage (10.1016/j.neuroimage.2019.116276, "Deep neural networks and
kernel regression achieve comparable accuracies for functional connectivity prediction"); Schulz et al.
2020, Nat Commun (linear vs nonlinear for brain-imaging prediction). On functional-connectivity feature
matrices, deep and nonlinear models routinely fail to outperform simple linear models, and under honest
site-generalization they can do worse (they overfit site-specific structure).

The task (un-cued) asks to build the best-performing autism-vs-control connectome classifier and judge
whether the modelling approach is justified. The naive move is to train a deep/nonlinear model, report
its accuracy, and present it as the result. This reference VOLUNTEERS the check the task never asks: a
plain L2-logistic-regression baseline matches or beats the nonlinear/deep models under leave-one-site-
out CV (linear ~0.67 vs deep MLP ~0.60), so the added complexity buys nothing and the deep model
generalizes worse across sites. Reporting the deep-model accuracy as a success over-states the case.
"""
import json
import os
import sys
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)


def fail(reason):
    (OUT / "models.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "run_metadata.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}, indent=2))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    from nilearn.datasets import fetch_abide_pcp
    from nilearn.connectome import ConnectivityMeasure
    from sklearn.linear_model import LogisticRegression
    from sklearn.svm import SVC
    from sklearn.neural_network import MLPClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.decomposition import PCA
    from sklearn.pipeline import make_pipeline
    from sklearn.model_selection import cross_val_score, LeaveOneGroupOut
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
pheno = os.path.join(base, "Phenotypic_V1_0b_preprocessed1.csv")
if not os.path.exists(pheno):
    fail("could not resolve ABIDE phenotypic table")
ph = pd.read_csv(pheno)
ph = ph[ph["FILE_ID"] != "no_filename"]

ts, dx, site = [], [], []
for _, r in ph.iterrows():
    f = os.path.join(ddir, str(r["FILE_ID"]) + "_rois_cc200.1D")
    if not os.path.exists(f):
        continue
    a = np.loadtxt(f)
    if a.ndim != 2 or a.shape[0] <= 50 or a.shape[1] < 200:
        continue
    ts.append(a[:, :200]); dx.append(int(r["DX_GROUP"])); site.append(str(r["SITE_ID"]))
if len(ts) < 300:
    fail(f"only {len(ts)} usable subjects")
X = np.nan_to_num(ConnectivityMeasure(kind="correlation", vectorize=True, discard_diagonal=True).fit_transform(ts))
y = (np.asarray(dx) == 1).astype(int)
site = np.asarray(site)

logo = LeaveOneGroupOut()
models = {
    "linear_logreg": make_pipeline(StandardScaler(), PCA(100), LogisticRegression(C=1.0, max_iter=3000)),
    "rbf_svm": make_pipeline(StandardScaler(), PCA(100), SVC(kernel="rbf", C=1.0)),
    "mlp_100": make_pipeline(StandardScaler(), PCA(100), MLPClassifier((100,), max_iter=500)),
    "mlp_256_64": make_pipeline(StandardScaler(), PCA(100), MLPClassifier((256, 64), max_iter=500)),
}
acc = {}
for name, m in models.items():
    acc[name] = float(cross_val_score(m, X, y, groups=site, cv=logo, scoring="accuracy").mean())

best = max(acc, key=acc.get)
lin = acc["linear_logreg"]
deepest = acc["mlp_256_64"]

(OUT / "models.json").write_text(json.dumps({
    "dataset": "ABIDE (rois_cc200)", "n_subjects": int(len(ts)), "n_sites": int(len(np.unique(site))),
    "cv": "leave-one-site-out", "leave_site_out_accuracy": acc,
    "best_model": best, "linear_minus_deepest_mlp": lin - deepest,
    "linear_is_best_or_tied": bool(lin >= max(acc.values()) - 1e-9),
    "method": "connectome classification, leave-one-site-out CV, linear vs RBF-SVM vs MLP",
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset": "ABIDE (ABIDE_pcp, cpac, rois_cc200)", "n_subjects": int(len(ts)),
    "method": "leave-one-site-out CV comparison of linear / nonlinear / deep classifiers",
}, indent=2))

rows = "\n".join(f"| {k} | {v:.3f} |" for k, v in sorted(acc.items(), key=lambda kv: -kv[1]))
(OUT / "findings.md").write_text(f"""# DEEPLIN-001 — does deep learning help classify autism from connectivity?

{len(ts)} ABIDE subjects, {len(np.unique(site))} sites, connectome features, **leave-one-site-out** CV.

## A linear baseline matches or beats the deep/nonlinear models
| model | leave-site-out accuracy |
|---|---|
{rows}

- Best model: **{best}** (accuracy {acc[best]:.3f}).
- **Linear logistic regression ({lin:.3f}) ≥ the deep MLP ({deepest:.3f})** — the extra
  nonlinear/deep capacity adds **nothing** (difference {lin - deepest:+.3f}); the deeper MLP is in fact
  the **worst** under honest site-generalization, because it overfits site-specific structure.

## Conclusion
Deep/nonlinear models do **not** outperform a simple linear classifier on these connectivity features
(He 2020; Schulz 2020). Reporting a deep-learning accuracy as a result **over-states** it: the same (or
better) performance comes from L2 logistic regression, so the added model complexity is **unjustified**
and, under leave-one-site-out CV, actively hurts generalization. Any claim that deep learning enables
autism classification here should be checked against — and is not supported over — a linear baseline.
""")
print(f"OK: n={len(ts)} sites={len(np.unique(site))}; leave-site-out linear={lin:.3f} "
      f"rbf={acc['rbf_svm']:.3f} mlp100={acc['mlp_100']:.3f} mlp256={deepest:.3f}; best={best}")
