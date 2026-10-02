"""External TASKFC source-basis validator; no source/oracle imports or fitting.

The root-owned reconstruction supplies a fully authenticated ten-person basis.
Only accepted residual primitives drive this module's one downstream replay.
"""
from __future__ import annotations

import math
import re

import numpy as np

import artifact_reader as a
import sensitivity_math as m

PARTICIPANTS = tuple(f"sub-{i:02}" for i in range(1, 11))
COHORT_FIELDS = ("subject", "bold_path", "events_path", "confounds_path", "n_frames",
                 "operational_TR_s", "operational_frame_origin_s", "left_n_voxels",
                 "right_n_voxels", "left_support_sha256", "right_support_sha256")
EVENT_FIELDS = ("subject", "source_event_index", "trial_type", "onset_token",
                "duration_token", "modulation_token", "onset_s", "duration_s", "modulation")
HEADER_FIELDS = ("shape", "selected_affine", "storage_dtype", "spatial_units", "temporal_units",
                 "zooms", "raw_toffset", "raw_scl_slope", "raw_scl_inter",
                 "effective_slope", "effective_intercept")
SOURCE_FIELDS = ("path", "role", "participant_id", "size_bytes", "sha256")
MODEL_DIAGNOSTICS = ("model_id", "column_ids", "rank", "residual_df", "singular_values", "rank_cutoff")
SUPPORT_FIELDS = ("roi_id", "raw_sample_sd", "residual_centered_l2", "activity_threshold", "active")


def subset(value, keys):
    a.require(isinstance(value, dict) and set(keys) <= set(value), "required object fields")
    return {key: value[key] for key in keys}


def text_axis(value, expected, name):
    values = m.labels(value).tolist()
    a.require(len(values) == len(expected) and len(set(values)) == len(values)
              and set(values) == set(expected), name+": exact unique literal axis")
    return np.asarray([values.index(key) for key in expected], dtype=np.int64)


def close(actual, expected, *, atol, rtol, name):
    actual, expected = m.array(actual), m.array(expected)
    a.require(actual.shape == expected.shape, name+": exact shape")
    a.require(np.all(np.abs(actual-expected) <= atol+rtol*np.abs(expected)), name+": numerical fidelity")
    return actual


def match(actual, expected, name, *, csv=False, atol=1e-6, rtol=0.):
    if isinstance(expected, dict):
        a.require(isinstance(actual, dict) and set(expected) <= set(actual), name+": fields")
        for key, value in expected.items():
            match(actual[key], value, name+"."+key, csv=csv, atol=atol, rtol=rtol)
    elif isinstance(expected, (list, tuple, np.ndarray)):
        a.require(isinstance(actual, list) and len(actual) == len(expected), name+": list shape")
        for i, value in enumerate(expected):
            match(actual[i], value, name+f"[{i}]", csv=csv, atol=atol, rtol=rtol)
    elif expected is None:
        a.require(actual == "" if csv else actual is None, name+": explicit undefined")
    elif isinstance(expected, (bool, np.bool_)):
        a.require((a.csv_boolean(actual) == bool(expected)) if csv else
                  (type(actual) is bool and actual == bool(expected)), name+": Boolean exact")
    elif isinstance(expected, (int, np.integer)):
        a.require(a.integer(actual, json_number=not csv) == int(expected), name+": integer exact")
    elif isinstance(expected, str):
        a.require(type(actual) is str and actual == expected, name+": literal exact")
    else:
        value = a.real(actual, json_number=not csv)
        a.require(abs(value-float(expected)) <= atol+rtol*abs(float(expected)), name+": numeric receipt")


def csv_rows(actual, expected, keys, *, numeric_keys=(), atol=1e-9, rtol=0.):
    have = a.keyed_rows(actual, keys, integer_columns=numeric_keys)
    want = a.keyed_rows(expected, keys, integer_columns=numeric_keys)
    a.require(set(have) == set(want), "complete exact CSV row keys")
    for key in want:
        match(have[key], want[key], str(key), csv=True, atol=atol, rtol=rtol)


