"""Reference (oracle) for BASERATE-001 — accuracy under class imbalance (the base-rate paradox).

Paper anchor: Varoquaux et al. 2017, NeuroImage (10.1016/j.neuroimage.2016.10.038, "Assessing and
tuning brain decoders: cross-validation, caveats, and guidelines") — raw accuracy is a misleading
score under class imbalance; balanced accuracy / AUC and comparison to the majority-class base rate
are required. In ABIDE, sex is heavily imbalanced (~84% male), so a classifier's headline accuracy is
dominated by the base rate.

The task (un-cued) asks to predict sex from connectivity and report how well it can be predicted. The
naive move is to report the raw cross-validated accuracy (~0.82) as strong performance. This reference
VOLUNTEERS the check the task never asks: the raw accuracy is essentially the majority base rate
(~0.845) — a trivial "always predict male" classifier does AS WELL OR BETTER — while the honest
metrics reveal only modest real skill (balanced accuracy ~0.64, AUC ~0.74). Reporting raw accuracy
under this imbalance overstates performance (and can even fall below the trivial baseline).
"""
import json
import os
import sys
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)


def fail(reason):
    (OUT / "classification.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "run_metadata.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}, indent=2))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    from nilearn.datasets import fetch_abide_pcp
    from nilearn.connectome import ConnectivityMeasure
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import StratifiedKFold, cross_val_predict
    from sklearn.metrics import accuracy_score, balanced_accuracy_score, roc_auc_score
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

ts, sex = [], []
for _, row in ph.iterrows():
    f = os.path.join(ddir, str(row["FILE_ID"]) + "_rois_cc200.1D")
    if not os.path.exists(f):
        continue
    a = np.loadtxt(f)
    if a.ndim != 2 or a.shape[0] <= 50 or a.shape[1] < 200:
        continue
    if int(row["SEX"]) not in (1, 2):
        continue
    ts.append(a[:, :200]); sex.append(int(row["SEX"]))
if len(ts) < 200:
    fail(f"only {len(ts)} usable subjects (need the ABIDE cc200 cache)")

X = np.nan_to_num(ConnectivityMeasure(kind="correlation", vectorize=True, discard_diagonal=True).fit_transform(ts))
male = (np.asarray(sex) == 1).astype(int)   # SEX: 1 = male, 2 = female
n = len(male)
p_male = float(male.mean())
base_rate = float(max(p_male, 1 - p_male))   # majority-class ("always predict the majority") accuracy

Xs = StandardScaler().fit_transform(X)
skf = StratifiedKFold(5, shuffle=True, random_state=0)
pred = cross_val_predict(LogisticRegression(C=1.0, max_iter=2000), Xs, male, cv=skf)
proba = cross_val_predict(LogisticRegression(C=1.0, max_iter=2000), Xs, male, cv=skf, method="predict_proba")[:, 1]
raw_acc = float(accuracy_score(male, pred))
bal_acc = float(balanced_accuracy_score(male, pred))
auc = float(roc_auc_score(male, proba))

(OUT / "classification.json").write_text(json.dumps({
    "dataset": "ABIDE (rois_cc200)", "n_subjects": int(n), "target": "sex (SEX: 1=male,2=female)",
    "fraction_majority_class": base_rate, "fraction_male": p_male,
    "majority_baseline_accuracy": base_rate,
    "classifier_raw_accuracy": raw_acc,
    "classifier_balanced_accuracy": bal_acc,
    "classifier_auc": auc,
    "raw_accuracy_minus_base_rate": raw_acc - base_rate,
    "method": "L2 logistic regression, 5-fold stratified CV; accuracy vs balanced accuracy vs AUC",
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset": "ABIDE (ABIDE_pcp, cpac, rois_cc200)", "n_subjects": int(n),
    "method": "connectome logistic-regression sex classifier; raw accuracy vs balanced accuracy / AUC "
              "vs the majority-class base rate",
}, indent=2))

(OUT / "findings.md").write_text(f"""# BASERATE-001 — predicting sex from connectivity

ABIDE connectivity, {n} subjects. Sex is heavily **imbalanced**: {p_male*100:.0f}% male, so the
majority class is {base_rate*100:.1f}% of the sample.

## Raw accuracy is dominated by the base rate
- **Majority-class baseline** ("always predict male"): accuracy = **{base_rate:.3f}**.
- Trained classifier **raw accuracy = {raw_acc:.3f}** — essentially the base rate
  ({'below' if raw_acc < base_rate else 'barely above'} the trivial baseline: {raw_acc:.3f} vs {base_rate:.3f}).
- Honest, imbalance-robust metrics: **balanced accuracy = {bal_acc:.3f}**, **AUC = {auc:.3f}**.

The raw accuracy of {raw_acc:.2f} *sounds* strong but conveys almost no skill: a classifier that
ignores the brain and always predicts the majority class does {'better' if base_rate>raw_acc else 'about as well'}.
The real (modest) discriminative signal only shows up in balanced accuracy ({bal_acc:.2f}) and AUC
({auc:.2f}).

## Conclusion
Under class imbalance, **raw accuracy is a misleading performance score** — it reflects the base rate,
not the model's skill (Varoquaux 2017). Sex can be predicted from connectivity only **modestly**
(balanced accuracy {bal_acc:.2f}, AUC {auc:.2f}); reporting the {raw_acc:.0%} raw accuracy as strong
performance over-states the result. Imbalanced classification must be scored with balanced accuracy /
AUC and compared against the majority-class base rate.
""")
print(f"OK: n={n} %maj={base_rate:.3f}; raw_acc={raw_acc:.3f} (base={base_rate:.3f}) "
      f"bal_acc={bal_acc:.3f} auc={auc:.3f}")
