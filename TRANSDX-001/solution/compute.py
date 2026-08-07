"""Reference (oracle) for TRANSDX-001 — the schizophrenia connectome "biomarker" is not
diagnosis-specific (transdiagnostic non-specificity).

Paper anchor: Arbabshirani et al. 2017, NeuroImage (10.1016/j.neuroimage.2016.02.079, "Single subject
prediction of brain disorders in neuroimaging: promises and pitfalls") — a classifier that separates a
patient group from controls is routinely reported as a biomarker for that disorder, but is rarely
tested for SPECIFICITY against other disorders. Data: UCLA Consortium for Neuropsychiatric Phenomics
(OpenNeuro ds000030), resting-state functional connectomes for controls + schizophrenia + bipolar +
ADHD (see data/ provenance).

The task (un-cued) asks to build a connectivity classifier for schizophrenia vs controls and judge
whether connectivity is a valid schizophrenia biomarker. The naive move is to report the (real)
cross-validated accuracy as a schizophrenia biomarker. This reference VOLUNTEERS the check the task
never asks: is it schizophrenia-SPECIFIC? The schizophrenia-vs-control classifier works (held-out AUC
~0.78), but applied to BIPOLAR (never trained on) it still separates bipolar from controls (AUC ~0.62,
well above the ADHD value ~0.49, which is at chance) — so the "schizophrenia biomarker" is really a
psychosis-spectrum / shared-illness signal, not schizophrenia-specific. (ADHD at chance argues against
a generic patient/motion confound.)
"""
import json
import os
import sys
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)
DATA = Path(__file__).resolve().parent.parent / "data" / "cnp_connectomes.npz"


def fail(reason):
    (OUT / "specificity.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "run_metadata.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}, indent=2))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline
    from sklearn.model_selection import StratifiedKFold, cross_val_predict
    from sklearn.metrics import roc_auc_score
except Exception as e:  # pragma: no cover
    fail(f"import failed: {e}")

if not DATA.exists():
    fail(f"connectome dataset not found at {DATA}")
d = np.load(DATA, allow_pickle=True)
X, y = d["X"].astype(float), d["y"].astype(str)
Xc, Xs, Xb, Xa = X[y == "CONTROL"], X[y == "SCHZ"], X[y == "BIPOLAR"], X[y == "ADHD"]
if min(len(Xc), len(Xs), len(Xb), len(Xa)) < 15:
    fail("insufficient subjects per group")


def mk():
    return make_pipeline(StandardScaler(), LogisticRegression(C=0.3, max_iter=3000))


# 1) schizophrenia vs control — the reported "biomarker" (5-fold CV AUC)
m = (y == "CONTROL") | (y == "SCHZ")
proba = cross_val_predict(mk(), X[m], (y[m] == "SCHZ").astype(int),
                          cv=StratifiedKFold(5, shuffle=True, random_state=0), method="predict_proba")[:, 1]
schz_cv_auc = float(roc_auc_score((y[m] == "SCHZ").astype(int), proba))

# 2) SPECIFICITY: train SCHZ-vs-control, apply to OTHER disorders vs HELD-OUT controls (no control reuse)
def transfer(seed):
    rng = np.random.default_rng(seed)
    ci, si = rng.permutation(len(Xc)), rng.permutation(len(Xs))
    Ctr, Cte = Xc[ci[:len(Xc) // 2]], Xc[ci[len(Xc) // 2:]]
    Str, Ste = Xs[si[:len(Xs) // 2]], Xs[si[len(Xs) // 2:]]
    M = mk().fit(np.vstack([Ctr, Str]), np.r_[np.zeros(len(Ctr)), np.ones(len(Str))])

    def a(Xpos):
        s = M.decision_function(np.vstack([Cte, Xpos]))
        return roc_auc_score(np.r_[np.zeros(len(Cte)), np.ones(len(Xpos))], s)
    return a(Ste), a(Xb), a(Xa)


R = np.array([transfer(s) for s in range(30)])
schz_self, bip_auc, adhd_auc = [float(v) for v in R.mean(0)]
bip_sd, adhd_sd = float(R[:, 1].std()), float(R[:, 2].std())

(OUT / "specificity.json").write_text(json.dumps({
    "dataset": "UCLA CNP (OpenNeuro ds000030) functional connectomes",
    "n_per_group": {g: int((y == g).sum()) for g in ["CONTROL", "SCHZ", "BIPOLAR", "ADHD"]},
    "schizophrenia_vs_control_cv_auc": schz_cv_auc,
    "schz_classifier_transfer": {
        "schizophrenia_heldout_auc": schz_self,
        "bipolar_vs_control_auc": bip_auc,
        "adhd_vs_control_auc": adhd_auc},
    "bipolar_transfer_above_chance": bool(bip_auc - 2 * bip_sd > 0.5),
    "method": "L2 logistic regression on connectome edges; SCHZ-vs-control CV, then transfer to other "
              "disorders with held-out controls",
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset": "UCLA CNP (ds000030) connectomes", "n_subjects": int(len(y)),
    "method": "schizophrenia connectome classifier + cross-disorder specificity transfer",
}, indent=2))

(OUT / "findings.md").write_text(f"""# TRANSDX-001 — is connectivity a schizophrenia biomarker?

UCLA CNP connectomes: {int((y=='CONTROL').sum())} control, {int((y=='SCHZ').sum())} schizophrenia,
{int((y=='BIPOLAR').sum())} bipolar, {int((y=='ADHD').sum())} ADHD.

## A schizophrenia classifier works — but is not schizophrenia-specific
- Schizophrenia vs control (5-fold CV): **AUC = {schz_cv_auc:.2f}** — a real, above-chance classifier.
- Applying that **same** classifier (trained only on schizophrenia vs control) to other disorders,
  against **held-out** controls:
  - schizophrenia (held-out): AUC = **{schz_self:.2f}**
  - **bipolar** vs control: AUC = **{bip_auc:.2f}** ± {bip_sd:.2f} — **it still separates bipolar**
  - ADHD vs control: AUC = **{adhd_auc:.2f}** ± {adhd_sd:.2f} — at chance

The "schizophrenia biomarker" retains substantial power for **bipolar** disorder (AUC {bip_auc:.2f},
clearly above the ADHD/chance value {adhd_auc:.2f}). So it is not detecting schizophrenia specifically —
it captures a **psychosis-spectrum / shared-illness** signal common to schizophrenia and bipolar. That
ADHD is at chance argues the transfer is not a generic patient or head-motion confound.

## Conclusion
Reporting the schizophrenia-vs-control accuracy as a **schizophrenia biomarker over-states the claim**:
the classifier is **not diagnosis-specific** — it also separates bipolar disorder from controls
(Arbabshirani 2017). A valid disorder biomarker must be tested for **specificity** against other
disorders, not only against controls; here connectivity marks the psychosis spectrum, not
schizophrenia per se.
""")
print(f"OK: SCHZ-vs-CTL CV AUC={schz_cv_auc:.2f}; transfer self={schz_self:.2f} bipolar={bip_auc:.2f} "
      f"adhd={adhd_auc:.2f}")
