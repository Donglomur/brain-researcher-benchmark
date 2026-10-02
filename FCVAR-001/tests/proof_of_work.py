"""FCVAR bounded, source-bound proof; shared public statistic kernel only.

No oracle, stage helper, historical bank, fetch, or import-time source access.
The source reference is reconstructed independently once by the caller. No
submission, acceptance, or endpoint is cached. Genuine mutation QA is separate.
"""
from __future__ import annotations

import os
import hashlib
from decimal import Decimal
from pathlib import Path
import types

import numpy as np

import artifact_reader as a

WINDOWS = (20, 30, 44)
N_DRAWS = 50
RAW_TOL = (1e-5, 1e-6)
CLEAN_TOL = (1e-7, 1e-7)
DERIVED_TOL = (1e-6, 1e-6)
# Prospective metadata-only candidates; parent must freeze before original use.
HEADER_TOL = (1e-9, 1e-9)
DIAGNOSTIC_TOL = (1e-10, 1e-6)
KERNEL_SHA256 = "a446d8b5b8cc8ea4bafe97fecc0a9dcf21f2b9df43cbf379feb63a3c1e5bdba5"


def load_kernel():
    """Do not resolve editable public/cwd modules, cached pyc or sys.modules."""
    path = Path(__file__).with_name("signal_kernel.py")
    a.require(isinstance(KERNEL_SHA256, str) and len(KERNEL_SHA256) == 64, "private kernel pin not frozen")
    body = a.read_bytes(path, 2**20)
    a.require(hashlib.sha256(body).hexdigest() == KERNEL_SHA256, "private shared kernel checksum")
    module = types.ModuleType("_fcvar_private_signal_kernel")
    module.__file__ = str(path)
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


def strings(value, ndim=1):
    a.checked_array(value)
    a.require(value.ndim == ndim and value.dtype.kind in "US", "literal text array required")
    out = np.char.decode(value, "utf-8") if value.dtype.kind == "S" else value
    a.require(np.all(out != ""), "empty text axis")
    return out.astype(str)


def real_array(value, shape):
    a.checked_array(value)
    a.require(value.dtype.kind in "iuf" and value.shape == tuple(shape), "real array shape/type")
    return np.asarray(value, dtype=np.float64)


def ordered_axis(value, expected, kind="text"):
    observed = strings(value).tolist() if kind == "text" else a.integer_array(value).tolist()
    a.require(value.ndim == 1 and len(observed) == len(set(observed)), "duplicate/nonvector axis")
    a.require(set(observed) == set(expected), "axis membership mismatch")
    return np.asarray([observed.index(key) for key in expected], dtype=np.int64)


def close(actual, expected, tolerance, context):
    actual, expected = np.asarray(actual, dtype=float), np.asarray(expected, dtype=float)
    a.require(actual.shape == expected.shape and np.isfinite(actual).all() and np.isfinite(expected).all(), context + ": shape/finite")
    atol, rtol = tolerance
    a.require(np.all(np.abs(actual - expected) <= atol + rtol * np.abs(expected)), context + ": numeric mismatch")


def scalar(value, expected, *, csv=False, tolerance=DERIVED_TOL, context="scalar"):
    if expected is None:
        a.require(value == "" if csv else value is None, context + ": required undefined null")
    elif isinstance(expected, (bool, np.bool_)):
        parsed = a.csv_boolean(value) if csv else value
        a.require(type(parsed) is bool and parsed == bool(expected), context + ": Boolean mismatch")
    elif isinstance(expected, (int, np.integer)):
        a.require(a.integer(value, json_number=not csv) == int(expected), context + ": integer mismatch")
    elif isinstance(expected, (float, np.floating, Decimal)):
        parsed = a.real(value, json_number=not csv)
        close(parsed, float(expected), tolerance, context)
    else:
        a.require(isinstance(value, str) and value == expected, context + ": literal mismatch")


def record(actual, expected, *, csv=False, tolerance=DERIVED_TOL, context="record"):
    a.require(isinstance(actual, dict), context + ": object required")
    for key, value in expected.items():
        a.require(key in actual, context + ": missing " + key)
        scalar(actual[key], value, csv=csv, tolerance=tolerance, context=context + "." + key)
        if value is not None and key in ("mean_edge_sd", "mean_edge_sd_null", "observed_over_null_ratio", "p_value"):
            observed = a.real(actual[key], json_number=not csv)
            a.require(observed >= 0., context + ": nonnegative scientific domain")
            if key == "p_value": a.require(observed <= 1., context + ": probability domain")


