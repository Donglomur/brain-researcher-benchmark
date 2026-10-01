"""Reference-backed contract fixtures; no EEG recomputation is claimed."""
import csv
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

TASK = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("defect", [None, "invalid_power", "wrong_channels", "duplicate"])
def test_contract(tmp_path, defect):
    ref = np.load(TASK / "tests/reference.npz")
    rows = [dict(subject=str(s), ec_occipital_alpha=float(ec), eo_occipital_alpha=float(eo), ratio=float(r))
            for s, ec, eo, r in zip(ref["ref_ids"], ref["ref_ec"], ref["ref_eo"], ref["ref_ratio"])]
    if defect == "invalid_power":
        rows[0]["ec_occipital_alpha"] = -1
        rows[0]["eo_occipital_alpha"] = 0
    if defect == "duplicate":
        rows.append(rows[0])
    with (tmp_path / "per_subject.csv").open("w") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)
    channels = ["O1", "Oz", "O2"] if defect != "wrong_channels" else ["F1", "F2", "Fz"]
    result = dict(occipital_alpha_ratio_ec_over_eo=float(ref["occ_mean"]), band_hz=[8, 13],
                  n_subjects=5, channels=channels, wholehead_alpha_ratio_for_reference=float(ref["wholehead_mean"]))
    metadata = dict(dataset_id="eegbci", subjects=[1, 2, 3, 4, 5], runs={"eyes_open": 1, "eyes_closed": 2},
                    band_hz=[8, 13], channels=channels, psd_method="Welch, 2 s", reference="common average")
    (tmp_path / "alpha_ratio.json").write_text(json.dumps(result))
    (tmp_path / "run_metadata.json").write_text(json.dumps(metadata))
    (tmp_path / "findings.md").write_text("Occipital alpha is enhanced with eyes closed in this modern sample.")
    proc = subprocess.run([sys.executable, "-m", "pytest", "-q", str(TASK / "tests/test_outputs.py")],
                          env={**os.environ, "OUTPUT_DIR": str(tmp_path)}, capture_output=True, text=True)
    assert (proc.returncode == 0) == (defect is None), proc.stdout + proc.stderr
