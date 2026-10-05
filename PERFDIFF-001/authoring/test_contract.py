"""Parser/linkage mechanics; miniature arrays are not a scientific bank."""
import copy
import csv
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
from proof_of_work import (METHODS, FLAGS, STATUSES, bound_flags, load_parameters, load_f_map,
    match_contract, normalized_predictions, signal_nrmse, ordered_rows, source_masks)
from ivim_contract import validate_parameters, validate_f_maps, validate_metadata


def write_rows(path, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def parameter_rows():
    return [dict(i="90.0", j=90, k=33, method=name, S0=1000., f=.2, Dstar=.02, D=.001,
                 status="ok", nrmse=.01, optimizer_status=2, nfev=10, bound_flags="",
                 init_projected="false", fallback="false", eligible="true", common_valid="true",
                 component_swap="false", context="extra permitted") for name in METHODS]


@pytest.mark.parametrize("defect", [None, "fractional_coord", "negative_coord", "duplicate",
    "unknown_method", "one_method", "missing_column", "inf", "bad_bool", "bad_status",
    "bad_optimizer", "fractional_nfev", "excess_nfev", "unknown_bound", "duplicate_bound"])
def test_strict_parameter_parser(tmp_path, defect):
    rows = parameter_rows()
    if defect == "fractional_coord": rows[0]["i"] = "90.1"
    elif defect == "negative_coord": rows[0]["i"] = "-1"
    elif defect == "duplicate": rows.append(dict(rows[0]))
    elif defect == "unknown_method": rows[0]["method"] = "trr"
    elif defect == "one_method": rows.pop()
    elif defect == "missing_column":
        for row in rows: row.pop("Dstar")
    elif defect == "inf": rows[0]["S0"] = "inf"
    elif defect == "bad_bool": rows[0]["eligible"] = "maybe"
    elif defect == "bad_status": rows[0]["status"] = "fallback_success"
    elif defect == "bad_optimizer": rows[0]["optimizer_status"] = "1.1"
    elif defect == "fractional_nfev": rows[0]["nfev"] = "3.5"
    elif defect == "excess_nfev": rows[0]["nfev"] = 1001
    elif defect == "unknown_bound": rows[0]["bound_flags"] = "physiological"
    elif defect == "duplicate_bound": rows[0]["bound_flags"] = "f_lower|f_lower"
    path = tmp_path / "parameters.csv"
    write_rows(path, rows)
    if defect is None:
        assert set(load_parameters(path)) == set(METHODS)
    else:
        with pytest.raises((AssertionError, ValueError)):
            load_parameters(path)


@pytest.mark.parametrize("defect", [None, "fractional", "duplicate", "inf", "missing"])
def test_fmap_parser(tmp_path, defect):
    rows = [dict(i=90, j=90, k=33, f=.1), dict(i=90, j=91, k=33, f="")]
    if defect == "fractional": rows[0]["k"] = 33.1
    elif defect == "duplicate": rows.append(dict(rows[0]))
    elif defect == "inf": rows[0]["f"] = "inf"
    elif defect == "missing":
        for row in rows: row.pop("f")
    path = tmp_path / "f.csv"
    write_rows(path, rows)
    if defect is None:
        values = load_f_map(path)
        assert np.isnan(values[(90, 91, 33)])
    else:
        with pytest.raises((AssertionError, ValueError)):
            load_f_map(path)


def mechanics_example():
    # Two rows only, deliberately incapable of passing load_reference's900-row source checks.
    keys = [(90, 90, 33), (90, 91, 33)]
    bvals = np.array([0., 100., 200., 400.])
    signal = np.array([[1000., 800., 700., 600.], [1000., 850., 750., 650.]])
    params = np.array([[1000., .2, .02, .001], [1000., -.1, np.nan, .002]])
    ref = {"keys": keys, "signal": signal, "bvals": bvals, "eligible": np.ones(2, bool), "methods": {}}
    groups = {}
    for name in METHODS:
        normalized = normalized_predictions(params, signal, bvals)
        residual = signal_nrmse(params, signal, bvals)
        ref["methods"][name] = {"params": params.copy(), "status": np.array(["ok", "segmented_out_of_bounds"]),
            "init_projected": np.zeros(2, bool), "fallback": np.zeros(2, bool),
            "component_swap": np.zeros(2, bool), "normalized_predictions": normalized}
        groups[name] = {key: dict(params=params[index].copy(), status=ref["methods"][name]["status"][index],
            nrmse=residual[index], optimizer_status=2 if index == 0 else float("nan"), nfev=10 if index == 0 else 0,
            bound_flags=bound_flags(params[index], 1000.), init_projected=False, fallback=False,
            eligible=True, common_valid=index == 0, component_swap=False) for index, key in enumerate(keys)}
    return ref, groups


@pytest.mark.parametrize("defect", [None, "partial", "padding", "wrong_D", "wrong_S0", "wrong_status",
    "fallback", "eligibility", "common_valid", "residual", "undefined", "bad_bound", "optimizer_failure",
    "nfev_zero", "fake_nosolver", "noncanonical_params"])
def test_source_linkage_mechanics(defect):
    ref, groups = mechanics_example()
    row = groups[METHODS[0]][ref["keys"][0]]
    if defect == "partial": groups[METHODS[0]].pop(ref["keys"][0])
    elif defect == "padding": groups[METHODS[0]][(900, 0, 0)] = groups[METHODS[0]].pop(ref["keys"][0])
    elif defect == "wrong_D": row["params"][3] += .0001
    elif defect == "wrong_S0": row["params"][0] += 1.
    elif defect == "wrong_status": row["status"] = "optimizer_failed"
    elif defect == "fallback": row["fallback"] = True
    elif defect == "eligibility": row["eligible"] = False
    elif defect == "common_valid": row["common_valid"] = False
    elif defect == "residual": row["nrmse"] += .01
    elif defect == "undefined": row["params"][2] = np.nan
    elif defect == "bad_bound": row["bound_flags"] = "f_upper"
    elif defect == "optimizer_failure": row["optimizer_status"] = 0
    elif defect == "nfev_zero": row["nfev"] = 0
    elif defect == "fake_nosolver":
        second = groups[METHODS[0]][ref["keys"][1]]
        second["optimizer_status"], second["nfev"] = 2, 10
    elif defect == "noncanonical_params":
        row["params"][[2, 3]] = row["params"][[3, 2]]
    if defect is None:
        arrays, common = validate_parameters(groups, ref)
        assert common.tolist() == [True, False]
    else:
        with pytest.raises((AssertionError, ValueError)):
            validate_parameters(groups, ref)


def test_optimizer_history_not_bitwise_identity():
    ref, groups = mechanics_example()
    groups[METHODS[0]][ref["keys"][0]]["optimizer_status"] = 3
    groups[METHODS[0]][ref["keys"][0]]["nfev"] = 11
    validate_parameters(groups, ref)


def test_f_maps_must_join_parameter_rows():
    ref, groups = mechanics_example()
    sweep = {name: {key: row["params"][1] for key, row in rows.items()} for name, rows in groups.items()}
    validate_f_maps(sweep[METHODS[0]], sweep, groups, ref, METHODS[0])
    altered = copy.deepcopy(sweep)
    altered[METHODS[1]][ref["keys"][0]] += .01
    with pytest.raises(AssertionError, match="linkage"):
        validate_f_maps(sweep[METHODS[0]], altered, groups, ref, METHODS[0])


def test_source_mask_excludes_nonfinite_signals_without_deleting_coordinates():
    signal = np.array([[1000., 500.], [np.inf, 500.], [100., 50.], [1000., 0.]])
    tissue, eligible = source_masks(signal, np.array([0., 100.]))
    assert tissue.tolist() == [True, False, False, True]
    assert eligible.tolist() == [True, False, False, False]


@pytest.mark.parametrize("defect", [None, "wrong_hash", "extra_hash", "wrong_primary", "missing_status", "wrong_methods", "missing_recipe"])
def test_required_public_metadata(defect):
    source = {"image": "a"*64}
    contract = {"pipeline_id": "example", "source_sha256": source, "recipe": {"cutoff": 200}}
    reference = {"stats": {"metadata_contract": contract, "source_sha256": source}, "keys": [(90,90,33)],
                 "tissue_eligible": np.array([True]), "eligible": np.array([True]), "common_valid": np.array([True]),
                 "methods": {name: {"status": np.array(["ok"])} for name in METHODS}}
    metadata = {**copy.deepcopy(contract), "status": "ok", "primary_method": METHODS[0], "fitted_methods": list(METHODS),
                "n_box_voxels": 1, "n_tissue_voxels": 1, "n_eligible_voxels": 1, "n_common_valid_voxels": 1,
                "status_counts": {name: {status: int(status == "ok") for status in STATUSES} for name in METHODS}}
    if defect == "wrong_hash": metadata["source_sha256"]["image"] = "b"*64
    elif defect == "extra_hash": metadata["source_sha256"]["extra"] = "b"*64
    elif defect == "wrong_primary": metadata["primary_method"] = METHODS[1]
    elif defect == "missing_status": metadata.pop("status")
    elif defect == "wrong_methods": metadata["fitted_methods"] = [METHODS[0]]*2
    elif defect == "missing_recipe": metadata.pop("recipe")
    if defect is None:
        validate_metadata(metadata, reference, METHODS[0])
    else:
        with pytest.raises((AssertionError, KeyError)):
            validate_metadata(metadata, reference, METHODS[0])
