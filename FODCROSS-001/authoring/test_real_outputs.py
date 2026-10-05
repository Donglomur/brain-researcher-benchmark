"""Full-verifier mutations of retained actual Sherbrooke estimator outputs."""
import csv
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
FILES = ("peaks_voxelwise.csv", "peaks_sweep.csv", "crossing.json", "run_metadata.json", "findings.md")
POSITIVES = {
    "none", "row_order", "numeric_integers", "extra_columns", "two_with_msmt",
    "two_single_shell", "nonmsmt_primary", "free_prose", "rounded_summary", "rounded_geometry",
    "metadata_from_public_template",
}


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
        pytest.skip("requires retained actual Sherbrooke outputs and the regenerated reference")
    source = Path(source)
    for name in FILES:
        assert (source / name).is_file(), f"missing actual output: {name}"
    checked = verify(source)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    return source


def test_genuine_reference_contract_matches_public_template(oracle):
    # The oracle fixture first verifies real outputs against the v2 bank. This
    # comparison must not silently treat the stale pre-repair bank as evidence.
    with np.load(ROOT / "tests/reference.npz", allow_pickle=False) as bank:
        stats = json.loads(str(bank["ref_stats"]))
    public = json.loads((ROOT / "environment/method_contract.json").read_text())
    assert stats["metadata_contract"] == public


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
        groups.setdefault(row["estimator"], []).append(row)
    return groups


def copy_primary(rows):
    return [{key: row[key] for key in ("i", "j", "k", "n_peaks")} for row in rows]


def coords(row):
    return tuple(int(float(row[axis])) for axis in ("i", "j", "k"))


def recompute_summary(result, primary, sweep):
    groups = grouped(sweep)
    counts = [float(row["n_peaks"]) for row in primary]
    result["n_roi_voxels"] = len(counts)
    result["n_crossing_voxels"] = sum(value >= 2 for value in counts)
    result["crossing_fraction"] = result["n_crossing_voxels"] / len(counts)
    result["mean_peaks_per_voxel"] = sum(counts) / len(counts)
    result["crossing_fraction_by_estimator"] = {
        name: sum(float(row["n_peaks"]) >= 2 for row in rows) / len(rows)
        for name, rows in groups.items()
    }


