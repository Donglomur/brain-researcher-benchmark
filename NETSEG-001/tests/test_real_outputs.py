"""Genuine source-output acceptance and controlled mutations; no new fits.

These require separately gated original outputs. Source-free runs exclude this
file; full integration must supply both genuine paths and have zero skips.
"""
import copy
import csv
import json
import os
from pathlib import Path
import shutil
import tempfile

import numpy as np
import pytest

import proof_of_work as p
import source_math as s
from test_authoring_regressions import write_csv, mutate_npz, mutate_json, reject


def configured(name):
    value = os.environ.get(name)
    if not value:
        pytest.skip(f"Original-source evidence not configured: {name}")
    path = Path(value)
    assert path.is_dir(), f"Configured original evidence is absent: {name}={path}"
    return path


@pytest.fixture(scope="session")
def original():
    return configured("REPAIR_ORACLE_OUTPUT")


@pytest.fixture
def output(original, tmp_path):
    # Each owned temporary copy is removed promptly, not retained 70 times.
    with tempfile.TemporaryDirectory(prefix="netseg-mutation-", dir=tmp_path) as folder:
        dest = Path(folder) / "output"
        shutil.copytree(original, dest)
        yield dest


def write_derived(output, reference, cleaned):
    own = s.derived(cleaned, reference["participant_id"],
                    [r["group"] for r in reference["participants"]], reference["parcel_id"],
                    [r["network"] for r in reference["parcels"]], reference["method"])
    mutate_npz(output, lambda a: a.update(standardized_clean=cleaned, **{
        k: own[k] for k in ("pearson_r", "fisher_z", "positive_z")}))
    write_csv(output / "segregation.csv", own["segregation"], reference["method"]["artifacts"]["segregation.csv"]["columns"])
    (output / "cohort_results.json").write_text(json.dumps(own["results"], allow_nan=False))


def test_genuine_oracle(original, source_reference):
    p.validate_output_directory(original, source_reference)


def test_genuine_independent(source_reference):
    p.validate_output_directory(configured("REPAIR_INDEPENDENT_OUTPUT"), source_reference)


def test_reordered_all_axes_tables_headers(output, source_reference):
    rng = np.random.default_rng(20261002)
    def permute(a):
        pi, fi, ri, ei = (rng.permutation(len(a[k])) for k in
                          ("participant_id", "frame_index", "parcel_id", "edge_i"))
        for name, order in (("participant_id", pi), ("frame_index", fi), ("parcel_id", ri), ("edge_i", ei), ("edge_j", ei)):
            a[name] = a[name][order]
        for name in ("raw_mean", "standardized_clean"):
            a[name] = a[name][np.ix_(pi, fi, ri)]
        for name in ("raw_sd", "residual_sd"):
            a[name] = a[name][np.ix_(pi, ri)]
        for name in ("pearson_r", "fisher_z", "positive_z"):
            a[name] = a[name][np.ix_(pi, ei)]
    mutate_npz(output, permute)
    for name in ("participants.csv", "parcels.csv", "segregation.csv"):
        with (output / name).open() as f:
            rows = list(csv.DictReader(f))
        write_csv(output / name, rows[::-1], list(rows[0])[::-1])
    mutate_json(output, "run_metadata.json", lambda m: m["source_observed"]["bold_headers"].reverse())
    p.validate_output_directory(output, source_reference)


def test_float32_primitives_own_recompute(output, source_reference):
    values = p.canonical_arrays(output / "connectivity.npz", source_reference)
    clean = values["standardized_clean"].astype(np.float32).astype(np.float64)
    write_derived(output, source_reference, clean)
    mutate_npz(output, lambda a: a.update({k: a[k].astype(np.float32) for k in
                ("raw_mean", "raw_sd", "residual_sd", "standardized_clean")}))
    p.validate_output_directory(output, source_reference)


def test_free_prose_extra_fields_alternate_versions(output, source_reference):
    (output / "findings.md").write_text("A computation on the supplied people, with its uncertainty left intact.\n")
    mutate_json(output, "cohort_results.json", lambda x: x.update(optional_signed={"estimate": -123.0}))
    mutate_json(output, "run_metadata.json", lambda x: x.update(software_versions={"independent": 2},
                                                               warnings=[{"category": "information", "message": "actual stack"}], extra=None))
    p.validate_output_directory(output, source_reference)