def recursive(actual, expected, tolerance, context):
    """Expected public metadata subset; exact keyed memberships handled separately."""
    if isinstance(expected, dict):
        a.require(isinstance(actual, dict) and set(expected).issubset(actual), context + ": missing object fields")
        for key, value in expected.items():
            if key == "storage_dtype":
                a.require(isinstance(actual[key], str), context + ": dtype must be text")
                try:
                    got, want = np.dtype(actual[key]), np.dtype(value)
                except (ValueError, TypeError) as exc:
                    raise a.ArtifactError(context + ": invalid dtype") from exc
                a.require(got.fields is None and got.kind in "iuf" and got == want, context + ": dtype mismatch")
            else:
                recursive(actual[key], value, tolerance, context + "." + key)
    elif isinstance(expected, list):
        a.require(isinstance(actual, list) and len(actual) == len(expected), context + ": list length")
        for i, value in enumerate(expected):
            recursive(actual[i], value, tolerance, context + f"[{i}]")
    else:
        scalar(actual, expected, tolerance=tolerance, context=context)


def table(actual, expected, keys, integers=(), *, tolerance=DERIVED_TOL, context="table"):
    got = a.keyed_rows(actual, keys, integer_columns=integers)
    want = a.keyed_rows(expected, keys, integer_columns=integers)
    a.require(set(got) == set(want), context + ": exact row keys")
    for key, row in want.items():
        record(got[key], row, csv=True, tolerance=tolerance, context=context + str(key))


def json_rows(actual, expected, keys, integers=(), *, tolerance=HEADER_TOL, context="metadata rows"):
    a.require(isinstance(actual, list), context + ": list required")
    def rows(values):
        result = {}
        for row in values:
            a.require(isinstance(row, dict) and all(k in row for k in keys), context + ": missing row key")
            key = tuple(a.integer(row[k], json_number=True) if k in integers else row[k] for k in keys)
            a.require(all(isinstance(v, (str, int)) and not isinstance(v, bool) for v in key), context + ": typed key")
            a.require(key not in result, context + ": duplicate row key")
            result[key] = row
        return result
    got, want = rows(actual), rows(expected)
    a.require(set(got) == set(want), context + ": exact row keys")
    for key in want:
        recursive(got[key], want[key], tolerance, context + str(key))


def canonical_primitives(arrays, reference):
    """Align keyed receipts; never re-clean or reclassify accepted receipts."""
    ids, rois = reference["participant_ids"], reference["roi_ids"]
    si = ordered_axis(arrays["participant_ids"], ids)
    ri = ordered_axis(arrays["roi_ids"], rois, "integer")
    a.require(strings(arrays["roi_labels"]).shape == (len(rois),), "ROI labels shape")
    a.require(strings(arrays["roi_labels"])[ri].tolist() == list(reference["roi_labels"]), "source ROI labels")
    shape = (len(ids), len(rois))
    for name in ("geometry_present", "roi_active"):
        value = arrays[name]
        a.require(value.dtype.kind == "b" and value.shape == shape, name + ": Boolean shape")
        key = "active" if name == "roi_active" else name
        expected = np.asarray([reference["persons"][sid][key] for sid in ids], dtype=bool)
        a.require(np.array_equal(value[np.ix_(si, ri)], expected), name + ": canonical support mismatch")
    counts = a.integer_array(arrays["n_voxels"])
    a.require(counts.shape == shape and np.all(counts >= 0), "support counts shape/domain")
    expected_counts = np.asarray([reference["persons"][sid]["n_voxels"] for sid in ids])
    a.require(np.array_equal(counts[np.ix_(si, ri)], expected_counts), "source voxel support counts")
    digests = strings(arrays["support_sha256"], 2)
    a.require(digests.shape == shape, "support digests shape")
    a.require(np.array_equal(digests[np.ix_(si, ri)], np.asarray([reference["persons"][sid]["support_sha256"] for sid in ids])), "source support digests")
    for name in ("raw_sample_sd", "prestandardization_centered_l2", "activity_threshold", "full_clean_centered_l2"):
        value = real_array(arrays[name], shape)
        a.require(np.all(value >= 0), name + ": nonnegative domain")
        expected = np.asarray([reference["persons"][sid][name] for sid in ids])
        close(value[np.ix_(si, ri)], expected, DIAGNOSTIC_TOL, name)
    frame_ids = strings(arrays["frame_subject"])
    frame_index = a.integer_array(arrays["frame_index"])
    f = sum(reference["persons"][sid]["n_frames"] for sid in ids)
    a.require(frame_ids.shape == frame_index.shape == (f,), "frame axis shape")
    keys = list(zip(frame_ids.tolist(), frame_index.tolist()))
    a.require(len(set(keys)) == f, "duplicate original frame key")
    expected_keys = [(sid, i) for sid in ids for i in range(reference["persons"][sid]["n_frames"])]
    a.require(set(keys) == set(expected_keys), "source original frame coverage")
    positions = {key: i for i, key in enumerate(keys)}
    raw = real_array(arrays["raw_roi_mean"], (f, len(rois)))
    clean = real_array(arrays["clean_roi_series"], (f, len(rois)))
    accepted = {}
    for sid in ids:
        person = reference["persons"][sid]
        fi = [positions[sid, i] for i in range(person["n_frames"])]
        own_raw = raw[np.ix_(fi, ri)]
        own_clean = np.ascontiguousarray(clean[np.ix_(fi, ri)], dtype=np.float64)
        close(own_raw, person["raw"], RAW_TOL, sid + ": raw mean receipt")
        close(own_clean, person["clean"], CLEAN_TOL, sid + ": cleaned primitive")
        # Canonical inactive entries are zero; toleranced submitted receipts
        # need not serialize exact zero. Their fixed masks never reactivate.
        accepted[sid] = own_clean
    return accepted


