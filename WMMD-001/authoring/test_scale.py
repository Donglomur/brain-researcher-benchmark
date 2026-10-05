"""Invented tiny arrays test mechanics only; no scientific bank or source fits."""
import csv
import json
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"tests"))
import proof_of_work as q


@pytest.fixture
def small_reference():
    b = np.array([0, 200, 400, 800, 1000, 1200, 1600, 2000, 2600, 3000.])
    g = np.array([[0,0,0], [1,0,0], [0,1,0], [0,0,1], [1,1,0], [1,0,1],
                  [0,1,1], [1,-1,1], [-1,1,1], [1,1,1]], float)
    g[1:] /= np.linalg.norm(g[1:], axis=1)[:, None]
    beta = np.zeros((6, 7)); beta[:, 0] = .001; beta[:, 2] = .0006; beta[:, 5] = .0003
    beta[:, -1] = -np.log(np.arange(100, 160, 10))
    beta[0, 0] = -.00002
    signal = np.exp(beta @ q.design_matrix(b, g, "dti_all").T)
    signal[0, [0, -1]] = 0
    reference = {"ijk": np.array([[i, 0, 0] for i in range(6)]), "signal": signal,
                 "bvals": b, "bvecs": g, "configs": {}, "stats": {
        "pipeline_id": q.PIPELINE_ID, "source_sha256": {"mechanical_fixture": "1"*64},
        "n_brain_voxels": 10, "metadata_by_config": {}, "results_by_config": {},
    }}
    for config in q.CONFIGS:
        indices = np.flatnonzero(np.round(b, -2) <= 1000) if config == "dti_lowb" else np.arange(len(b))
        design = q.design_matrix(b[indices], g[indices], config)
        coefficients = np.zeros((6, design.shape[1]))
        coefficients[:, :6] = beta[:, :6]; coefficients[:, -1] = beta[:, -1]
        if config == "dki_all": coefficients[:, 6] = 1e-7
        if config == "dti_lowb": coefficients[:, 2] *= 1.01
        derived = q.derive(coefficients, signal[:, indices], design, b[indices])
        reference["configs"][config] = {"indices": indices, "design": design, "beta": coefficients,
                                        **{name: derived[name] for name in q.METRICS}}
        reference["stats"]["metadata_by_config"][config] = {
            "pipeline_id": q.PIPELINE_ID, "model_config": config, "dataset_id": "mechanical_fixture_not_data",
            "source_sha256": reference["stats"]["source_sha256"], "shape": [6, 1, 1],
            "preprocessing": {"smoothing": False, "signal_floor": 1e-4},
        }
        reference["stats"]["results_by_config"][config] = q.summarize(config, derived)
    return q.validate_reference(reference)


def write_rows(output, rows, columns=None):
    with (output/"md_voxelwise.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns or list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def read_rows(output):
    with (output/"md_voxelwise.csv").open(newline="") as stream:
        return list(csv.DictReader(stream))


def write_output(output, reference, config, beta=None):
    output.mkdir(parents=True, exist_ok=True)
    entry = reference["configs"][config]
    beta = entry["beta"] if beta is None else beta
    values = q.derive(beta, reference["signal"][:, entry["indices"]], entry["design"], reference["bvals"][entry["indices"]])
    rows = [{"i": int(xyz[0]), "j": int(xyz[1]), "k": int(xyz[2]),
             **{key: int(values[key][i]) if key in q.INTEGER_METRICS else float(values[key][i]) for key in q.METRICS},
             **{f"beta_{j}": float(value) for j, value in enumerate(beta[i])}}
            for i, xyz in enumerate(reference["ijk"])]
    write_rows(output, rows)
    (output/"diffusivity.json").write_text(json.dumps(q.summarize(config, values)))
    metadata = dict(reference["stats"]["metadata_by_config"][config], status="ok",
                    n_wm_voxels=len(reference["ijk"]), n_brain_voxels=reference["stats"]["n_brain_voxels"])
    (output/"run_metadata.json").write_text(json.dumps(metadata))
    (output/"findings.md").write_text("Mechanical numerical fixture, not a measured brain result.")
    return output


@pytest.fixture
def output(tmp_path, small_reference):
    return write_output(tmp_path, small_reference, "dki_all")


@pytest.mark.parametrize("config", q.CONFIGS)
def test_one_configuration_is_sufficient(tmp_path, small_reference, config):
    q.validate_output_directory(write_output(tmp_path, small_reference, config), small_reference)


@pytest.mark.parametrize("factor", [1e-3, 1.01, 1e3, -1])
def test_coherent_scaled_coefficients_and_all_summaries_do_not_pass(output, small_reference, factor):
    beta = small_reference["configs"]["dki_all"]["beta"].copy()
    beta[:, :6] *= factor
    write_output(output, small_reference, "dki_all", beta)
    with pytest.raises(AssertionError, match="raw coefficients"):
        q.validate_output_directory(output, small_reference)


def test_coherent_wrong_model_cannot_be_relabelled(tmp_path, small_reference):
    output = write_output(tmp_path, small_reference, "dti_all")
    metadata = small_reference["stats"]["metadata_by_config"]["dti_lowb"]
    result = q.load_json(output/"diffusivity.json"); result["model_config"] = "dti_lowb"
    (output/"diffusivity.json").write_text(json.dumps(result))
    (output/"run_metadata.json").write_text(json.dumps(dict(metadata, status="ok", n_wm_voxels=6, n_brain_voxels=10)))
    with pytest.raises(AssertionError, match="raw coefficients"):
        q.validate_output_directory(output, small_reference)


def test_units_are_explicit_not_inferred_from_magnitude(output, small_reference):
    result = q.load_json(output/"diffusivity.json"); result["md_units"] = "mm^2/s"
    (output/"diffusivity.json").write_text(json.dumps(result))
    with pytest.raises(AssertionError, match="units"):
        q.validate_output_directory(output, small_reference)