def records(actual, expected, key, name, *, atol=1e-9, rtol=1e-9):
    a.require(isinstance(actual, list), name+": list")
    have, want = {}, {}
    for rows, result in ((actual, have), (expected, want)):
        for row in rows:
            a.require(isinstance(row, dict) and type(row.get(key)) is str
                      and row[key] and row[key] not in result, name+": unique literal keys")
            result[row[key]] = row
    a.require(set(have) == set(want), name+": complete keys")
    for identity in want:
        match(have[identity], want[identity], name+"."+identity, atol=atol, rtol=rtol)


def require_reference(reference):
    a.require(isinstance(reference, dict) and set(reference["participant_ids"]) == set(PARTICIPANTS)
              and len(reference["participant_ids"]) == 10, "production ten-person basis required")
    a.require(set(reference["participants"]) == set(PARTICIPANTS), "complete source participants")
    a.require(len(reference["source_files"]) == 48, "closed 48 source records required")
    a.require(len(reference["cohort"]) == 10, "complete canonical cohort")
    for pid in PARTICIPANTS:
        part = reference["participants"][pid]
        n = len(part["raw"])
        a.require(n >= 2 and np.array_equal(part["frame_index"], np.arange(n)), "canonical frame axis")
        a.require(m.array(part["raw"], 2).shape == (n, 2), "canonical raw shape")
        a.require(m.array(part["residuals"], 3).shape == (n, 2, 2), "canonical residual shape")
        m.mask(part["active"], (2, 2))
        a.require(set(part["designs"]) == set(part["design_columns"]) == set(m.MODELS), "two canonical models")


def union_columns(reference):
    columns = set()
    for part in reference["participants"].values():
        for names in part["design_columns"].values():
            a.require(len(names) == len(set(names)), "canonical unique design columns")
            columns.update(names)
    drift = [name for name in columns if re.fullmatch(r"drift_[1-9][0-9]*", name)]
    result = ["intercept", *sorted(drift, key=lambda name: int(name.split("_")[1])), *m.MOTION, *m.CONDITIONS]
    a.require(set(result) == columns, "canonical design vocabulary")
    return result


def canonical_primitives(submitted, reference):
    require_reference(reference)
    required = {"participant_ids", "roi_ids", "model_ids", "design_column_ids", "frame_participant_id",
                "source_frame_index", "frame_time_s", "roi_signals", "design_values", "design_included", "residuals"}
    a.require(isinstance(submitted, dict) and required <= set(submitted), "required NPZ primitives")
    columns = union_columns(reference)
    subject_order = text_axis(submitted["participant_ids"], PARTICIPANTS, "participants")
    roi_order = text_axis(submitted["roi_ids"], m.ROIS, "ROI")
    model_order = text_axis(submitted["model_ids"], m.MODELS, "model")
    column_order = text_axis(submitted["design_column_ids"], columns, "design column")
    frame_ids = m.labels(submitted["frame_participant_id"]).tolist()
    frame_index = a.integer_array(submitted["source_frame_index"])
    a.require(frame_index.ndim == 1 and len(frame_index) == len(frame_ids), "frame key axes")
    keys = list(zip(frame_ids, frame_index.tolist()))
    expected_keys = [(pid, i) for pid in PARTICIPANTS for i in range(len(reference["participants"][pid]["raw"]))]
    a.require(len(keys) == len(set(keys)) and set(keys) == set(expected_keys), "complete unique source frames")
    by_key = {key: i for i, key in enumerate(keys)}
    order = np.asarray([by_key[key] for key in expected_keys], dtype=np.int64)
    n = len(order)
    raw = m.array(submitted["roi_signals"], 2)
    residuals = m.array(submitted["residuals"], 3)
    design = m.array(submitted["design_values"], 2)
    times = m.array(submitted["frame_time_s"], 1)
    a.require(raw.shape == (n, 2) and residuals.shape == (n, 2, 2)
              and design.shape == (n, len(columns)) and times.shape == (n,), "exact primitive shapes")
    raw = raw[np.ix_(order, roi_order)]
    residuals = residuals[np.ix_(order, model_order, roi_order)]
    design = design[np.ix_(order, column_order)]
    times = times[order]
    included = m.mask(submitted["design_included"], (10, 2, len(columns)))
    included = included[np.ix_(subject_order, model_order, column_order)]
    own, offset = {}, 0
    for s, pid in enumerate(PARTICIPANTS):
        part = reference["participants"][pid]
        t = len(part["raw"])
        block = slice(offset, offset+t)
        close(raw[block], part["raw"], atol=1e-6, rtol=1e-6, name=pid+" raw")
        close(times[block], part["frame_times"], atol=1e-9, rtol=0., name=pid+" frame clock")
        expected_design = np.zeros((t, len(columns)))
        full = m.MODELS[1]
        names = part["design_columns"][full]
        expected_design[:, [columns.index(name) for name in names]] = part["designs"][full]
        close(design[block], expected_design, atol=1e-10, rtol=1e-8, name=pid+" design")
        for model_index, model in enumerate(m.MODELS):
            expected = np.asarray([name in part["design_columns"][model] for name in columns], dtype=bool)
            a.require(np.array_equal(included[s, model_index], expected), pid+": source model membership")
        own[pid] = m.residual_fidelity(residuals[block], part["residuals"], part["active"],
                                     atol=1e-6, rtol=1e-6, centered_rtol=1e-6)
        offset += t
    return own


