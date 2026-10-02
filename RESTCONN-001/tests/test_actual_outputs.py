"""Gated actual-output tests, authored before any original result inspection.

Not part of manufactured-only qualification. Requires REPAIR_ORACLE_OUTPUT;
missing configuration fails rather than silently skipping. Uses conftest's
single source reconstruction. Original files are read-only; every mutation is
on a detached per-test copy. An ineffective/undefined component control is
reported separately and never counted as a demonstrated negative.
"""
import copy
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import shutil

import numpy as np
import pytest

import artifact_reader as a
import circular_contract as c
import proof_of_work as p


def file_hashes(root):
    return {name: hashlib.sha256(a.read_bytes(root / name, 64*2**20)).hexdigest() for name in a.REQUIRED}


@pytest.fixture(scope="session")
def actual_original(original_reference):
    path = os.environ.get("REPAIR_ORACLE_OUTPUT")
    assert path, "REPAIR_ORACLE_OUTPUT must be explicitly configured for actual-output controls"
    root = a.guarded_path(path, directory=True)
    before = file_hashes(root)
    assert p.validate_output_directory(root, original_reference)["status"] == "accepted"
    yield root
    assert file_hashes(root) == before, "original artifacts changed during controls"


@pytest.fixture
def candidate(tmp_path, actual_original):
    out = tmp_path / "detached-output"; out.mkdir()
    for name in a.REQUIRED: shutil.copyfile(actual_original / name, out / name)
    yield out
    # Only this fixture's validated, newly-created exact directory is removed.
    shutil.rmtree(out)


def arrays(path):
    with np.load(path, allow_pickle=False) as archive: return {k: archive[k].copy() for k in archive.files}


def write_json(path, value):
    path.write_text(json.dumps(value, allow_nan=False, indent=2) + "\n")


def own_arrays(output, reference):
    raw = a.parse_npz(a.read_bytes(output / "raw_map_coefficients.npz", a.CAPS["npz"]))
    rows = a.parse_csv(a.read_bytes(output / "timeseries.csv", a.CAPS["csv"]))
    return c.canonical_primitives(raw, rows, reference)


def write_series(output, clean):
    with (output / "timeseries.csv").open("w", newline="") as stream:
        writer = csv.writer(stream); writer.writerow(["frame_index", *c.TARGETS])
        writer.writerows([i, *map(float, row)] for i, row in enumerate(clean))


