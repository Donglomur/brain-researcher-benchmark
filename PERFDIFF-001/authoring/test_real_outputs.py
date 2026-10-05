"""Mutate retained genuine IVIM outputs; never manufacture a scientific bank."""
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
sys.path.insert(0, str(ROOT / "tests"))
from proof_of_work import METHODS, PARAMETERS, SUMMARY_ATOL

FILES = ("parameters_voxelwise.csv", "f_voxelwise.csv", "f_sweep.csv",
         "ivim_results.json", "run_metadata.json", "findings.md")
POSITIVES = {"none", "row_order", "numeric_coordinates", "extra_columns", "segmented_primary",
             "free_prose", "rounded_geometry", "public_metadata_template", "alternate_optimizer_termination",
             "undefined_spelling"}
CASES = sorted(POSITIVES) + [
    "fractional_coordinate", "duplicate_parameter", "duplicate_primary", "duplicate_sweep",
    "half_parameters", "half_primary", "half_sweep", "padding", "unknown_method", "only_one_method",
    "swapped_methods", "copied_method", "fabricated_D", "fabricated_Dstar", "fabricated_S0",
    "shifted_f", "coordinate_permutation", "undefined_success", "infinite_parameter",
    "wrong_status", "fallback_success", "wrong_eligibility", "wrong_common_valid",
    "wrong_init_projected", "wrong_component_swap", "wrong_bound_flags", "wrong_optimizer_status",
    "wrong_nfev", "invented_nrmse", "wrong_primary_link", "wrong_primary_label",
    "wrong_own_count", "wrong_common_count", "wrong_common_summary", "wrong_signed_paired_difference",
    "wrong_D_units", "wrong_box_count", "wrong_tissue_count", "wrong_eligible_count", "wrong_summary_only",
    "metadata_source_hash", "metadata_extra_hash", "metadata_recipe", "metadata_primary",
    "metadata_methods", "metadata_status_count", "missing_metadata", "missing_findings",
    "failed_result", "failed_metadata", "missing_parameter_column",
]


def verify(path):
    return subprocess.run([sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q",
                           str(ROOT / "tests/test_outputs.py")], capture_output=True, text=True, timeout=60,
                          env={**os.environ, "OUTPUT_DIR": str(path), "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"})


@pytest.fixture(scope="module")
def oracle():
    location = os.environ.get("REPAIR_ORACLE_OUTPUT")
    if not location:
        pytest.skip("requires actual900-row IVIM oracle outputs and the regenerated v2 reference")
    source = Path(location)
    for name in FILES:
        assert (source / name).is_file(), f"missing actual output: {name}"
    result = verify(source)
    assert result.returncode == 0, result.stdout + result.stderr
    return source


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def coords(row):
    return tuple(float(row[key]) for key in ("i", "j", "k"))


def truth(value):
    return str(value).lower() in ("true", "1")


def value(row, field):
    raw = str(row[field]).strip().lower()
    return np.nan if raw in ("", "null", "nan") else float(raw)


def grouped(rows):
    return {method: [row for row in rows if row["method"] == method] for method in METHODS}


def rebuild_maps(parameters, primary):
    sweep = [{key: row[key] for key in ("i", "j", "k", "method", "f")} for row in parameters]
    single = [{key: row[key] for key in ("i", "j", "k", "f")} for row in parameters if row["method"] == primary]
    return single, sweep


def recompute_summaries(result, parameters):
    groups = grouped(parameters)
    def summary(rows):
        output = {"n_voxels": len(rows)}
        for field in (*PARAMETERS, "nrmse"):
            values = [value(row, field) for row in rows]
            output[f"{field}_mean"] = float(np.mean(values)) if values and np.isfinite(values).all() else None
        return output
    result["fits"] = [{"method": name, **summary([row for row in rows if row["status"] == "ok"])}
                      for name, rows in groups.items()]
    common = {name: summary([row for row in rows if truth(row["common_valid"])]) for name, rows in groups.items()}
    difference = {}
    for field in SUMMARY_ATOL:
        left, right = common[METHODS[0]][field], common[METHODS[1]][field]
        difference[field] = right-left if left is not None and right is not None else None
    result["common_valid"] = {"n_voxels": common[METHODS[0]]["n_voxels"], "by_method": common,
                              "paired_differences": {"segmented_minus_trr": difference}}


def test_reference_public_contract_identity(oracle):
    with np.load(ROOT / "tests/reference.npz", allow_pickle=False) as bank:
        stats = json.loads(str(bank["ref_stats"]))
        assert bank["ref_roi_ijk"].shape == (900, 3)
    assert stats["metadata_contract"] == json.loads((ROOT / "environment/method_contract.json").read_text())


