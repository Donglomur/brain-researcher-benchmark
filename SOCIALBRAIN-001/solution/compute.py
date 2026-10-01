"""Richardson-derived GSR/motion sensitivity adaptation, not paper-faithful reproduction."""
from __future__ import annotations

import hashlib
import json
import os
import re
import traceback
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata, spearmanr, t

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
CONFOUND_COLUMNS = ["trans_x", "trans_y", "trans_z", "rot_x", "rot_y", "rot_z",
                    "framewise_displacement", *[f"a_comp_cor_{i:02d}" for i in range(6)],
                    "white_matter", "csf"]


def wj(name: str, payload: dict) -> None:
    (OUTPUT_DIR / name).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def source_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def participant_id(path):
    match = re.search(r"(sub-pixar\d+)", Path(path).name)
    if match is None:
        raise ValueError(f"unrecognized participant filename: {Path(path).name}")
    return match.group(1)


def _means(cc):
    iu_t = np.triu_indices(N_TOM, 1)
    iu_p = np.triu_indices(len(COORDS) - N_TOM, 1)
    def fisher(values):
        assert np.isfinite(values).all()
        return float(np.tanh(np.mean(np.arctanh(np.clip(values, -.999999, .999999)))))
    return (fisher(cc[:N_TOM, :N_TOM][iu_t]),
            fisher(cc[N_TOM:, N_TOM:][iu_p]), fisher(cc[:N_TOM, N_TOM:]))


def partial_rank_corr(age, values, motion):
    a, y, m = rankdata(age), rankdata(values), rankdata(motion)
    design = np.column_stack([np.ones(len(a)), m])
    ra = a - design @ np.linalg.lstsq(design, a, rcond=None)[0]
    ry = y - design @ np.linalg.lstsq(design, y, rcond=None)[0]
    r = float(np.corrcoef(ra, ry)[0, 1])
    df = len(a) - 3
    p = float(2 * t.sf(abs(r * np.sqrt(df / (1 - r * r))), df))
    return r, p


def write_failfast(reason: str) -> None:
    pd.DataFrame(columns=["subject_id", "age", "group", "mean_fd", "within_tom",
                          "within_pain", "across_network", "across_network_gsr"]).to_csv(
                              OUTPUT_DIR / "network_connectivity.csv", index=False)
    wj("age_effects.json", {"across_network": {"r": None, "p": None},
                           "adult_means": {}, "n_children": 0, "n_adults": 0})
    wj("run_metadata.json", {"task_id": TASK_ID, "dataset_id": DATASET_ID,
                             "status": "failed_precondition", "reason": reason})
    (OUTPUT_DIR / "findings.md").write_text(
        f"# Findings\n\nAnalysis did not complete: {reason}.\n", encoding="utf-8")


