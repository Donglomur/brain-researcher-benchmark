"""Genuine three-configuration acceptance and adversarial receipt checks.

REPAIR_ORACLE_OUTPUT is a directory containing the three actual config outputs.
Tests never fit models, fetch data or create a scientific reference bank.
"""
import csv
import json
import os
from pathlib import Path
import shutil
import sys

import numpy as np
import pytest

TASK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK/"tests"))
import proof_of_work as q
from build_reference import template_for


@pytest.fixture(scope="module")
def genuine_outputs():
    configured = os.environ.get("REPAIR_ORACLE_OUTPUT")
    if not configured: pytest.skip("requires genuine source-derived outputs for all three configs")
    directories = {config: Path(configured)/config for config in q.CONFIGS}
    assert all(path.is_dir() for path in directories.values()), "missing genuine configuration directory"
    return directories


@pytest.fixture(scope="module")
def reference(genuine_outputs):
    reference = q.load_reference(TASK/"tests/reference.npz")
    for config, output in genuine_outputs.items():
        declared, _ = q.validate_output_directory(output, reference)
        assert declared == config
    return reference


def copy_output(source, target):
    for filename in q.FILES: shutil.copyfile(source/filename, target/filename)
    return target


@pytest.fixture
def output(tmp_path, genuine_outputs):
    return copy_output(genuine_outputs["dki_all"], tmp_path)


def read_rows(output):
    with (output/"md_voxelwise.csv").open(newline="") as stream:
        return list(csv.DictReader(stream))