@pytest.mark.parametrize("mode", ["baseline", "key_permutations", "metadata_permutations", "finite_extras", "float32_roundtrip", "source_close_own_replay"])
def test_actual_equivalent_positive(candidate, original_reference, mode, record_property):
    record_property("case_role", "genuine_positive")
    if mode == "key_permutations":
        path = candidate / "raw_map_coefficients.npz"; data = arrays(path)
        data["frame_indices"] = data["frame_indices"][::-1].astype(float)
        data["map_ids"] = data["map_ids"][::-1].astype(float)
        data["map_labels"] = data["map_labels"][::-1].astype("S")
        data["raw_coefficients"] = data["raw_coefficients"][::-1, ::-1]
        data["participant_id"] = data["participant_id"].astype("S"); np.savez(path, **data)
        with (candidate / "timeseries.csv").open() as stream: rows = list(csv.DictReader(stream))
        fields = [*reversed(list(rows[0]))]
        with (candidate / "timeseries.csv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader(); writer.writerows(rows[::-1])
        report = json.loads((candidate / "connectivity.json").read_text())
        for key in ("shifts", "null_r", "exceeds"): report["inference"][key].reverse()
        write_json(candidate / "connectivity.json", report)
    if mode == "metadata_permutations":
        metadata = json.loads((candidate / "run_metadata.json").read_text())
        metadata["source_files"].reverse(); metadata["source_observed"]["map_labels"].reverse()
        metadata["analysis_observed"]["target_support"].reverse()
        write_json(candidate / "run_metadata.json", metadata)
    if mode == "finite_extras":
        report = json.loads((candidate / "connectivity.json").read_text()); report["optional_note"] = {"value": 1., "text": "Unscored explanation"}
        write_json(candidate / "connectivity.json", report)
        path = candidate / "raw_map_coefficients.npz"; data = arrays(path); data["optional_array"] = np.zeros((1,)*9); np.savez(path, **data)
        (candidate / "findings.md").write_text("Independent descriptive wording; no required keywords.\n")
    if mode in ("float32_roundtrip", "source_close_own_replay"):
        _, clean = own_arrays(candidate, original_reference)
        if mode == "float32_roundtrip":
            clean = clean.astype(np.float32).astype(float)
            path = candidate / "raw_map_coefficients.npz"; data = arrays(path)
            data["raw_coefficients"] = data["raw_coefficients"].astype(np.float32); np.savez(path, **data)
        else: clean = clean + 1e-9*np.sin(np.arange(len(clean)))[:, None]
        write_series(candidate, clean)
        write_json(candidate / "connectivity.json", c.circular_evidence(clean, original_reference["active"]))
    assert p.validate_output_directory(candidate, original_reference)["status"] == "accepted"
    record_property("control_status", "positive_accepted")


@pytest.mark.parametrize("mode", ["raw_wrong", "final_wrong_coherent", "subject_digits", "raw_map_missing", "frame_missing", "source_pin", "method_pin", "support_flip", "rank_wrong", "failure_marker"])
def test_actual_effective_binding_negative(candidate, original_reference, mode, record_property):
    record_property("case_role", "binding_negative")
    if mode in ("raw_wrong", "subject_digits", "raw_map_missing", "frame_missing"):
        path = candidate / "raw_map_coefficients.npz"; data = arrays(path)
        if mode == "raw_wrong":
            previous = float(data["raw_coefficients"][0, 0])
            data["raw_coefficients"][0, 0] += 100*(c.RAW_ATOL+c.RAW_RTOL*abs(previous)) + .001
            assert data["raw_coefficients"][0, 0] != previous
        if mode == "subject_digits": data["participant_id"] = np.array("10064")
        if mode == "raw_map_missing": data["raw_coefficients"] = data["raw_coefficients"][:, :-1]
        if mode == "frame_missing":
            data["frame_indices"] = data["frame_indices"][:-1]; data["raw_coefficients"] = data["raw_coefficients"][:-1]
        np.savez(path, **data)
        with pytest.raises(ValueError): own_arrays(candidate, original_reference)
    elif mode == "final_wrong_coherent":
        _, clean = own_arrays(candidate, original_reference); clean[:, 0] += 1.
        write_series(candidate, clean)
        # This offset leaves correlation unchanged mathematically; source binding
        # still rejects the incorrect pre-inference cleaned component.
        write_json(candidate / "connectivity.json", c.circular_evidence(clean, original_reference["active"]))
        with pytest.raises(ValueError): own_arrays(candidate, original_reference)
    elif mode == "failure_marker": (candidate / "failure_report.json").symlink_to(candidate / "absent")
    else:
        metadata = json.loads((candidate / "run_metadata.json").read_text())
        if mode == "source_pin": metadata["source_manifest_sha256"] = "0"*64
        if mode == "method_pin": metadata["method_sha256"] = "0"*64
        if mode == "support_flip": metadata["analysis_observed"]["target_support"][0]["active"] = not metadata["analysis_observed"]["target_support"][0]["active"]
        if mode == "rank_wrong": metadata["analysis_observed"]["map_rank"] += 1
        write_json(candidate / "run_metadata.json", metadata)
    with pytest.raises(ValueError): p.validate_output_directory(candidate, original_reference)
    record_property("control_status", "effective_rejection")


def component_candidate(clean, active, mode):
    expected = c.circular_evidence(clean, active); actual = copy.deepcopy(expected)
    if expected["status"] != "ok": return expected, actual, False, "canonical_pair_inactive"
    n = len(clean); inference = actual["inference"]
    x, y = (c.center_scaled(clean[:, k]) for k in range(2))
    dots = [math.fsum(float(x[(t-k)%n])*float(y[t]) for t in range(n)) for k in range(n)]
    if mode == "reverse_shift":
        inference["null_r"].reverse(); inference["exceeds"].reverse()
    elif mode == "abs_observed": actual["r"] = abs(actual["r"])
    elif mode == "no_plus_one":
        numerator = inference["n_exceedances"]; denominator = n-1
        inference.update(numerator=numerator, denominator=denominator, p_value=numerator/denominator, significant=20*numerator<denominator)
        actual.update(p_value=inference["p_value"], significant=inference["significant"])
    elif mode in ("strict_greater", "one_sided", "rounded_rank"):
        if mode == "strict_greater": exceeds = [abs(v)>abs(dots[0]) for v in dots[1:]]
        elif mode == "one_sided": exceeds = [v>=dots[0] for v in dots[1:]]
        else:
            inference["null_r"] = [round(v, 6) for v in inference["null_r"]]; actual["r"] = round(actual["r"], 6)
            exceeds = [abs(v)>=abs(actual["r"]) for v in inference["null_r"]]
        count = sum(exceeds); numerator = 1+count
        inference.update(exceeds=exceeds, n_exceedances=count, numerator=numerator, p_value=numerator/n, significant=20*numerator<n)
        actual.update(p_value=inference["p_value"], significant=inference["significant"])
    else: raise AssertionError("unknown component control")
    # Independent explicit observable comparison, not inference from acceptance.
    changed = any(actual[k] != expected[k] for k in ("significant",))
    changed |= abs(actual["r"]-expected["r"]) > c.RECEIPT_ATOL
    changed |= abs(actual["p_value"]-expected["p_value"]) > c.RECEIPT_ATOL
    changed |= any(inference[k] != expected["inference"][k] for k in ("exceeds", "n_exceedances", "numerator", "denominator", "significant"))
    changed |= any(abs(a-b)>c.RECEIPT_ATOL for a, b in zip(inference["null_r"], expected["inference"]["null_r"]))
    return expected, actual, bool(changed), "constructed"


@pytest.mark.parametrize("mode", ["reverse_shift", "abs_observed", "no_plus_one", "strict_greater", "one_sided", "rounded_rank"])
def test_actual_component_controls(candidate, original_reference, mode, record_property):
    record_property("case_role", "circular_component_control")
    _, clean = own_arrays(candidate, original_reference)
    expected, altered, effective, construction = component_candidate(clean, original_reference["active"], mode)
    preserved = {name: hashlib.sha256((candidate/name).read_bytes()).hexdigest() for name in a.REQUIRED if name != "connectivity.json"}
    write_json(candidate / "connectivity.json", altered)
    assert preserved == {name: hashlib.sha256((candidate/name).read_bytes()).hexdigest() for name in preserved}
    record_property("observed_status", expected["status"])
    record_property("construction", construction)
    if effective:
        with pytest.raises(ValueError): c.validate_report(altered, expected)
        with pytest.raises(ValueError): p.validate_output_directory(candidate, original_reference)
        record_property("control_status", "effective_rejection")
    else:
        assert c.validate_report(altered, expected)["status"] == "accepted"
        assert p.validate_output_directory(candidate, original_reference)["status"] == "accepted"
        record_property("control_status", "control_not_constructed" if construction != "constructed" else "control_not_discriminating")