def expected_metadata(reference):
    cohort = {row["subject"]: row for row in reference["cohort"]}
    source = dict(headers={}, event_column_names={}, confound_column_names={},
                  selected_motion_columns=list(m.MOTION), operational_clock={})
    analysis = []
    for pid in PARTICIPANTS:
        part = reference["participants"][pid]
        observed = part["source_observed"]
        source["headers"][pid] = subset(observed["header"], HEADER_FIELDS)
        source["event_column_names"][pid] = observed["event_column_names"]
        source["confound_column_names"][pid] = observed["confound_column_names"]
        source["operational_clock"][pid] = dict(TR_s=cohort[pid]["operational_TR_s"],
                                                frame_origin_s=cohort[pid]["operational_frame_origin_s"])
        models = []
        for record in part["analysis_observed"]["models"]:
            models.append(dict(**subset(record, MODEL_DIAGNOSTICS),
                               roi_support=[subset(row, SUPPORT_FIELDS) for row in record["roi_support"]]))
        analysis.append(dict(subject=pid, models=models))
    return dict(schema_version="taskfc-metadata-v2", task_id="TASKFC-001", status="ok",
                **reference["pins"], source_files=[subset(row, SOURCE_FIELDS) for row in reference["source_files"]],
                source_observed=source, analysis_observed=analysis)


def validate_metadata(actual, reference):
    want = expected_metadata(reference)
    a.finite_json(actual)
    for key in ("schema_version", "task_id", "status", *reference["pins"]):
        a.require(key in actual, "metadata identity fields")
        match(actual[key], want[key], key)
    records(actual.get("source_files"), want["source_files"], "path", "source_files")
    have, expected = actual.get("source_observed"), want["source_observed"]
    a.require(isinstance(have, dict) and set(expected) <= set(have), "source observed fields")
    for group in ("headers", "event_column_names", "confound_column_names", "operational_clock"):
        a.require(isinstance(have[group], dict) and set(have[group]) == set(PARTICIPANTS), "exact source participant map")
    for pid in PARTICIPANTS:
        header = have["headers"][pid]
        a.require(isinstance(header, dict) and set(HEADER_FIELDS) <= set(header), "header fields")
        for key in HEADER_FIELDS:
            if key == "storage_dtype":
                a.require(isinstance(header[key], str), "dtype text")
                try: equivalent = np.dtype(header[key]) == np.dtype(expected["headers"][pid][key])
                except (TypeError, ValueError) as exc: raise a.ArtifactError("invalid source dtype") from exc
                a.require(equivalent, "semantic source dtype")
            else:
                match(header[key], expected["headers"][pid][key], "header."+key, atol=1e-9, rtol=1e-9)
        for group in ("event_column_names", "confound_column_names"):
            match(have[group][pid], expected[group][pid], group, atol=1e-9, rtol=0.)
        match(have["operational_clock"][pid], expected["operational_clock"][pid], "clock", atol=1e-9, rtol=0.)
    match(have["selected_motion_columns"], expected["selected_motion_columns"], "selected motion")
    rows = actual.get("analysis_observed")
    a.require(isinstance(rows, list), "analysis records")
    keyed = a.keyed_rows(rows, ["subject"])
    a.require(set(keyed) == {(pid,) for pid in PARTICIPANTS}, "analysis subject membership")
    for expected_person in want["analysis_observed"]:
        person = keyed[(expected_person["subject"],)]
        models = person.get("models")
        a.require(isinstance(models, list), "model diagnostic records")
        have_models = a.keyed_rows(models, ["model_id"])
        a.require(set(have_models) == {(model,) for model in m.MODELS}, "both model diagnostics")
        for expected_model in expected_person["models"]:
            observed = have_models[(expected_model["model_id"],)]
            literal_columns = m.labels(observed.get("column_ids")).tolist()
            a.require(len(literal_columns) == len(set(literal_columns))
                      and set(literal_columns) == set(expected_model["column_ids"]), "source model columns")
            diagnostic_fields = tuple(key for key in MODEL_DIAGNOSTICS if key != "column_ids")
            match(subset(observed, diagnostic_fields), subset(expected_model, diagnostic_fields),
                  "model diagnostics", atol=1e-10, rtol=1e-6)
            records(observed.get("roi_support"), expected_model["roi_support"], "roi_id", "ROI support",
                    atol=1e-10, rtol=1e-6)
            for field in ("rank", "residual_df", "rank_cutoff"):
                a.require(a.real(observed[field], json_number=True) >= 0., "nonnegative model diagnostic")
            for value in observed["singular_values"]:
                a.require(a.real(value, json_number=True) >= 0., "nonnegative singular values")
            for roi in observed["roi_support"]:
                for field in ("raw_sample_sd", "residual_centered_l2", "activity_threshold"):
                    a.require(a.real(roi[field], json_number=True) >= 0., "nonnegative support diagnostic")
    software, warnings = actual.get("software_versions"), actual.get("warnings")
    a.require(isinstance(software, dict) and software and all(type(k) is str and k and
              type(v) is str and v.strip() for k, v in software.items()), "actual software record")
    a.require(isinstance(warnings, list) and all(type(v) is str for v in warnings), "warning strings")


