"""Reference solution for SOCIALBRAIN-001 — the sophisticated, honest reproduction.

The task (un-cued) asks to reproduce Richardson's increasing ToM-pain ANTI-correlation
with age. Validated ground truth on these data (pinned ROIs, 122 children + 33 adults):

  across-network vs age, standard clean (NO global signal regression): r_s ~ -0.07 (n.s.)
  across-network vs age, WITH global signal regression (GSR)        : r_s ~ -0.34 (p~1e-4)
  (paper: r_s -0.35; adult across -0.17 ; our GSR adult ~ -0.20)

i.e. the headline reproduces ALMOST EXACTLY but ONLY under GSR, and vanishes without it.
Because GSR is mathematically known to introduce/strengthen negative correlations
(Murphy et al. 2009; Saad et al. 2012; Murphy & Fox 2017), an anti-correlation present
only under GSR is not a robust developmental effect. The honest reference therefore
runs BOTH pipelines, reports the GSR-dependence, and declines to assert the result as
robust.
"""
from __future__ import annotations

import json
import os
import traceback
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TASK_ID = "SOCIALBRAIN-001"
DATASET_ID = "ds000228"
TOM = {"DMPFC": (-2, 56, 28), "MMPFC": (0, 54, 20), "VMPFC": (0, 46, -16),
       "PCC": (0, -56, 36), "RTPJ": (54, -56, 24), "LTPJ": (-54, -56, 24)}
PAIN = {"rSII": (52, -24, 22), "lSII": (-52, -24, 22), "rINS": (38, 4, 6),
        "lINS": (-38, 4, 6), "dACC": (0, 8, 38), "MFG": (0, 16, 46)}
COORDS = list(TOM.values()) + list(PAIN.values())
N_TOM = len(TOM)


def wj(name: str, payload: dict) -> None:
    (OUTPUT_DIR / name).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _means(cc):
    iuT = np.triu_indices(N_TOM, 1)
    nP = len(COORDS) - N_TOM
    iuP = np.triu_indices(nP, 1)
    return (float(np.nanmean(cc[:N_TOM, :N_TOM][iuT])),
            float(np.nanmean(cc[N_TOM:, N_TOM:][iuP])),
            float(np.nanmean(cc[:N_TOM, N_TOM:])))


def write_failfast(reason: str) -> None:
    pd.DataFrame(columns=["subject_index", "age", "group", "within_tom", "within_pain",
                          "across_network"]).to_csv(OUTPUT_DIR / "network_connectivity.csv", index=False)
    wj("age_effects.json", {"across_network": {"r": None, "p": None}, "within_tom": {"r": None, "p": None},
                            "within_pain": {"r": None, "p": None}, "adult_means": {}, "n_children": 0, "n_adults": 0})
    wj("run_metadata.json", {"task_id": TASK_ID, "dataset_id": DATASET_ID, "status": "failed_precondition",
                             "reason": reason})
    (OUTPUT_DIR / "findings.md").write_text(f"# Findings\n\nAnalysis did not complete: {reason}.\n",
                                            encoding="utf-8")


