"""Isolated summary arithmetic, not a generated scientific positive or reference."""
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
from peak_contract import validate_results
from proof_of_work import PIPELINE_ID


@pytest.mark.parametrize("defect", [
    None, "context_bypass", "counts", "mean", "fraction_by_estimator", "extra_summary",
    "missing_summary", "missing_status", "wrong_pipeline", "unsubmitted_primary", "boolean_count",
])
def test_primary_summary_arithmetic(defect):
    primary = np.array([0, 1, 2, 3])
    groups = {"csd_b1000": primary, "csd_b3500": np.array([0, 0, 1, 1])}
    report = dict(
        status="ok", pipeline_id=PIPELINE_ID, primary_estimator="csd_b1000",
        crossing_fraction=0.5, n_roi_voxels=4, n_crossing_voxels=2,
        mean_peaks_per_voxel=1.5, crossing_fraction_by_estimator={"csd_b1000": 0.5, "csd_b3500": 0},
    )
    if defect == "context_bypass":
        report.update(crossing_fraction=0.9, context_fraction=0.5)
    elif defect == "counts":
        report["n_roi_voxels"] = -1
    elif defect == "mean":
        report["mean_peaks_per_voxel"] = 1.6
    elif defect == "fraction_by_estimator":
        report["crossing_fraction_by_estimator"]["csd_b3500"] = 0.5
    elif defect == "extra_summary":
        report["crossing_fraction_by_estimator"]["msmt"] = 0.5
    elif defect == "missing_summary":
        report["crossing_fraction_by_estimator"].pop("csd_b3500")
    elif defect == "missing_status":
        report.pop("status")
    elif defect == "wrong_pipeline":
        report["pipeline_id"] = "old"
    elif defect == "unsubmitted_primary":
        report["primary_estimator"] = "msmt"
    elif defect == "boolean_count":
        report["n_crossing_voxels"] = True
    if defect is None:
        assert validate_results(report, primary, groups) == "csd_b1000"
    else:
        with pytest.raises(AssertionError):
            validate_results(report, primary, groups)
