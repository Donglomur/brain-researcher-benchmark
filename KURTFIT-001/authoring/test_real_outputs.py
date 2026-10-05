"""Full-verifier mutations of retained measured CFIN DKI outputs."""
import csv
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
FILES = ("mk_voxelwise.csv", "mk_sweep.csv", "dki_results.json", "run_metadata.json", "findings.md")


def verify(output):
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", str(ROOT / "tests/test_outputs.py")],
        env={**os.environ, "OUTPUT_DIR": str(output), "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"},
        capture_output=True, text=True, timeout=60,
    )


@pytest.fixture(scope="module")
def oracle():
    source = os.environ.get("REPAIR_ORACLE_OUTPUT")
    if not source:
        pytest.skip("requires retained real-data DKI outputs and a regenerated reference")
    source = Path(source)
    for name in FILES:
        assert (source / name).is_file(), f"missing actual output: {name}"
    checked = verify(source)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    return source


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def grouped(sweep):
    groups = {}
    for row in sweep:
        groups.setdefault(int(float(row["max_b"])), []).append(row)
    return groups


def recompute_summary(result, primary, sweep):
    groups = grouped(sweep)
    result["n_wm_voxels"] = len(primary)
    result["mean_kurtosis_wm"] = sum(float(row["mk"]) for row in primary) / len(primary)
    means = {str(cap): sum(float(row["mk"]) for row in rows) / len(rows)
             for cap, rows in groups.items()}
    result["mean_kurtosis_wm_by_bcap"] = means
    result["mk_shell_cap_spread"] = max(means.values()) - min(means.values())