def phase_receipts(arrays, analyses, reference):
    di = ordered_axis(arrays["surrogate_ids"], list(range(N_DRAWS)), "integer")
    subject = strings(arrays["phase_subject"])
    window = a.integer_array(arrays["phase_window"])
    frequency = a.integer_array(arrays["frequency_index"])
    q = sum(len(WINDOWS) * (reference["persons"][sid]["n_frames"] // 2 + 1) for sid in reference["participant_ids"])
    a.require(subject.shape == window.shape == frequency.shape == (q,), "phase key shapes")
    keys = list(zip(subject.tolist(), window.tolist(), frequency.tolist()))
    a.require(len(set(keys)) == q, "duplicate phase key")
    positions = {key: i for i, key in enumerate(keys)}
    want = {(sid, w, f) for sid in reference["participant_ids"] for w in WINDOWS for f in range(reference["persons"][sid]["n_frames"] // 2 + 1)}
    a.require(set(keys) == want, "complete canonical phase keys")
    values = real_array(arrays["phase_angles"], (q, N_DRAWS))
    a.require(np.all(values >= 0.) and np.all(values <= 2*np.pi + 1e-6), "phase receipt domain")
    for analysis in analyses:
        sid, n = analysis["subject"], analysis["n_timepoints"]
        for w in WINDOWS:
            rows = [positions[sid, w, f] for f in range(n // 2 + 1)]
            submitted = values[np.ix_(rows, di)].T
            close(submitted, analysis["phases"][w], (1e-6, 0.), "canonical phase receipt")
            a.require(np.all(submitted[:, 0] == 0.), "phase DC must remain zero")
            if n % 2 == 0:
                a.require(np.all(submitted[:, -1] == 0.), "phase even-Nyquist must remain zero")


def validate_metadata(actual, reference, seed):
    expected = reference["metadata"]
    record(actual, {key: expected[key] for key in ("schema_version", "task_id", "status", "source_manifest_sha256", "method_contract_sha256", "output_schema_sha256")}, context="metadata identity")
    a.require(a.integer(actual.get("seed"), json_number=True) == seed and 0 <= seed < 2**32, "metadata seed/replay mismatch")
    json_rows(actual.get("source_files"), expected["source_files"], ("path",), context="closed source identities")
    source = actual.get("source_observed")
    want = expected["source_observed"]
    a.require(isinstance(source, dict), "source_observed required")
    # Dictionary memberships expressing the fixed cohort are exact, whereas
    # each source record can have harmless descriptive extra fields.
    for name in ("persons",):
        a.require(isinstance(source.get(name), dict) and set(source[name]) == set(want[name]), name + ": exact participant keys")
        recursive(source[name], want[name], HEADER_TOL, "source_observed." + name)
    recursive(source.get("atlas_header"), want["atlas_header"], HEADER_TOL, "atlas_header")
    json_rows(source.get("roi_labels"), want["roi_labels"], ("roi_id",), ("roi_id",), context="atlas labels")
    for name in ("phenotype_columns", "slice_timing_columns"):
        recursive(source.get(name), want[name], HEADER_TOL, name)
    analysis = actual.get("analysis_observed")
    a.require(isinstance(analysis, dict) and isinstance(analysis.get("persons"), dict), "analysis persons required")
    a.require(set(analysis["persons"]) == set(expected["analysis_observed"]["persons"]), "analysis exact participant keys")
    recursive(analysis, expected["analysis_observed"], DIAGNOSTIC_TOL, "analysis diagnostics")
    versions = actual.get("software_versions")
    a.require(isinstance(versions, dict) and all(isinstance(versions.get(k), str) and versions[k].strip() for k in ("python", "numpy", "scipy", "nibabel", "nilearn")), "descriptive software versions")
    a.require(isinstance(actual.get("warnings"), list) and all(isinstance(v, str) for v in actual["warnings"]), "warnings list")


def validate_dynamics(actual, expected):
    a.require(isinstance(actual, dict), "dynamics object")
    scalar_fields = {k: v for k, v in expected.items() if k not in ("windows", "window_lengths_tr")}
    record(actual, scalar_fields, context="dynamics")
    ws = actual.get("window_lengths_tr")
    a.require(isinstance(ws, list) and len(ws) == 3, "three window lengths")
    parsed = [a.integer(v, json_number=True) for v in ws]
    a.require(len(set(parsed)) == 3 and set(parsed) == set(WINDOWS), "window length membership")
    json_rows(actual.get("windows"), expected["windows"], ("window_tr",), ("window_tr",), tolerance=DERIVED_TOL, context="own-series group metrics")
    for window in actual["windows"]:
        for metric in ("mean_observed_edge_sd", "mean_null_edge_sd", "mean_subject_observed_over_null_ratio", "median_subject_p", "fraction_subjects_significant"):
            value = window[metric]["value"]
            if value is not None:
                number = a.real(value, json_number=True)
                a.require(number >= 0., "group metric nonnegative domain")
                if metric in ("median_subject_p", "fraction_subjects_significant"):
                    a.require(number <= 1., "group probability domain")


def validate_output_directory(output_dir, reference):
    kernel = load_kernel()
    files = a.read_artifacts(output_dir)
    a.require(reference.get("status") == "complete" and len(reference["participant_ids"]) == 30, "full30 reference required")
    dynamics = files["dynamics.json"]
    seed = a.integer(dynamics.get("seed"), json_number=True)
    a.require(0 <= seed < 2**32, "exact nonboolean uint32 base seed")
    accepted = canonical_primitives(files["roi_evidence.npz"], reference)
    analyses = [kernel.analyze_subject(accepted[sid], reference["persons"][sid]["clean"], reference["persons"][sid]["active"], sid, seed=seed) for sid in reference["participant_ids"]]
    phase_receipts(files["roi_evidence.npz"], analyses, reference)
    table(files["cohort.csv"], reference["cohort"], ("subject",), tolerance=HEADER_TOL, context="source cohort")
    table(files["variability.csv"], [row for result in analyses for row in result["windows"]], ("subject", "window_tr"), ("window_tr",), context="own variability")
    table(files["surrogate_statistics.csv"], [row for result in analyses for row in result["surrogates"]], ("subject", "window_tr", "surrogate_id"), ("window_tr", "surrogate_id"), context="own null statistics")
    validate_dynamics(dynamics, kernel.summarize_subjects(analyses, reference["participant_ids"]))
    validate_metadata(files["run_metadata.json"], reference, seed)
    a.require(not os.path.lexists(a.guarded_path(output_dir, directory=True) / a.FAILURE), "authoritative late failure_report.json present")
    return {"status": "accepted", "n_subjects": 30, "n_rois": len(reference["roi_ids"]), "n_subject_window_rows": len(analyses)*3, "n_surrogate_rows": len(analyses)*150, "seed": seed}
