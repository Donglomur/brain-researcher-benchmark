"""Prospective five-artifact verifier. Source reconstruction is caller-owned.

Metadata and all39 raw coefficients are receipts. Only accepted source-close
final series govern recomputed signed r, all offsets, rank, p and significance.
"""
from __future__ import annotations

import numpy as np

import artifact_reader as a
import circular_contract as c


def match(actual, expected, name, *, atol=1e-9, rtol=1e-9):
    if isinstance(expected, dict):
        a.require(isinstance(actual, dict) and set(expected) <= set(actual), name + ": required object fields")
        for key, value in expected.items(): match(actual[key], value, name + "." + key, atol=atol, rtol=rtol)
    elif isinstance(expected, list):
        a.require(isinstance(actual, list) and len(actual) == len(expected), name + ": list length")
        for i, value in enumerate(expected): match(actual[i], value, name + f"[{i}]", atol=atol, rtol=rtol)
    elif expected is None:
        a.require(actual is None, name + ": null")
    elif type(expected) is bool:
        a.require(type(actual) is bool and actual == expected, name + ": Boolean")
    elif type(expected) is int:
        a.require(a.integer(actual, json_number=True) == expected, name + ": exact integer")
    elif isinstance(expected, str):
        a.require(isinstance(actual, str) and actual == expected, name + ": literal")
    else:
        value = a.real(actual, json_number=True)
        a.require(abs(value - float(expected)) <= atol + rtol * abs(float(expected)), name + ": numeric precision")


def keyed_records(records, key, *, numeric=False):
    a.require(isinstance(records, list), "metadata record list")
    result = {}
    for row in records:
        a.require(isinstance(row, dict) and key in row, "metadata record key")
        value = a.integer(row[key], json_number=True) if numeric else row[key]
        a.require(type(value) in (str, int) and not isinstance(value, bool) and value not in result, "metadata duplicate/type key")
        result[value] = row
    return result


def record_match(actual, expected, key, *, numeric=False, atol=1e-9, rtol=1e-9):
    have, want = keyed_records(actual, key, numeric=numeric), keyed_records(expected, key, numeric=numeric)
    a.require(set(have) == set(want), "metadata complete record identities")
    for identity in want: match(have[identity], want[identity], str(identity), atol=atol, rtol=rtol)


def header_match(actual, expected):
    a.require(isinstance(actual, dict) and set(expected) <= set(actual), "header fields")
    for key, value in expected.items():
        if key == "storage_dtype":
            a.require(isinstance(actual[key], str), "storage_dtype text")
            try: equal = np.dtype(actual[key]) == np.dtype(value)
            except (TypeError, ValueError) as exc: raise a.ArtifactError("invalid storage_dtype") from exc
            a.require(equal, "storage_dtype source")
        else: match(actual[key], value, "header." + key)


def validate_metadata(actual, basis):
    c.finite_json(actual)
    want = basis["metadata"]
    for key in ("schema_version", "status", "task_id", "method_sha256", "output_schema_sha256", "source_manifest_sha256"):
        a.require(key in actual, "required metadata identity")
        match(actual[key], want[key], key)
    record_match(actual.get("source_files"), want["source_files"], "path")
    have, expected = actual.get("source_observed"), want["source_observed"]
    a.require(isinstance(have, dict) and set(expected) <= set(have), "source_observed fields")
    for key, value in expected.items():
        if key in ("bold_header", "atlas_header"): header_match(have[key], value)
        elif key == "map_labels": record_match(have[key], value, "map_id", numeric=True)
        else: match(have[key], value, "source_observed." + key)
    have, expected = actual.get("analysis_observed"), want["analysis_observed"]
    a.require(isinstance(have, dict) and set(expected) <= set(have), "analysis_observed fields")
    for key in ("map_rank", "confound_rank"): match(have[key], expected[key], key)
    record_match(have["target_support"], expected["target_support"], "map_id", numeric=True, atol=1e-10, rtol=1e-6)
    for row in have["target_support"]:
        for key in ("raw_sample_sd", "residual_centered_l2", "activity_threshold"):
            a.require(a.real(row[key], json_number=True) >= 0., "nonnegative support diagnostic")
    software = actual.get("software_versions")
    a.require(isinstance(software, dict) and set(("python", "numpy", "scipy", "nibabel", "nilearn")) <= set(software), "software fields")
    a.require(all(isinstance(k, str) and k and isinstance(v, str) and v.strip() for k, v in software.items()), "actual software strings")
    warnings = actual.get("warnings")
    a.require(isinstance(warnings, list) and all(isinstance(v, str) for v in warnings), "warning list")


def validate_output_directory(output_dir, reference):
    artifacts = a.read_artifacts(output_dir)
    raw, clean = c.canonical_primitives(artifacts["raw_map_coefficients.npz"], artifacts["timeseries.csv"], reference)
    expected = c.circular_evidence(clean, reference["active"])
    result = c.validate_report(artifacts["connectivity.json"], expected)
    validate_metadata(artifacts["run_metadata.json"], reference)
    return {**result, "n_raw_maps": raw.shape[1], "source_bound": True}