def write_rows(output, rows, columns=None):
    with (output/"md_voxelwise.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns or list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def write_coherent_beta(output, reference, config, beta):
    entry = reference["configs"][config]
    indices = entry["indices"]
    derived = q.derive(beta, reference["signal"][:, indices], entry["design"], reference["bvals"][indices])
    rows = [{"i": int(ijk[0]), "j": int(ijk[1]), "k": int(ijk[2]),
             **{key: int(derived[key][i]) if key in q.INTEGER_METRICS else float(derived[key][i]) for key in q.METRICS},
             **{f"beta_{j}": float(value) for j, value in enumerate(beta[i])}}
            for i, ijk in enumerate(reference["ijk"])]
    write_rows(output, rows)
    (output/"diffusivity.json").write_text(json.dumps(q.summarize(config, derived)))
    metadata = dict(reference["stats"]["metadata_by_config"][config], status="ok",
                    n_wm_voxels=len(reference["ijk"]), n_brain_voxels=reference["stats"]["n_brain_voxels"])
    (output/"run_metadata.json").write_text(json.dumps(metadata))


@pytest.mark.parametrize("config", q.CONFIGS)
def test_each_single_genuine_configuration_passes(output, genuine_outputs, reference, config):
    copy_output(genuine_outputs[config], output)
    assert not (output/"analysis_arrays.npz").exists()
    q.validate_output_directory(output, reference)


def test_public_templates_exactly_match_reference_contracts(reference):
    for config in q.CONFIGS:
        assert template_for(TASK/"environment", config) == reference["stats"]["metadata_by_config"][config]


def test_public_template_minimal_metadata_free_prose(output, reference):
    measured = q.load_json(output/"run_metadata.json")
    template = template_for(TASK/"environment", "dki_all")
    template.update({key: measured[key] for key in ("status", "n_wm_voxels", "n_brain_voxels")})
    (output/"run_metadata.json").write_text(json.dumps(template))
    (output/"findings.md").write_text("The attached tables give the computed quantities; these estimates are conditional on the stated method.")
    q.validate_output_directory(output, reference)


def test_row_column_order_extra_fields_numeric_notation(output, reference):
    rows = read_rows(output)
    for row in rows:
        for key in ("i", "j", "k", *q.INTEGER_METRICS): row[key] = f'{int(row[key])}.0'
        row["optional_note"] = "ignored"
    write_rows(output, rows[::-1], list(rows[0])[::-1])
    meta = q.load_json(output/"run_metadata.json"); meta["ungraded_diagnostic"] = {"comment": "extra"}
    (output/"run_metadata.json").write_text(json.dumps(meta))
    q.validate_output_directory(output, reference)


def test_full_precision_scientific_notation(output, reference):
    rows = read_rows(output)
    for row in rows:
        for key in row: row[key] = format(float(row[key]), ".17e")
    write_rows(output, rows)
    q.validate_output_directory(output, reference)


@pytest.mark.parametrize("config", q.CONFIGS)
def test_independently_refitted_subset_is_numerically_accepted(output, reference, config):
    configured = os.environ.get("REPAIR_INDEPENDENT_ROOT")
    if not configured:
        pytest.skip("requires retained genuine GELSD subset fits; never refits source in this test")
    root = Path(configured)
    name = f"independent_coefficients_{config}.npz"
    path = root/name if (root/name).is_file() else root/config/name
    with np.load(path, allow_pickle=False) as receipt:
        assert str(receipt["pipeline_id"].item()) == q.PIPELINE_ID
        assert str(receipt["model_config"].item()) == config
        assert int(receipt["n_roi_voxels"].item()) == len(reference["ijk"])
        assert json.loads(str(receipt["source_sha256_json"].item())) == reference["stats"]["source_sha256"]
        indices = receipt["roi_row_indices"]
        assert indices.dtype.kind in "iu" and indices.ndim == 1
        assert len(indices) == min(256, len(reference["ijk"])) and len(np.unique(indices)) == len(indices)
        assert np.all((indices >= 0) & (indices < len(reference["ijk"])))
        assert np.array_equal(receipt["roi_ijk"], reference["ijk"][indices])
        alternate = receipt["beta"]
    beta = reference["configs"][config]["beta"].copy()
    assert alternate.shape == beta[indices].shape and np.isfinite(alternate).all()
    beta[indices] = alternate
    # All other rows stay genuine; this is acceptance of the independently
    # refitted subset, never a claim of a second complete independent fit.
    write_coherent_beta(output, reference, config, beta)
    q.validate_output_directory(output, reference)


@pytest.mark.parametrize("mutation", ["diffusion_scale", "diffusion_offset", "quartic_sign", "intercept_shift", "coefficient_permutation"])
def test_coherent_raw_coefficient_forgery(output, reference, mutation):
    beta = reference["configs"]["dki_all"]["beta"].copy()
    if mutation == "diffusion_scale": beta[:, :6] *= 1.01
    elif mutation == "diffusion_offset": beta[:, [0, 2, 5]] += 1e-5
    elif mutation == "quartic_sign": beta[:, 6:21] *= -1
    elif mutation == "intercept_shift": beta[:, -1] += .01
    elif mutation == "coefficient_permutation": beta = beta[::-1].copy()
    assert not np.array_equal(beta, reference["configs"]["dki_all"]["beta"])
    write_coherent_beta(output, reference, "dki_all", beta)
    with pytest.raises(AssertionError, match="raw coefficients"):
        q.validate_output_directory(output, reference)


def test_other_genuine_config_cannot_be_relabelled(output, reference, genuine_outputs):
    copy_output(genuine_outputs["dti_all"], output)
    result = q.load_json(output/"diffusivity.json"); result["model_config"] = "dti_lowb"
    (output/"diffusivity.json").write_text(json.dumps(result))
    metadata = dict(reference["stats"]["metadata_by_config"]["dti_lowb"], status="ok",
                    n_wm_voxels=len(reference["ijk"]), n_brain_voxels=reference["stats"]["n_brain_voxels"])
    (output/"run_metadata.json").write_text(json.dumps(metadata))
    with pytest.raises(AssertionError, match="raw coefficients"):
        q.validate_output_directory(output, reference)


@pytest.mark.parametrize("mutation", ["drop_one", "half_roi", "duplicate", "fractional_coordinate", "foreign_coordinate", "missing_beta", "nonfinite_beta", "fractional_floor", "missing_fa"])
def test_incomplete_or_invalid_receipt(output, reference, mutation):
    rows = read_rows(output)
    if mutation == "drop_one": rows.pop()
    elif mutation == "half_roi": rows = rows[:len(rows)//2]
    elif mutation == "duplicate": rows.append(dict(rows[0]))
    elif mutation == "fractional_coordinate": rows[0]["i"] = float(rows[0]["i"])+.1
    elif mutation == "foreign_coordinate": rows[0]["i"] = 999
    elif mutation == "missing_beta":
        for row in rows: del row["beta_21"]
    elif mutation == "nonfinite_beta": rows[0]["beta_0"] = "nan"
    elif mutation == "fractional_floor": rows[0]["n_eigenvalues_floored"] = .1
    elif mutation == "missing_fa":
        for row in rows: del row["fa"]
    write_rows(output, rows)
    with pytest.raises(AssertionError): q.validate_output_directory(output, reference)


@pytest.mark.parametrize("key", q.METRICS)
def test_each_voxel_measurement_is_source_and_coefficient_bound(output, reference, key):
    rows = read_rows(output)
    old = float(rows[0][key]); rows[0][key] = old+max(1., abs(old)*.1)
    write_rows(output, rows)
    with pytest.raises(AssertionError): q.validate_output_directory(output, reference)


@pytest.mark.parametrize("key", ["md_mean", "fa_mean", "S0_hat_mean", "nrmse_mean", "log_rmse_mean", "n_wm_voxels",
                                 "n_signal_floored_total", "n_eigenvalues_floored_total", "n_voxels_signal_floored", "n_voxels_eigenvalues_floored"])
def test_each_headline_recomputed(output, reference, key):
    path = output/"diffusivity.json"; result = q.load_json(path)
    previous = result[key]
    result[key] += max(1, int(abs(previous)*.1)) if key.startswith("n_") else max(1., abs(previous)*.1)
    assert result[key] != previous
    path.write_text(json.dumps(result))
    with pytest.raises(AssertionError, match="summary"):
        q.validate_output_directory(output, reference)


def test_unit_guessing_is_not_accepted(output, reference):
    rows = read_rows(output)
    for row in rows: row["md"] = float(row["md"])*1e-3
    write_rows(output, rows)
    result = q.load_json(output/"diffusivity.json"); result["md_mean"] *= 1e-3; result["md_units"] = "mm^2/s"
    (output/"diffusivity.json").write_text(json.dumps(result))
    with pytest.raises(AssertionError, match="units"):
        q.validate_output_directory(output, reference)


@pytest.mark.parametrize("mutation", ["source", "config", "smoothing", "floor", "pinv_rcond", "shells", "geometry", "status", "roi_count", "brain_count"])
def test_wrong_public_metadata(output, reference, mutation):
    path = output/"run_metadata.json"; meta = q.load_json(path)
    if mutation == "source": meta["source_sha256"] = {}
    elif mutation == "config": meta["model_config"] = "dti_lowb"
    elif mutation == "smoothing": meta["preprocessing"]["smoothing"] = True
    elif mutation == "floor": meta["fit"]["signal_floor"] = 1e-3
    elif mutation == "pinv_rcond": meta["fit"]["pinv_rcond"] = 0
    elif mutation == "shells": meta["volume_indices"] = meta["volume_indices"][:-1]
    elif mutation == "geometry": meta["affine"][0][3] += 1
    elif mutation == "status": meta["status"] = "failed_precondition"
    elif mutation == "roi_count": meta["n_wm_voxels"] += 1
    elif mutation == "brain_count": meta["n_brain_voxels"] += 1
    path.write_text(json.dumps(meta))
    with pytest.raises(AssertionError): q.validate_output_directory(output, reference)


@pytest.mark.parametrize("filename", q.FILES)
def test_missing_artifact(output, reference, filename):
    (output/filename).unlink()
    with pytest.raises(AssertionError): q.validate_output_directory(output, reference)


def test_empty_findings(output, reference):
    (output/"findings.md").write_text(" \n")
    with pytest.raises(AssertionError, match="empty findings"):
        q.validate_output_directory(output, reference)