@pytest.mark.parametrize("defect", [
    "none", "row_order", "rounded_values", "rounded_geometry", "numeric_coordinates", "extra_columns", "two_caps", "free_prose",
    "partial_primary", "partial_sweep", "padding", "duplicate_primary", "duplicate_sweep",
    "fractional_coordinate", "mean_preserving_scaling", "invalid_extra_group", "unknown_2500",
    "swapped_caps", "wrong_primary", "primary_sweep_mismatch", "missing_2000", "only_2000",
    "wrong_count", "nan", "inf", "out_of_range", "missing_metadata", "source_hash",
    "wrong_method", "wrong_primary_mean", "wrong_cap_mean", "wrong_spread", "wrong_shells", "wrong_bmax",
    "missing_status", "failed_status",
])
def test_actual_outputs_full_verifier(oracle, tmp_path, defect):
    for name in FILES:
        shutil.copy2(oracle / name, tmp_path / name)
    primary = read_csv(tmp_path / "mk_voxelwise.csv")
    sweep = read_csv(tmp_path / "mk_sweep.csv")
    result = json.loads((tmp_path / "dki_results.json").read_text())
    metadata = json.loads((tmp_path / "run_metadata.json").read_text())
    if defect == "row_order":
        primary.reverse()
        sweep.reverse()
    elif defect == "rounded_values":
        for row in primary + sweep:
            row["mk"] = f'{float(row["mk"]):.6f}'
    elif defect == "rounded_geometry":
        metadata["affine"] = [[round(value, 6) for value in row] for row in metadata["affine"]]
        metadata["voxel_sizes_mm"] = [round(value, 6) for value in metadata["voxel_sizes_mm"]]
        metadata["preprocessing"]["sigma_vox"] = [round(value, 6) for value in metadata["preprocessing"]["sigma_vox"]]
    elif defect == "numeric_coordinates":
        for row in primary + sweep:
            for axis in ("i", "j", "k"):
                row[axis] = f'{float(row[axis]):.1f}'
            if "max_b" in row:
                row["max_b"] = f'{float(row["max_b"]):.1f}'
    elif defect == "extra_columns":
        for row in primary + sweep:
            row["description"] = "extra context"
        metadata["description"] = "extra context"
    elif defect == "two_caps":
        sweep = [row for row in sweep if int(row["max_b"]) in (1000, 2000)]
    elif defect == "free_prose":
        (tmp_path / "findings.md").write_text("该测量仅适用于所选被试、白质区域与拟合条件。逐体素结果见输出表。\n")
    elif defect == "partial_primary":
        primary.pop()
    elif defect == "partial_sweep":
        sweep.pop()
    elif defect == "padding":
        primary[0]["i"] = "999999"
    elif defect == "duplicate_primary":
        primary.append(dict(primary[0]))
    elif defect == "duplicate_sweep":
        sweep.append(dict(sweep[0]))
    elif defect == "fractional_coordinate":
        primary[0]["i"] = str(float(primary[0]["i"]) + 0.1)
    elif defect == "mean_preserving_scaling":
        # Retains every cap mean and perfect positive correlation while changing the maps.
        for rows in [primary, *grouped(sweep).values()]:
            mean = sum(float(row["mk"]) for row in rows) / len(rows)
            for row in rows:
                row["mk"] = str(mean + 0.9 * (float(row["mk"]) - mean))
    elif defect == "invalid_extra_group":
        groups = grouped(sweep)
        sweep = groups[1000] + groups[2000] + groups[1400][:1]
    elif defect == "unknown_2500":
        for row in sweep:
            if int(row["max_b"]) == 2400:
                row["max_b"] = "2500"
    elif defect == "swapped_caps":
        for row in sweep:
            if int(row["max_b"]) == 1000:
                row["max_b"] = "3000"
            elif int(row["max_b"]) == 3000:
                row["max_b"] = "1000"
    elif defect == "wrong_primary":
        primary = [{key: row[key] for key in ("i", "j", "k", "mk")} for row in grouped(sweep)[3000]]
    elif defect == "primary_sweep_mismatch":
        row = next(row for row in primary if 0 < float(row["mk"]) < 2.9)
        row["mk"] = str(float(row["mk"]) + 5e-6)
    elif defect == "missing_2000":
        sweep = [row for row in sweep if int(row["max_b"]) != 2000]
    elif defect == "only_2000":
        sweep = [row for row in sweep if int(row["max_b"]) == 2000]
    elif defect in ("nan", "inf"):
        primary[0]["mk"] = defect
    elif defect == "out_of_range":
        primary[0]["mk"] = "3.001"
    elif defect == "source_hash":
        key = next(iter(metadata["source_sha256"]))
        metadata["source_sha256"][key] = "0" * 64
    elif defect == "wrong_method":
        metadata["dki"]["fit_method"] = "OLS"

    recompute_summary(result, primary, sweep)
    if defect == "rounded_values":
        result["mean_kurtosis_wm"] = round(result["mean_kurtosis_wm"], 6)
        result["mean_kurtosis_wm_by_bcap"] = {key: round(value, 6)
                                             for key, value in result["mean_kurtosis_wm_by_bcap"].items()}
        result["mk_shell_cap_spread"] = round(result["mk_shell_cap_spread"], 6)
    elif defect == "wrong_count":
        result["n_wm_voxels"] += 1
    elif defect == "wrong_primary_mean":
        result["mean_kurtosis_wm"] += 0.01
    elif defect == "wrong_cap_mean":
        result["mean_kurtosis_wm_by_bcap"]["1000"] += 0.01
    elif defect == "wrong_spread":
        result["mk_shell_cap_spread"] += 0.01
    elif defect == "wrong_shells":
        result["shells_used"] = [0, 2000]
    elif defect == "wrong_bmax":
        result["b_max_used"] = 3000
    elif defect == "missing_status":
        result.pop("status")
    elif defect == "failed_status":
        result["status"] = "failed_precondition"

    write_csv(tmp_path / "mk_voxelwise.csv", primary)
    write_csv(tmp_path / "mk_sweep.csv", sweep)
    (tmp_path / "dki_results.json").write_text(json.dumps(result))
    (tmp_path / "run_metadata.json").write_text(json.dumps(metadata))
    if defect == "missing_metadata":
        (tmp_path / "run_metadata.json").unlink()
    checked = verify(tmp_path)
    positive = defect in ("none", "row_order", "rounded_values", "rounded_geometry", "numeric_coordinates",
                          "extra_columns", "two_caps", "free_prose")
    assert checked.returncode == (0 if positive else 1), checked.stdout + checked.stderr
    if defect == "mean_preserving_scaling":
        assert "voxel MK values differ" in checked.stdout
    if defect == "primary_sweep_mismatch":
        assert "primary map and 2000 sweep map disagree" in checked.stdout