@pytest.mark.parametrize("defect", CASES)
def test_genuine_outputs_full_verifier(oracle, tmp_path, defect):
    for filename in FILES:
        shutil.copy2(oracle / filename, tmp_path / filename)
    parameters = read_csv(tmp_path / "parameters_voxelwise.csv")
    primary = read_csv(tmp_path / "f_voxelwise.csv")
    sweep = read_csv(tmp_path / "f_sweep.csv")
    result = json.loads((tmp_path / "ivim_results.json").read_text())
    metadata = json.loads((tmp_path / "run_metadata.json").read_text())
    selected = result["primary_method"]
    success = next(row for row in parameters if row["method"] == selected and row["status"] == "ok" and truth(row["common_valid"]))
    changed_parameters = False
    if defect == "row_order":
        parameters.reverse(); primary.reverse(); sweep.reverse()
    elif defect == "numeric_coordinates":
        for row in parameters+primary+sweep:
            for field in ("i", "j", "k"): row[field] = f"{float(row[field]):.1f}"
    elif defect == "extra_columns":
        for row in parameters+primary+sweep: row["note"] = "additional context"
        metadata["note"] = "additional context"
    elif defect == "segmented_primary":
        result["primary_method"] = metadata["primary_method"] = METHODS[1]
        primary, sweep = rebuild_maps(parameters, METHODS[1])
    elif defect == "free_prose":
        (tmp_path / "findings.md").write_text("模型拟合结果不等于真实灌注；方法比较仅限此公开数据。\n")
    elif defect == "rounded_geometry":
        metadata["affine"] = [[round(item, 6) for item in row] for row in metadata["affine"]]
        metadata["header_voxel_sizes"] = [round(item, 6) for item in metadata["header_voxel_sizes"]]
    elif defect == "public_metadata_template":
        observed = {key: metadata[key] for key in ("n_box_voxels", "n_tissue_voxels", "n_eligible_voxels",
                    "n_common_valid_voxels", "status_counts")}
        metadata = json.loads((ROOT / "environment/method_contract.json").read_text())
        metadata.update(status="ok", primary_method=selected, fitted_methods=list(METHODS))
        metadata.update(observed)
    elif defect == "alternate_optimizer_termination":
        success["optimizer_status"] = "3" if value(success, "optimizer_status") != 3 else "2"
        success["nfev"] = str(max(1, min(1000, int(value(success, "nfev"))+1)))
    elif defect == "undefined_spelling":
        for row in parameters:
            for field in (*PARAMETERS, "nrmse", "optimizer_status"):
                if str(row[field]).lower() in ("", "nan", "null"): row[field] = "NaN"
        for row in primary+sweep:
            if str(row["f"]).lower() in ("", "nan", "null"): row["f"] = "NaN"
    elif defect == "fractional_coordinate": primary[0]["i"] = str(float(primary[0]["i"])+.1)
    elif defect == "duplicate_parameter": parameters.append(dict(parameters[0]))
    elif defect == "duplicate_primary": primary.append(dict(primary[0]))
    elif defect == "duplicate_sweep": sweep.append(dict(sweep[0]))
    elif defect == "half_parameters": parameters = parameters[:len(parameters)//2]
    elif defect == "half_primary": primary = primary[:len(primary)//2]
    elif defect == "half_sweep": sweep = sweep[:len(sweep)//2]
    elif defect == "padding": parameters[0]["i"] = "999999"
    elif defect == "unknown_method": parameters[0]["method"] = "trr"
    elif defect == "only_one_method": parameters = [row for row in parameters if row["method"] == selected]
    elif defect == "swapped_methods":
        for row in parameters: row["method"] = METHODS[1] if row["method"] == METHODS[0] else METHODS[0]
        changed_parameters = True
    elif defect == "copied_method":
        original = [row for row in parameters if row["method"] == METHODS[0]]
        parameters = original + [{**row, "method": METHODS[1]} for row in original]
        changed_parameters = True
    elif defect in ("fabricated_D", "fabricated_Dstar", "fabricated_S0", "shifted_f"):
        field = {"fabricated_D":"D", "fabricated_Dstar":"Dstar", "fabricated_S0":"S0", "shifted_f":"f"}[defect]
        success[field] = str(value(success, field) + {"D":.001, "Dstar":.01, "S0":1., "f":.01}[field])
        changed_parameters = True
    elif defect == "coordinate_permutation":
        other = next(row for row in parameters if row["method"] == selected and coords(row) != coords(success)
                     and row["status"] == "ok" and abs(value(row,"f")-value(success,"f")) > 1e-4)
        for field in (*PARAMETERS, "nrmse", "bound_flags", "component_swap", "init_projected"):
            success[field], other[field] = other[field], success[field]
        changed_parameters = True
    elif defect == "undefined_success": success["Dstar"] = ""
    elif defect == "infinite_parameter": success["D"] = "inf"
    elif defect == "wrong_status": success["status"] = "optimizer_failed"
    elif defect == "fallback_success": success["fallback"] = "true"
    elif defect == "wrong_eligibility": success["eligible"] = "false"
    elif defect == "wrong_common_valid": success["common_valid"] = "false"
    elif defect == "wrong_init_projected": success["init_projected"] = str(not truth(success["init_projected"]))
    elif defect == "wrong_component_swap": success["component_swap"] = str(not truth(success["component_swap"]))
    elif defect == "wrong_bound_flags": success["bound_flags"] = "f_lower" if success["bound_flags"] != "f_lower" else ""
    elif defect == "wrong_optimizer_status": success["optimizer_status"] = "0"
    elif defect == "wrong_nfev": success["nfev"] = "0"
    elif defect == "invented_nrmse": success["nrmse"] = str(value(success,"nrmse")+.01)
    elif defect == "wrong_primary_link":
        linked = next(row for row in primary if np.isfinite(value(row, "f")))
        linked["f"] = str(value(linked,"f")+.01)
    elif defect == "wrong_primary_label": result["primary_method"] = METHODS[1] if selected == METHODS[0] else METHODS[0]
    elif defect == "metadata_source_hash": metadata["source_sha256"][next(iter(metadata["source_sha256"]))] = "0"*64
    elif defect == "metadata_extra_hash": metadata["source_sha256"]["other"] = "0"*64
    elif defect == "metadata_recipe": metadata["pipeline_id"] = "ivim-unpinned"
    elif defect == "metadata_primary": metadata["primary_method"] = METHODS[1] if selected == METHODS[0] else METHODS[0]
    elif defect == "metadata_methods": metadata["fitted_methods"] = [METHODS[0]]*2
    elif defect == "metadata_status_count": metadata["status_counts"][METHODS[0]]["ok"] += 1
    elif defect == "failed_result": result["status"] = "failed_precondition"
    elif defect == "failed_metadata": metadata["status"] = "failed_precondition"
    elif defect == "missing_parameter_column":
        for row in parameters: row.pop("Dstar")
    if changed_parameters:
        primary, sweep = rebuild_maps(parameters, selected)
        recompute_summaries(result, parameters)
    if defect == "wrong_own_count": result["fits"][0]["n_voxels"] += 1
    elif defect == "wrong_common_count": result["common_valid"]["n_voxels"] += 1
    elif defect == "wrong_common_summary": result["common_valid"]["by_method"][METHODS[0]]["f_mean"] += .01
    elif defect == "wrong_signed_paired_difference":
        differences = result["common_valid"]["paired_differences"]["segmented_minus_trr"]
        field = next((key for key, item in differences.items()
                      if key != "S0_mean" and item is not None and abs(item) > 10*SUMMARY_ATOL[key]), None)
        if field is None:
            # Agreement is legitimate; a fabricated signed difference still must fail.
            differences["f_mean"] += .01
        else:
            differences[field] = -differences[field]
    elif defect == "wrong_D_units": result["diffusivity_units"] = "um^2/ms"
    elif defect == "wrong_box_count": result["n_box_voxels"] += 1
    elif defect == "wrong_tissue_count": result["n_tissue_voxels"] += 1
    elif defect == "wrong_eligible_count": result["n_eligible_voxels"] += 1
    elif defect == "wrong_summary_only": result["fits"][0]["f_mean"] += .01
    write_csv(tmp_path / "parameters_voxelwise.csv", parameters)
    write_csv(tmp_path / "f_voxelwise.csv", primary)
    write_csv(tmp_path / "f_sweep.csv", sweep)
    (tmp_path / "ivim_results.json").write_text(json.dumps(result))
    (tmp_path / "run_metadata.json").write_text(json.dumps(metadata))
    if defect == "missing_metadata": (tmp_path / "run_metadata.json").unlink()
    if defect == "missing_findings": (tmp_path / "findings.md").unlink()
    checked = verify(tmp_path)
    assert checked.returncode == (0 if defect in POSITIVES else 1), checked.stdout + checked.stderr
    if defect in {"swapped_methods", "copied_method", "fabricated_D", "fabricated_Dstar", "fabricated_S0",
                  "shifted_f", "coordinate_permutation"}:
        assert "reference parameters" in checked.stdout, checked.stdout + checked.stderr
    if defect == "invented_nrmse":
        assert "source-reconstructed NRMSE" in checked.stdout, checked.stdout + checked.stderr
    if defect in {"wrong_primary_link", "wrong_primary_label"}:
        assert "primary f map/declared method linkage" in checked.stdout, checked.stdout + checked.stderr