def main() -> None:
    from nilearn.datasets import fetch_development_fmri
    from nilearn.maskers import NiftiMasker, NiftiSpheresMasker

    dev = fetch_development_fmri(n_subjects=155)
    ph = dev.phenotypic.copy()
    assert ph.participant_id.is_unique and len(ph) == 155, "exact155 phenotype required"
    ph = ph.set_index("participant_id")
    assert len(dev.func) == len(dev.confounds) == 155, "exact155 inputs required"
    func_ids = [participant_id(path) for path in dev.func]
    assert len(set(func_ids)) == 155 and set(func_ids) == set(ph.index)
    sph = NiftiSpheresMasker(COORDS, radius=9.0, standardize="zscore_sample",
                            detrend=True, allow_overlap=True)
    gsm = NiftiMasker(mask_strategy="whole-brain-template", standardize=False, detrend=True)
    rows, sources = [], {}
    for func, conf in zip(dev.func, dev.confounds):
        sid = participant_id(func)
        assert participant_id(conf) == sid, "BOLD/confounds subject mismatch"
        cdf = pd.read_csv(conf, sep="\t")
        assert set(CONFOUND_COLUMNS) <= set(cdf.columns), "required reduced confounds missing"
        mean_fd = float(pd.to_numeric(cdf.framewise_displacement).mean())
        assert np.isfinite(mean_fd), "motion metadata missing"
        nuisance = cdf[CONFOUND_COLUMNS].apply(pd.to_numeric).fillna(0.0).to_numpy()
        gs = gsm.fit_transform(func).mean(axis=1, keepdims=True)
        ts0 = sph.fit_transform(func, confounds=nuisance)
        ts1 = sph.fit_transform(func, confounds=np.hstack([nuisance, gs]))
        assert ts0.shape == ts1.shape and ts0.shape[1] == len(COORDS)
        wt, wp, ax0 = _means(np.corrcoef(ts0.T))
        _, _, ax1 = _means(np.corrcoef(ts1.T))
        rows.append({"subject_id": sid, "age": float(ph.loc[sid, "Age"]),
                     "group": str(ph.loc[sid, "Child_Adult"]), "mean_fd": mean_fd,
                     "within_tom": wt, "within_pain": wp,
                     "across_network": ax0, "across_network_gsr": ax1})
        sources[sid] = {"bold_sha256": source_sha256(func),
                        "confounds_sha256": source_sha256(conf)}
    df = pd.DataFrame(rows)
    assert len(df) == 155 and df.subject_id.is_unique
    df.to_csv(OUTPUT_DIR / "network_connectivity.csv", index=False)
    ch, ad = df[df.group == "child"], df[df.group == "adult"]
    assert len(ch) == 122 and len(ad) == 33

    def estimate(column):
        r, p = spearmanr(ch.age, ch[column])
        pr, pp = partial_rank_corr(ch.age, ch[column], ch.mean_fd)
        return {"r": float(r), "p": float(p), "motion_adjusted_rank_r": pr,
                "motion_adjusted_rank_p": pp}

    columns = ["across_network", "across_network_gsr", "within_tom", "within_pain"]
    eff = {column: estimate(column) for column in columns}
    eff.update({"adult_means": {column: float(ad[column].mean()) for column in columns},
                "n_children": len(ch), "n_adults": len(ad)})
    wj("age_effects.json", eff)
    wj("run_metadata.json", {"task_id": TASK_ID, "dataset_id": DATASET_ID, "status": "ok",
                             "analysis_scope": "paper-derived GSR/motion sensitivity adaptation",
                             "n_children": len(ch), "n_adults": len(ad),
                             "subject_ids": list(df.subject_id), "source_sha256": sources,
                             "preprocessing": {"roi_radius_mm": 9, "detrend": True,
                                               "standardize": "zscore_sample",
                                               "confounds": CONFOUND_COLUMNS,
                                               "global_signal_mask_strategy": "whole-brain-template",
                                               "global_signal_standardize": False,
                                               "global_signal_detrend": True,
                                               "mean_fd_missing_values": "excluded before regression zero-fill",
                                               "pipelines": ["without_GSR", "with_GSR"]},
                             "edge_aggregation": "tanh(mean(Fisher-z))",
                             "roi_set": {"ToM": list(TOM), "pain": list(PAIN)}})
    a0, a1 = eff["across_network"]["r"], eff["across_network_gsr"]["r"]
    p0, p1 = eff["across_network"]["p"], eff["across_network_gsr"]["p"]
    (OUTPUT_DIR / "findings.md").write_text(
        "# Richardson-derived GSR/motion sensitivity application\n\n"
        f"Child-only age association without/with GSR: {a0:+.4f}/{a1:+.4f}; "
        f"p={p0:.5g}/{p1:.5g}. Motion-adjusted rank estimates are also reported. "
        "This is an adaptation using reduced fMRIPrep nuisance regressors, Fisher-z network "
        "edge aggregation and optional global signal, not the paper's primary-motor/artifact "
        "pipeline. GSR sensitivity is descriptive; a sign/p change alone does not demonstrate "
        "a spurious developmental mechanism or prove that the paper finding fails.\n",
        encoding="utf-8")
    print(f"children={len(ch)} adults={len(ad)} | across no-GSR r={a0} "
          f"(p={p0:.3f}) | across GSR r={a1} (p={p1:.2e})")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        write_failfast(f"{type(exc).__name__}: {str(exc)[:200]} | {traceback.format_exc()[-300:]}")
        raise