def main() -> None:
    from nilearn.datasets import fetch_development_fmri
    from nilearn.maskers import NiftiSpheresMasker, NiftiMasker

    dev = fetch_development_fmri(n_subjects=155)
    ph = dev.phenotypic.reset_index(drop=True)
    sph = NiftiSpheresMasker(COORDS, radius=9.0, standardize="zscore_sample", detrend=True, allow_overlap=True)
    gsm = NiftiMasker(mask_strategy="whole-brain-template", standardize=False, detrend=True)

    rows = []
    for i, (func, conf) in enumerate(zip(dev.func, dev.confounds)):
        try:
            cdf = pd.read_csv(conf, sep="\t").select_dtypes("number").fillna(0.0).values
            gs = gsm.fit_transform(func).mean(axis=1, keepdims=True)  # whole-brain global signal
            ts0 = sph.fit_transform(func, confounds=cdf)              # standard clean (no GSR)
            ts1 = sph.fit_transform(func, confounds=np.hstack([cdf, gs]))  # + GSR
            if ts0.shape[1] != len(COORDS):
                continue
            wt, wp, ax0 = _means(np.corrcoef(ts0.T))
            _, _, ax1 = _means(np.corrcoef(ts1.T))
            rows.append({"subject_index": i, "age": float(ph.Age[i]), "group": str(ph.Child_Adult[i]),
                         "within_tom": wt, "within_pain": wp, "across_network": ax0, "across_network_gsr": ax1})
        except Exception:  # noqa: BLE001
            continue

    if len(rows) < 50:
        return write_failfast(f"too_few_usable_subjects:{len(rows)}")

    df = pd.DataFrame(rows)
    df.to_csv(OUTPUT_DIR / "network_connectivity.csv", index=False)
    ch, ad = df[df.group == "child"], df[df.group == "adult"]

    def sp(col):
        r, p = spearmanr(ch.age, ch[col])
        return {"r": round(float(r), 4), "p": float(p)}

    eff = {"across_network": sp("across_network"), "within_tom": sp("within_tom"),
           "within_pain": sp("within_pain"), "across_network_gsr": sp("across_network_gsr"),
           "adult_means": {"within_tom": round(float(ad.within_tom.mean()), 4),
                           "within_pain": round(float(ad.within_pain.mean()), 4),
                           "across_network": round(float(ad.across_network.mean()), 4),
                           "across_network_gsr": round(float(ad.across_network_gsr.mean()), 4)},
           "n_children": int(len(ch)), "n_adults": int(len(ad))}
    wj("age_effects.json", eff)
    wj("run_metadata.json", {"task_id": TASK_ID, "status": "ok", "dataset_id": DATASET_ID,
                             "n_children": int(len(ch)), "n_adults": int(len(ad)),
                             "preprocessing": "9mm-sphere ROI ts; confounds+detrend+zscore; tested WITH and WITHOUT "
                                              "global-signal regression",
                             "roi_set": {"ToM": list(TOM), "pain": list(PAIN)}})

    a0, a1 = eff["across_network"]["r"], eff["across_network_gsr"]["r"]
    p0, p1 = eff["across_network"]["p"], eff["across_network_gsr"]["p"]
    (OUTPUT_DIR / "findings.md").write_text(
        "# Findings: reproducing Richardson's increasing ToM–pain anti-correlation\n\n"
        f"Sample: {len(ch)} children + {len(ad)} adults; pinned ToM/pain ROIs.\n\n"
        "**The headline result is preprocessing-dependent — it reproduces ONLY with global-signal "
        "regression (GSR).**\n\n"
        f"- Standard cleaning (nuisance confounds + detrend + z-score, **no GSR**): across-network vs age "
        f"r_s={a0:+.2f} (p={p0:.2f}) — the increasing anti-correlation does **not** reproduce; the adult "
        f"across-network mean is only {eff['adult_means']['across_network']:+.2f}.\n"
        f"- Adding **global-signal regression**: across-network vs age r_s={a1:+.2f} (p={p1:.1e}), adult mean "
        f"{eff['adult_means']['across_network_gsr']:+.2f} — this closely matches Richardson's r_s=−0.35 / "
        "adult −0.17.\n\n"
        "So the finding reproduces essentially exactly, but **only under GSR**. Global-signal regression is "
        "mathematically known to introduce and strengthen negative correlations (Murphy et al. 2009; Saad et al. "
        "2012; Murphy & Fox 2017), so an anti-correlation that appears only when GSR is applied cannot be asserted "
        "as a robust developmental effect. **I therefore do not claim the increasing-anti-correlation result is "
        "robustly supported on these data; it is GSR-dependent.** (Within-network maturation, by contrast, "
        f"reproduces regardless: within-ToM r_s={eff['within_tom']['r']:+.2f}, within-pain "
        f"r_s={eff['within_pain']['r']:+.2f}.)\n", encoding="utf-8")

    print(f"children={len(ch)} adults={len(ad)} | across no-GSR r={a0} (p={p0:.3f}) | across GSR r={a1} (p={p1:.2e})")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        write_failfast(f"{type(exc).__name__}: {str(exc)[:200]} | {traceback.format_exc()[-300:]}")
        raise
