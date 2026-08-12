"""Reference (oracle) for SEXCLASS-001 — how well sex is predicted from connectivity, and the
un-cued class-imbalance / base-rate inflation of raw accuracy.

Paper anchor: Varoquaux et al. 2017, NeuroImage (10.1016/j.neuroimage.2016.10.038, "Assessing and
tuning brain decoders: cross-validation, caveats, and guidelines") — under class imbalance raw
accuracy is a misleading score; it tracks the majority-class base rate, so balanced accuracy / AUC
and a comparison to the trivial majority baseline are required. In ABIDE, sex is heavily imbalanced
(~85% male), so a connectome classifier's headline accuracy is dominated by the base rate.

The task (un-cued) asks to predict sex from connectivity and report how well. The naive move is to
read off the raw cross-validated accuracy (~0.84) and call it strong. This reference VOLUNTEERS the
check the task never asks: the raw accuracy is essentially the majority base rate (~0.848) — a
trivial "always predict male" classifier does as well or better — while the honest, imbalance-robust
metrics reveal only modest real skill (balanced accuracy ~0.58, AUC ~0.74).

Method repair (maintainer #14): feature standardisation is done INSIDE the cross-validation pipeline
(sklearn Pipeline, fit on train folds only — no leakage of test-fold statistics), and class-balanced
baselines are reported (balanced accuracy, AUC, and the majority-class base rate).

Reads the packaged cc200 bundle OFFLINE (no nilearn / no network). Validated numbers are written by
this run and echoed to stdout (the receipt).
"""
import csv
import json
import os
import sys
import warnings
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")
np.seterr(all="ignore")

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)
DATA = Path(os.environ.get("BUNDLE_DIR", str(Path(__file__).resolve().parent.parent / "data"))) / "cc200_baserate.npz"


def fail(reason):
    (OUT / "classification.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason, "dataset": "ABIDE cc200 (packaged)"}, indent=2))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedKFold, cross_val_predict
    from sklearn.metrics import accuracy_score, balanced_accuracy_score, roc_auc_score
except Exception as e:  # pragma: no cover
    fail(f"scikit-learn import failed: {e}")

try:
    d = np.load(DATA, allow_pickle=True)
    X = np.nan_to_num(d["X"].astype(np.float64))   # subjects x 19,900 Fisher-z cc200 edges
    sex = d["sex"].astype(int)                      # SEX: 1 = male, 2 = female
    subid = d["subid"]
except Exception as e:
    fail(f"could not load packaged cc200 bundle: {e}")

if X.shape[0] < 200 or not set(np.unique(sex)).issubset({1, 2}) or len(set(sex)) < 2:
    fail(f"packaged data invalid: X={X.shape}, sex values {np.unique(sex).tolist()}")

male = (sex == 1).astype(int)                       # 1 = male (majority), 0 = female
n = int(len(male))
p_male = float(male.mean())
base_rate = float(max(p_male, 1 - p_male))          # majority-class ("always predict majority") accuracy

# --- REPAIR #14: standardise INSIDE the CV pipeline (fit on train folds only) ---
pipe = Pipeline([("scale", StandardScaler()),
                 ("clf", LogisticRegression(C=1.0, max_iter=2000))])
skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=0)
pred = cross_val_predict(pipe, X, male, cv=skf)
proba = cross_val_predict(pipe, X, male, cv=skf, method="predict_proba")[:, 1]

raw_acc = float(accuracy_score(male, pred))
bal_acc = float(balanced_accuracy_score(male, pred))
auc = float(roc_auc_score(male, proba))
# per-class recall makes the imbalance concrete (majority recall high, minority recall low)
recall_male = float(((pred == 1) & (male == 1)).sum() / max((male == 1).sum(), 1))
recall_female = float(((pred == 0) & (male == 0)).sum() / max((male == 0).sum(), 1))

# ---- predictions.csv: the per-subject out-of-fold data the verifier CHECKS ----
with open(OUT / "predictions.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["subid", "sex", "pred_male", "proba_male"])
    for i in range(n):
        w.writerow([int(subid[i]), int(sex[i]), int(pred[i]), f"{float(proba[i]):.6f}"])

(OUT / "classification.json").write_text(json.dumps({
    "dataset": "ABIDE cc200 (packaged bundle)", "n_subjects": n,
    "target": "sex (SEX: 1=male, 2=female)",
    "fraction_male": p_male, "fraction_majority_class": base_rate,
    "majority_baseline_accuracy": base_rate,
    "classifier_raw_accuracy": raw_acc,
    "classifier_balanced_accuracy": bal_acc,
    "classifier_auc": auc,
    "recall_male": recall_male, "recall_female": recall_female,
    "raw_accuracy_minus_base_rate": raw_acc - base_rate,
    "method": "L2 logistic regression in a StandardScaler->LogReg Pipeline (scaling fit on train "
              "folds only), 5-fold stratified CV; raw accuracy vs balanced accuracy / AUC vs the "
              "majority-class base rate",
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset": "ABIDE (ABIDE_pcp, cpac, rois_cc200), packaged bundle",
    "atlas": "Craddock-200", "n_subjects": n,
    "preprocessing": "Fisher-z cc200 connectome edges (packaged); NaN edges -> 0; standardisation "
                     "fit inside CV on train folds only",
    "method": "connectome L2 logistic-regression sex classifier; scaling inside a CV Pipeline; "
              "raw accuracy vs balanced accuracy / AUC vs the majority-class base rate",
}, indent=2))

(OUT / "findings.md").write_text(f"""# SEXCLASS-001 — predicting sex from connectivity (ABIDE cc200)

ABIDE connectivity, {n} subjects. Sex is heavily **imbalanced**: {p_male*100:.0f}% male, so the
majority class is {base_rate*100:.1f}% of the sample.

## Raw accuracy is dominated by the base rate
- **Majority-class baseline** ("always predict male"): accuracy = **{base_rate:.3f}**.
- Trained classifier **raw accuracy = {raw_acc:.3f}** — essentially the base rate, and in fact
  {'at or below' if raw_acc <= base_rate + 1e-9 else 'barely above'} the trivial baseline
  ({raw_acc:.3f} vs {base_rate:.3f}). The raw accuracy just reflects the {base_rate*100:.0f}% majority
  prevalence, not the model's skill.
- Honest, imbalance-robust metrics: **balanced accuracy = {bal_acc:.3f}**, **AUC = {auc:.3f}**.
- The imbalance is visible in the per-class recall: male recall {recall_male:.2f} but female recall
  only {recall_female:.2f} — the classifier mostly predicts the majority class.

## The high-looking accuracy conveys little skill
A raw accuracy of {raw_acc:.2f} *sounds* strong, but a classifier that ignores the brain and always
predicts the majority class already scores {base_rate:.3f} — as well or better. The real (modest)
discriminative signal only shows up in the balanced accuracy ({bal_acc:.2f}) and AUC ({auc:.2f}).

## Conclusion
Under class imbalance, **raw accuracy is a misleading performance score** — it tracks the base rate,
not the model's skill (Varoquaux 2017). Sex can be predicted from connectivity only **modestly**
(balanced accuracy {bal_acc:.2f}, AUC {auc:.2f}); reporting the {raw_acc:.0%} raw accuracy as strong
sex prediction over-states the result. Imbalanced classification must be scored with balanced
accuracy / AUC and compared against the majority-class base rate.
""")

print(f"OK: n={n} base_rate={base_rate:.3f}; raw_acc={raw_acc:.3f} (<=base) "
      f"bal_acc={bal_acc:.3f} auc={auc:.3f} recall_M={recall_male:.2f} recall_F={recall_female:.2f}")
