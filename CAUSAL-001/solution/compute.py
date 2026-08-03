"""Reference (oracle) for CAUSAL-001 — directed functional connectivity (ABIDE).

The honest reference estimates lag-based directed influences but VOLUNTEERS the un-cued check
the task never asks: are the inferred DIRECTIONS reliable? They are not — within a subject, the
inferred direction of an influence replicates only ~58% of the time across a split-half (chance
50%). fMRI estimates the PRESENCE of connections well but their DIRECTION poorly, because
regional hemodynamic-lag differences confound lag-based causality (Smith et al. 2011). So a
directed/causal claim ('A drives B') is unwarranted.

Validated (ABIDE dosenbach160, cpac, no-QC, n~60, 160 ROIs):
  within-subject split-half DIRECTION agreement : ~0.58  (chance 0.50)  -> unreliable
"""
import json
import os
import sys
from pathlib import Path

import numpy as np

np.random.seed(0)
OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)
NROI, NPAIRS = 160, 100


def fail(reason):
    (OUT / "directed_connectivity.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason, "dataset": "ABIDE"}, indent=2))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    from nilearn import datasets
except Exception as e:  # pragma: no cover
    fail(f"nilearn import failed: {e}")

try:
    abide = datasets.fetch_abide_pcp(derivatives=["rois_dosenbach160"], pipeline="cpac",
                                     quality_checked=False, n_subjects=60)
except Exception as e:
    fail(f"could not resolve ABIDE: {e}")

TS, mats = [], []
for arr in abide.rois_dosenbach160:
    a = np.asarray(arr, float)
    if a.ndim != 2 or a.shape[0] < 120 or a.shape[1] < NROI:
        continue
    a = a[:, :NROI]
    a = (a - a.mean(0)) / (a.std(0) + 1e-8)
    TS.append(a)
    mats.append(np.corrcoef(a.T))
if len(TS) < 30:
    fail(f"only {len(TS)} usable subjects")

G = np.mean(mats, 0)
np.fill_diagonal(G, 0)
iu = np.triu_indices(NROI, 1)
top = np.argsort(np.abs(G[iu]))[::-1][:NPAIRS]
I, J = iu[0][top], iu[1][top]


def dirscore(x):
    a, b = x[:-1], x[1:]
    return np.mean(a[:, I] * b[:, J], 0) - np.mean(a[:, J] * b[:, I], 0)  # >0: I leads J


agrees, alld = [], []
for a in TS:
    alld.append(dirscore(a))
    h = a.shape[0] // 2
    agrees.append(float(np.mean(np.sign(dirscore(a[:h])) == np.sign(dirscore(a[h:])))))
rel = float(np.mean(agrees))
Dmean = np.mean(alld, 0)
order = np.argsort(np.abs(Dmean))[::-1][:10]
top_influences = []
for k in order:
    frm, to, sc = (int(I[k]), int(J[k]), float(Dmean[k])) if Dmean[k] > 0 else (int(J[k]), int(I[k]), float(-Dmean[k]))
    top_influences.append({"from": frm, "to": to, "direction_score": sc})

(OUT / "directed_connectivity.json").write_text(json.dumps({
    "n_subjects": int(len(TS)), "atlas": "Dosenbach-160", "method": "lag-1 directionality (Granger-style)",
    "n_pairs": int(NPAIRS),
    "top_directed_influences": top_influences,
    "direction_split_half_reliability": rel,
    "chance": 0.5,
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset": "ABIDE (ABIDE_pcp, cpac, rois_dosenbach160)", "atlas": "Dosenbach-160",
    "n_subjects": int(len(TS)), "method": "lag-1 directed influence; within-subject split-half direction reliability",
}, indent=2))

(OUT / "findings.md").write_text(f"""# CAUSAL-001 — directed functional connectivity (ABIDE)

## Directed influences (lag-based)
Lag-based directed influences were estimated among the {NPAIRS} most strongly connected region
pairs; the nominal dominant directions are listed in `directed_connectivity.json`.

## But the inferred directions are unreliable
The **direction** of these influences barely replicates within a subject: across a
within-subject split-half, the inferred direction agrees only **{rel:.0%}** of the time
(chance = 50%). That is far below what is needed to assert directionality. fMRI estimates the
**presence** of connections well but their **direction** poorly (Smith et al. 2011), because
inter-regional **hemodynamic-lag** differences confound lag-based causality.

## Conclusion
A directed / causal claim ("region A drives region B") is **not warranted** on these data: the
inferred directions are near chance and do not replicate. Which region drives which cannot be
established from resting fMRI here — connectivity should be interpreted as **undirected**.
""")
print(f"OK: {len(TS)} subjects; direction split-half reliability {rel:.2f} (chance 0.50)")