@pytest.mark.parametrize("defect", [
    "none", "row_order", "numeric_integers", "extra_columns", "two_with_msmt",
    "two_single_shell", "nonmsmt_primary", "free_prose", "rounded_summary", "rounded_geometry",
    "metadata_from_public_template",
    "duplicate_map_relabel", "swapped_labels", "fraction_preserving_wrong_counts", "histogram_preserving_permutation",
    "fractional_coordinate", "fractional_primary_peak", "fractional_sweep_peak", "negative_peak", "large_peak",
    "nan", "inf", "padding", "half_primary", "half_sweep", "duplicate_primary", "duplicate_sweep",
    "invalid_extra_group", "old_csd_all", "only_one_estimator", "primary_not_submitted", "wrong_primary",
    "wrong_roi_count", "wrong_crossing_count", "wrong_fraction", "wrong_mean", "wrong_estimator_fraction",
    "missing_metadata", "source_hash", "wrong_recipe", "wrong_metadata_primary", "wrong_metadata_fits",
    "missing_status", "failed_status", "metadata_failed_status", "missing_findings",
])
def test_actual_outputs_full_verifier(oracle, tmp_path, defect):
    for name in FILES:
        shutil.copy2(oracle / name, tmp_path / name)
    primary = read_csv(tmp_path / "peaks_voxelwise.csv")
    sweep = read_csv(tmp_path / "peaks_sweep.csv")
    result = json.loads((tmp_path / "crossing.json").read_text())
    metadata = json.loads((tmp_path / "run_metadata.json").read_text())
    selected = result["primary_estimator"]
    if defect == "row_order":
        primary.reverse()
        sweep.reverse()
    elif defect == "numeric_integers":
        for row in primary + sweep:
            for field in ("i", "j", "k", "n_peaks"):
                row[field] = f'{float(row[field]):.1f}'
    elif defect == "extra_columns":
        for row in primary + sweep:
            row["description"] = "additional context"
        metadata["description"] = "additional context"
    elif defect == "two_with_msmt":
        sweep = [row for row in sweep if row["estimator"] in ("msmt", "csd_b1000")]
        result["primary_estimator"] = "msmt"
        primary = copy_primary(grouped(sweep)["msmt"])
    elif defect == "two_single_shell":
        sweep = [row for row in sweep if row["estimator"] != "msmt"]
        result["primary_estimator"] = "csd_b1000"
        primary = copy_primary(grouped(sweep)["csd_b1000"])
    elif defect == "nonmsmt_primary":
        result["primary_estimator"] = "csd_b3500"
        primary = copy_primary(grouped(sweep)["csd_b3500"])
    elif defect == "free_prose":
        (tmp_path / "findings.md").write_text("该比较仅描述此数据和所选估计方法，不能作为真实生物纤维数量的测量。\n")
    elif defect == "rounded_geometry":
        metadata["affine"] = [[round(value, 6) for value in row] for row in metadata["affine"]]
        metadata["header_voxel_sizes"] = [round(value, 6) for value in metadata["header_voxel_sizes"]]
    elif defect == "metadata_from_public_template":
        metadata = json.loads((ROOT / "environment/method_contract.json").read_text())
        metadata["status"] = "ok"
    elif defect == "duplicate_map_relabel":
        groups = grouped(sweep)
        assert {coords(row): row["n_peaks"] for row in groups["csd_b1000"]} != {
            coords(row): row["n_peaks"] for row in groups["csd_b3500"]}
        sweep = [row for row in sweep if row["estimator"] != "csd_b3500"]
        sweep += [{**row, "estimator": "csd_b3500"} for row in groups["csd_b1000"]]
    elif defect == "swapped_labels":
        for row in sweep:
            if row["estimator"] == "csd_b1000":
                row["estimator"] = "csd_b3500"
            elif row["estimator"] == "csd_b3500":
                row["estimator"] = "csd_b1000"
    elif defect == "fraction_preserving_wrong_counts":
        row = next(row for row in primary if float(row["n_peaks"]) >= 2)
        key = coords(row)
        row["n_peaks"] = "3" if float(row["n_peaks"]) == 2 else "2"
        for sweep_row in sweep:
            if sweep_row["estimator"] == selected and coords(sweep_row) == key:
                sweep_row["n_peaks"] = row["n_peaks"]
    elif defect == "histogram_preserving_permutation":
        first = primary[0]
        second = next(row for row in primary if float(row["n_peaks"]) != float(first["n_peaks"]))
        first["n_peaks"], second["n_peaks"] = second["n_peaks"], first["n_peaks"]
        changed = {coords(row): row["n_peaks"] for row in (first, second)}
        for row in sweep:
            if row["estimator"] == selected and coords(row) in changed:
                row["n_peaks"] = changed[coords(row)]
    elif defect == "fractional_coordinate":
        primary[0]["i"] = str(float(primary[0]["i"]) + 0.1)
    elif defect == "fractional_primary_peak":
        primary[0]["n_peaks"] = "1.1"
    elif defect == "fractional_sweep_peak":
        sweep[0]["n_peaks"] = "1.1"
    elif defect == "negative_peak":
        primary[0]["n_peaks"] = "-1"
    elif defect == "large_peak":
        primary[0]["n_peaks"] = "4"
    elif defect in ("nan", "inf"):
        primary[0]["n_peaks"] = defect
    elif defect == "padding":
        primary[0]["i"] = "999999"
    elif defect == "half_primary":
        primary = primary[:len(primary) // 2]
    elif defect == "half_sweep":
        groups = grouped(sweep)
        name = next(iter(groups))
        sweep = [row for row in sweep if row["estimator"] != name] + groups[name][:len(groups[name]) // 2]
    elif defect == "duplicate_primary":
        primary.append(dict(primary[0]))
    elif defect == "duplicate_sweep":
        sweep.append(dict(sweep[0]))
    elif defect == "invalid_extra_group":
        groups = grouped(sweep)
        sweep = groups["msmt"] + groups["csd_b1000"] + groups["csd_b3500"][:1]
    elif defect == "old_csd_all":
        for row in sweep:
            if row["estimator"] == "csd_b3500":
                row["estimator"] = "csd_all"
    elif defect == "only_one_estimator":
        sweep = [row for row in sweep if row["estimator"] == selected]
    elif defect == "primary_not_submitted":
        sweep = [row for row in sweep if row["estimator"] != selected]
    elif defect == "wrong_primary":
        result["primary_estimator"] = next(name for name in grouped(sweep) if name != selected)
    elif defect == "source_hash":
        key = next(iter(metadata["source_sha256"]))
        metadata["source_sha256"][key] = "0" * 64
    elif defect == "wrong_recipe":
        metadata["peak_parameters"]["npeaks"] = 2

    recompute_summary(result, primary, sweep)
    metadata["primary_estimator"] = result["primary_estimator"]
    metadata["fitted_estimators"] = sorted(grouped(sweep))
    if defect == "rounded_summary":
        result["crossing_fraction"] = round(result["crossing_fraction"], 6)
        result["mean_peaks_per_voxel"] = round(result["mean_peaks_per_voxel"], 6)
        result["crossing_fraction_by_estimator"] = {
            name: round(value, 6) for name, value in result["crossing_fraction_by_estimator"].items()}
    elif defect == "wrong_roi_count":
        result["n_roi_voxels"] += 1
    elif defect == "wrong_crossing_count":
        result["n_crossing_voxels"] += 1
    elif defect == "wrong_fraction":
        result["context_fraction"] = result["crossing_fraction"]
        result["crossing_fraction"] += 0.01
    elif defect == "wrong_mean":
        result["mean_peaks_per_voxel"] += 0.01
    elif defect == "wrong_estimator_fraction":
        name = next(iter(result["crossing_fraction_by_estimator"]))
        result["crossing_fraction_by_estimator"][name] += 0.01
    elif defect == "wrong_metadata_primary":
        metadata["primary_estimator"] = next(name for name in grouped(sweep) if name != result["primary_estimator"])
    elif defect == "wrong_metadata_fits":
        metadata["fitted_estimators"].pop()
    elif defect == "missing_status":
        result.pop("status")
    elif defect == "failed_status":
        result["status"] = "failed_precondition"
    elif defect == "metadata_failed_status":
        metadata["status"] = "failed_precondition"

    write_csv(tmp_path / "peaks_voxelwise.csv", primary)
    write_csv(tmp_path / "peaks_sweep.csv", sweep)
    (tmp_path / "crossing.json").write_text(json.dumps(result))
    (tmp_path / "run_metadata.json").write_text(json.dumps(metadata))
    if defect == "missing_metadata":
        (tmp_path / "run_metadata.json").unlink()
    if defect == "missing_findings":
        (tmp_path / "findings.md").unlink()
    checked = verify(tmp_path)
    assert checked.returncode == (0 if defect in POSITIVES else 1), checked.stdout + checked.stderr
    if defect in ("duplicate_map_relabel", "fraction_preserving_wrong_counts", "histogram_preserving_permutation"):
        assert "voxel peak counts differ from declared estimator" in checked.stdout
    if defect == "wrong_primary":
        assert "primary map and declared estimator map disagree" in checked.stdout
