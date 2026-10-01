"""Richardson-derived GSR/motion sensitivity adaptation, not paper-faithful reproduction."""
from __future__ import annotations

import json
import os
import re
import hashlib
import traceback
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr, rankdata, t

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
    def fisher(values):
        return float(np.tanh(np.mean(np.arctanh(np.clip(values,-.999999,.999999)))))
    return (fisher(cc[:N_TOM, :N_TOM][iuT]),
            fisher(cc[N_TOM:, N_TOM:][iuP]),fisher(cc[:N_TOM, N_TOM:]))


def write_failfast(reason: str) -> None:
    pd.DataFrame(columns=["subject_index", "age", "group", "within_tom", "within_pain",
                          "across_network"]).to_csv(OUTPUT_DIR / "network_connectivity.csv", index=False)
    wj("age_effects.json", {"across_network": {"r": None, "p": None}, "within_tom": {"r": None, "p": None},
                            "within_pain": {"r": None, "p": None}, "adult_means": {}, "n_children": 0, "n_adults": 0})
    wj("run_metadata.json", {"task_id": TASK_ID, "dataset_id": DATASET_ID, "status": "failed_precondition",
                             "reason": reason})
    (OUTPUT_DIR / "findings.md").write_text(
        "# Richardson-derived GSR/motion sensitivity application\n\n"
        f"Child-only age association without/with GSR: {a0:+.4f}/{a1:+.4f}; "
        f"p={p0:.5g}/{p1:.5g}. Motion-adjusted rank estimates are also reported. "
        "This is an adaptation using reduced fMRIPrep nuisance regressors, Fisher-z network "
        "edge aggregation and optional global signal, not the paper's primary-motor/artifact "
        "pipeline. GSR sensitivity is descriptive; a sign/p change alone does not demonstrate "
        "a spurious developmental mechanism or prove that the paper finding fails.\n")

    print(f"children={len(ch)} adults={len(ad)} | across no-GSR r={a0} (p={p0:.3f}) | across GSR r={a1} (p={p1:.2e})")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        write_failfast(f"{type(exc).__name__}: {str(exc)[:200]} | {traceback.format_exc()[-300:]}")
        raise