def validate_derived(artifacts, derived):
    rows = artifacts["connectivity.csv"]
    expected_rows = list(derived["per_subject"].values())
    csv_rows(rows, expected_rows, ["subject"], atol=1e-6, rtol=0.)
    for row in rows:
        for key in ("connectivity", "background_connectivity"):
            if row[key] != "": a.require(-1. <= a.real(row[key]) <= 1., "signed correlation domain")
        for key in ("raw_fisher_z", "background_fisher_z"):
            if row[key] != "": a.require(abs(a.real(row[key])) <= math.atanh(.999)+1e-6, "Fisher receipt domain")
    expected = dict(schema_version="taskfc-results-v2", status="complete", **derived["summary"])
    actual = artifacts["connectivity_summary.json"]
    match(actual, expected, "summary", atol=1e-6, rtol=0.)
    for group in ("raw", "background"):
        if actual[group]["fisher_mean_r"] is not None:
            a.require(-1. <= a.real(actual[group]["fisher_mean_r"], json_number=True) <= 1., "group correlation domain")
    paired = actual["paired_z_sensitivity"]
    for key in ("sample_sd", "standard_error"):
        if paired[key] is not None: a.require(a.real(paired[key], json_number=True) >= 0., "nonnegative paired dispersion")
    if paired["p"] is not None: a.require(0. <= a.real(paired["p"], json_number=True) <= 1., "p domain")
    if paired["ci95"] is not None:
        a.require(a.real(paired["ci95"][0], json_number=True) <= a.real(paired["ci95"][1], json_number=True), "ordered CI")


def validate_output_directory(output_dir, reference):
    require_reference(reference)
    artifacts = a.read_artifacts(output_dir)
    csv_rows(artifacts["cohort.csv"], [subset(row, COHORT_FIELDS) for row in reference["cohort"]], ["subject"])
    csv_rows(artifacts["events.csv"], [subset(row, EVENT_FIELDS) for row in reference["events"]],
             ["subject", "source_event_index"], numeric_keys=["source_event_index"])
    own = canonical_primitives(artifacts["model_arrays.npz"], reference)
    active = {pid: reference["participants"][pid]["active"] for pid in PARTICIPANTS}
    derived = m.derive_cohort(own, active, list(PARTICIPANTS))
    validate_derived(artifacts, derived)
    validate_metadata(artifacts["run_metadata.json"], reference)
    return dict(status="accepted", n_subjects=10,
                n_frames=sum(len(part["raw"]) for part in reference["participants"].values()),
                source_bound=True)