def test_integral_scientific_notation_keys(output, source_reference):
    mutate_npz(output, lambda a: a.update({k: a[k].astype(float) for k in
                                          ("frame_index", "parcel_id", "edge_i", "edge_j")}))
    with (output / "parcels.csv").open() as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        for k in ("parcel_id", "source_lut_row_index", "native_voxel_count", "target_voxel_count"):
            row[k] += "e0"
    write_csv(output / "parcels.csv", rows, list(rows[0]))
    p.validate_output_directory(output, source_reference)


@pytest.mark.parametrize("array", ["raw_mean", "standardized_clean", "raw_sd", "residual_sd", "pearson_r", "fisher_z", "positive_z"])
def test_numerical_array_mismatch(output, source_reference, array):
    mutate_npz(output, lambda a: a[array].__setitem__(tuple([0]*a[array].ndim), a[array].flat[0] + max(1., abs(a[array].flat[0])*.01)))
    reject(output, source_reference)


@pytest.mark.parametrize("mode", ["clean_negation", "clean_column_swap", "wrong_frame", "raw_scale", "clean_offset"])
def test_coherent_wrong_primitives(output, source_reference, mode, record_property):
    values = p.canonical_arrays(output / "connectivity.npz", source_reference)
    clean = values["standardized_clean"].copy()
    if mode == "clean_negation": clean[:, :, 0] *= -1
    elif mode == "clean_column_swap": clean[:, :, [1, 2]] = clean[:, :, [2, 1]]
    elif mode == "wrong_frame": clean[:, 0, 0] += .1
    elif mode == "clean_offset": clean += .01  # own Pearson unchanged; primitive binding still rejects
    else:
        mutate_npz(output, lambda a: a["raw_mean"].__imul__(.001))
        actual = values["raw_mean"] * .001
        canonical = source_reference["raw_mean"]
        tol = source_reference["method"]["tolerances"]["raw_receipt"]
        effective = np.any(np.abs(actual-canonical) > tol["atol"] + tol["rtol"]*np.abs(canonical))
        if effective:
            reject(output, source_reference, "source raw_mean")
        else:
            p.validate_output_directory(output, source_reference)
        record_property("control_status", "effective_rejected" if effective else "control_not_discriminating")
        return
    write_derived(output, source_reference, clean)
    tol = source_reference["method"]["tolerances"]["standardized_clean_source"]
    canonical = source_reference["standardized_clean"]
    effective = np.any(np.abs(clean-canonical) > tol["atol"] + tol["rtol"]*np.abs(canonical))
    if effective:
        reject(output, source_reference, "source standardized_clean")
    else:
        p.validate_output_directory(output, source_reference)
    record_property("control_status", "effective_rejected" if effective else "control_not_discriminating")


@pytest.mark.parametrize("key", ["participant_id", "frame_index", "parcel_id", "edge"])
def test_duplicate_axis(output, source_reference, key):
    def wrong(a):
        if key == "edge":
            a["edge_i"][0] = a["edge_i"][1]; a["edge_j"][0] = a["edge_j"][1]
        else: a[key][0] = a[key][1]
    mutate_npz(output, wrong)
    reject(output, source_reference)


@pytest.mark.parametrize("mode", ["drop_raw", "drop_edge", "nonfinite_raw", "nonfinite_clean", "boolean_frame", "object_raw", "transpose", "reverse_edge"])
def test_invalid_tensor(output, source_reference, mode):
    def wrong(a):
        if mode == "drop_raw": a["raw_mean"] = a["raw_mean"][:-1]
        elif mode == "drop_edge": a["fisher_z"] = a["fisher_z"][:, :-1]
        elif mode == "nonfinite_raw": a["raw_mean"][0, 0, 0] = np.nan
        elif mode == "nonfinite_clean": a["standardized_clean"][0, 0, 0] = np.inf
        elif mode == "boolean_frame": a["frame_index"] = a["frame_index"].astype(bool)
        elif mode == "object_raw": a["raw_mean"] = a["raw_mean"].astype(object)
        elif mode == "transpose": a["standardized_clean"] = a["standardized_clean"].transpose(0, 2, 1)
        else: a["edge_i"], a["edge_j"] = a["edge_j"], a["edge_i"]
    mutate_npz(output, wrong)
    reject(output, source_reference)


