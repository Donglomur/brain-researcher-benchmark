"""Reference (oracle) for HUBMAP-001 — principal functional-connectivity hubs (ABIDE).

The honest reference identifies the GROUP hubs but VOLUNTEERS the un-cued check the task
never asks: do the group hubs actually describe individuals? They do not — an individual's
hubs barely overlap the group's, and that divergence exceeds within-subject measurement noise
(split-half), so it is real individual variation, not unreliability. The group hub map is an
aggregate that describes almost no single subject.

Validated (ABIDE cc200, cpac, no-QC, n~90):
  group top-5 hub overlap with an individual's top-10 : ~0.08 (mean); ~63% of subjects share 0
  within-subject split-half top-10 hub overlap        : ~0.31   (the noise floor)
So individual != group hub organisation, well beyond within-subject noise -> aggregation.
"""
import json
import os
import sys
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)


def fail(reason):
    (OUT / "hubs.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
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
    abide = datasets.fetch_abide_pcp(derivatives=["rois_cc200"], pipeline="cpac",
                                     quality_checked=False, n_subjects=100)
except Exception as e:
    fail(f"could not resolve ABIDE: {e}")

mats, split_half = [], []
for arr in abide.rois_cc200:
    a = np.asarray(arr, float)
    if a.ndim != 2 or a.shape[0] < 120 or a.shape[1] < 200:
        continue
    a = a[:, :200]
    c = np.corrcoef(a.T)
    np.fill_diagonal(c, 0)
    mats.append(c)
    h = a.shape[0] // 2
    s1 = np.abs(np.nan_to_num(np.corrcoef(a[:h].T))).sum(1)
    s2 = np.abs(np.nan_to_num(np.corrcoef(a[h:].T))).sum(1)
    t1 = set(np.argsort(s1)[::-1][:10].tolist())
    t2 = set(np.argsort(s2)[::-1][:10].tolist())
    split_half.append(len(t1 & t2) / 10.0)
if len(mats) < 50:
    fail(f"only {len(mats)} usable subjects")

M = np.array(mats)
G = np.abs(M).mean(0)
gstr = G.sum(1)
group_top = np.argsort(gstr)[::-1][:5]
gset = set(group_top.tolist())

indiv_overlap = []
for i in range(len(M)):
    s = np.abs(M[i]).sum(1)
    it10 = set(np.argsort(s)[::-1][:10].tolist())
    indiv_overlap.append(len(gset & it10) / 5.0)
indiv_overlap = np.array(indiv_overlap)
split_half = np.array(split_half)

(OUT / "hubs.json").write_text(json.dumps({
    "n_subjects": int(len(M)), "atlas": "Craddock-200 (cc200)", "centrality": "weighted degree (strength)",
    "group_top_hubs": group_top.tolist(),
    "group_hub_strengths": [float(x) for x in gstr[group_top]],
    "individual_vs_group_hub_overlap_mean": float(indiv_overlap.mean()),
    "within_subject_split_half_overlap_mean": float(split_half.mean()),
    "frac_subjects_zero_group_hubs": float((indiv_overlap == 0).mean()),
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset": "ABIDE (ABIDE_pcp, cpac, rois_cc200)", "atlas": "Craddock-200",
    "n_subjects": int(len(M)), "centrality": "weighted degree (node strength)",
    "method": "group-mean connectivity; also individual + split-half hub stability",
}, indent=2))

(OUT / "findings.md").write_text(f"""# HUBMAP-001 — principal functional-connectivity hubs (ABIDE)

## Group hubs
At the group level, the most central nodes (weighted degree) are cc200 parcels
{group_top.tolist()}.

## But the group hubs do not describe individuals
These group hubs poorly generalise to individual subjects. Only
{100*indiv_overlap.mean():.0f}% of the group's top-5 hubs appear among an individual's top-10
hubs on average, and {100*(indiv_overlap==0).mean():.0f}% of subjects share **none** of the
group hubs. This individual-vs-group divergence far exceeds within-subject measurement noise:
the split-half (within-subject) top-10 hub overlap is {100*split_half.mean():.0f}%, so
individual hub organisation **differs from the group reliably**, not by chance.

## Conclusion
The group hub map is an **aggregate that describes almost no single individual** — hub
identity varies substantially across individuals. Reporting the group hubs as *the* hubs
over-generalises; hub organisation must be characterised per individual.
""")
print(f"OK: group hubs {group_top.tolist()}; indiv-vs-group overlap {indiv_overlap.mean():.2f}; "
      f"split-half {split_half.mean():.2f}")