@pytest.mark.parametrize("field", ["source_manifest_sha256", "method_contract_sha256", "source_sha256", "status", "method_id", "units", "scale", "header_count", "tr"])
def test_source_metadata_mismatch(output, source_reference, field):
    def wrong(m):
        if field in ("source_manifest_sha256", "method_contract_sha256"): m[field] = "0"*64
        elif field == "source_sha256": m[field]["extra"] = "0"*64
        elif field == "status": m[field] = "failed_precondition"
        elif field == "method_id": m[field] = "other"
        elif field == "units": m["source_observed"]["bold_headers"][0]["temporal_units"] = "sec"
        elif field == "scale": m["source_observed"]["bold_headers"][0]["intensity_slope"] *= 2.
        elif field == "header_count": m["source_observed"]["bold_headers"].pop()
        else: m["source_observed"]["tr_seconds_used"] = 1.
    mutate_json(output, "run_metadata.json", wrong)
    reject(output, source_reference)


@pytest.mark.parametrize("name,key,mode", [(n,k,m) for n,k in
    (("participants.csv", "participant_id"), ("parcels.csv", "parcel_id"), ("segregation.csv", "participant_id"))
    for m in ("drop", "duplicate", "identity")])
def test_incomplete_table(output, source_reference, name, key, mode):
    with (output / name).open() as f:
        rows = list(csv.DictReader(f))
    fields = list(rows[0])
    if mode == "drop": rows.pop()
    elif mode == "duplicate": rows.append(rows[0].copy())
    else: rows[0][key] = "999" if key == "parcel_id" else "sub-pixar999"
    write_csv(output / name, rows, fields)
    reject(output, source_reference)


@pytest.mark.parametrize("field", ["group", "age", "nuisance_rank", "bold_path"])
def test_participant_receipt_contradiction(output, source_reference, field):
    with (output / "participants.csv").open() as f:
        rows = list(csv.DictReader(f))
    if field == "group": rows[0][field] = "adult" if rows[0][field] == "child" else "child"
    elif field == "age": rows[0][field] = str(float(rows[0][field])+1)
    elif field == "nuisance_rank": rows[0][field] = str(int(rows[0][field])+1)
    else: rows[0][field] = "not-original.nii.gz"
    write_csv(output / "participants.csv", rows, list(rows[0]))
    reject(output, source_reference)


@pytest.mark.parametrize("name", ["participants.csv", "parcels.csv", "connectivity.npz", "segregation.csv", "cohort_results.json", "run_metadata.json", "findings.md"])
def test_missing_file(output, source_reference, name):
    (output / name).unlink()
    reject(output, source_reference)


@pytest.mark.parametrize("mode", ["empty", "late_failed", "dangling"])
def test_authoritative_failure_marker(output, source_reference, mode):
    if mode == "dangling": (output / "failure_receipt.json").symlink_to(output / "absent")
    else: (output / "failure_receipt.json").write_text("" if mode == "empty" else '{"status":"failed_precondition"}')
    reject(output, source_reference, "failure_receipt")


@pytest.mark.parametrize("mode", ["coherent_shift", "wrong_pair_counts", "undefined_filled", "json_bool", "json_infinite"])
def test_derived_summary_wrong(output, source_reference, mode):
    if mode in ("coherent_shift", "wrong_pair_counts", "undefined_filled"):
        with (output / "segregation.csv").open() as f:
            rows = list(csv.DictReader(f))
        if mode == "coherent_shift":
            for row in rows:
                if row["segregation"]: row["segregation"] = str(float(row["segregation"])+.04)
                else: row["segregation"] = ".04"
        elif mode == "wrong_pair_counts": rows[0]["n_within_pairs"] = str(int(rows[0]["n_within_pairs"])-1)
        elif rows[0]["segregation"] == "": rows[0]["segregation"], rows[0]["status"] = "0", "ok"
        else: rows[0]["segregation"], rows[0]["status"] = "", "zero_within_mean"
        write_csv(output / "segregation.csv", rows, list(rows[0]))
        if mode == "coherent_shift":
            def shift(obj):
                for g in [obj["cohort"], *obj["groups"].values()]:
                    if g["mean"] is not None: g["mean"] += .04
            mutate_json(output, "cohort_results.json", shift)
    elif mode == "json_bool": mutate_json(output, "cohort_results.json", lambda x: x.update(n_undefined=False))
    else: mutate_json(output, "run_metadata.json", lambda x: x.update(extra={"x": float("inf")}))
    reject(output, source_reference)
