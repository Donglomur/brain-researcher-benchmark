"""Source-bound N170 evidence validation; no source, oracle or bank imports.

The caller authenticates original bytes and private code pins before constructing
reference. This module never reconstructs at import time, caches acceptance, or
uses public editable numerical helpers. Its sibling imports belong to the private
isolated verifier path. Accepted condition waves have one downstream authority.
"""
import os
from pathlib import Path

import numpy as np

import io_contract as io
import measurement_kernel as mk
import wave_contract as wc

SOURCE_SHA = "3970137c64990f680468baf1d51b89a73a61a748639795541e2c2734777b54cd"
METHOD_SHA = "549cf315f0175ab13c3007703cec298a6cc5080d695aecd9f93f49e98a08ce92"
SCHEMA_SHA = "fab0dbf2ff1fb60f0596b065ff5f148d9d46da8c89c6e81203dbc346a2070814"
KERNEL_SHA = "bc12162f1496b3f4b83419748ee33905a050331cc815ea7d7a9788e6a6fbba9e"
SUBJECTS = tuple(str(i) for i in range(1, 41) if i not in (1, 5, 16))
CONDITIONS = ("face", "car")
CHANNELS = ("FP1","F3","F7","FC3","C3","C5","P3","P7","P9","PO7","PO3","O1","Oz","Pz","CPz",
            "FP2","Fz","F4","F8","FC4","FCz","Cz","C4","C6","P4","P8","P10","PO8","PO4","O2")
OFFSETS = tuple(range(-51, 103))
ANNOTATION_COLUMNS = ("subject_id","source_event_index","type_json","latency_json","duration_json",
                      "urevent_json","normalized_event_code","event_role")
TRIAL_COLUMNS = ("subject_id","source_event_index","condition","event_sample","epoch_first_sample",
                 "epoch_last_sample","epoch_status","accepted","rejection_reason")
PERSON_COLUMNS = ("subject_id","n_face_candidates","n_car_candidates","n_face_accepted","n_car_accepted",
                  "n_face_rejected","n_car_rejected","waveform_status","amp_po8_uv","amplitude_status",
                  "onset_ms","onset_status","measurement_baseline_uv","peak_selection","peak_sample_offset",
                  "peak_time_ms","peak_uv","half_height_uv","crossing_sample_offset")
ARRAYS = ("subject_ids","condition_labels","sample_offsets","condition_defined","evoked_po8_uv",
          "rejection_channel_labels","epoch_subject_ids","epoch_source_event_index",
          "epoch_peak_to_peak_uv","epoch_po8_baseline_uv")


def pins():
    return dict(source_manifest_sha256=SOURCE_SHA, method_contract_sha256=METHOD_SHA,
                output_schema_sha256=SCHEMA_SHA)


def need(ok, message):
    io.need(ok, message)


def exact_integer(value, *, json_mode=False):
    if json_mode:
        need(type(value) in (int, float), "JSON integer type")
    return io.integer(value)


def keyed(rows, fields):
    need(type(rows) is list, "keyed records list")
    return io.key_rows(rows, fields)


def match(given, expected, *, atol=0., rtol=0., path="metadata"):
    """Typed required-field comparison; only declared keyed lists are unordered."""
    if expected is None:
        need(given is None, path+": null")
    elif isinstance(expected, (bool, np.bool_)):
        need(type(given) is bool and given == bool(expected), path+": Boolean")
    elif isinstance(expected, (int, np.integer)):
        need(exact_integer(given, json_mode=True) == int(expected), path+": integer")
    elif isinstance(expected, (float, np.floating)):
        actual = io.number(given, json_mode=True)
        need(abs(actual-float(expected)) <= atol+rtol*abs(float(expected)), path+": numerical mismatch")
    elif type(expected) is str:
        need(type(given) is str and given == expected, path+": string")
    elif type(expected) is dict:
        need(type(given) is dict and set(expected) <= set(given), path+": required fields")
        for key,value in expected.items():
            match(given[key], value, atol=atol, rtol=rtol, path=path+"."+key)
    elif isinstance(expected, (list, tuple)):
        need(type(given) is list, path+": list")
        name = path.rsplit(".", 1)[-1]
        if name in ("cohort", "missing_subject_ids"):
            need(all(type(x) is str for x in given) and len(given) == len(set(given))
                 and set(given) == set(expected), path+": subject membership")
        elif name in ("source_files", "persons"):
            fields = ("subject_id","role") if name == "source_files" else ("subject_id",)
            a,b = keyed(given, fields),keyed(list(expected), fields)
            need(set(a) == set(b), path+": keyed membership")
            for key in b:
                match(a[key],b[key],atol=atol,rtol=rtol,path=path+"[]")
        else:
            need(len(given) == len(expected), path+": list length")
            for index,(a,b) in enumerate(zip(given,expected)):
                match(a,b,atol=atol,rtol=rtol,path=path+f"[{index}]")
    else:
        raise ValueError("unsupported trusted metadata type: "+path)


def unicode_values(value, name):
    need(value.ndim == 1 and value.dtype.kind == "U", name+": Unicode axis")
    return value.tolist()


def axis(value, expected, name):
    values = unicode_values(value,name)
    need(len(values) == len(set(values)) and set(values) == set(expected), name+": membership")
    index = {v:i for i,v in enumerate(values)}
    return [index[v] for v in expected]


def integer_values(value, name):
    need(value.ndim == 1 and value.dtype.kind in "iuf" and np.isfinite(value).all(), name+": integral axis")
    return [exact_integer(x) for x in value]


def real_array(value, shape, name):
    need(value.dtype.kind in "iuf" and value.shape == shape and np.isfinite(value).all(), name+": finite real shape")
    return np.ascontiguousarray(value, dtype=np.float64)


def canonical_primitives(arrays, reference):
    need(set(ARRAYS) <= set(arrays), "required NPZ arrays")
    so = axis(arrays["subject_ids"], SUBJECTS, "subject_ids")
    co = axis(arrays["condition_labels"], CONDITIONS, "condition_labels")
    ho = axis(arrays["rejection_channel_labels"], CHANNELS, "rejection_channel_labels")
    offsets = integer_values(arrays["sample_offsets"],"sample_offsets")
    need(len(offsets) == len(set(offsets)) and set(offsets) == set(OFFSETS), "sample offset membership")
    ko = [offsets.index(v) for v in OFFSETS]
    defined = arrays["condition_defined"]
    need(defined.dtype.kind == "b" and defined.shape == (37,2), "condition flags Boolean shape")
    defined = defined[np.ix_(so,co)]
    need(np.array_equal(defined,reference["condition_defined"]), "source condition support")
    evoked = real_array(arrays["evoked_po8_uv"], (37,2,154), "condition waveforms")[np.ix_(so,co,ko)]
    need(np.all(evoked[~defined] == 0), "missing condition zero sentinel")
    subjects = unicode_values(arrays["epoch_subject_ids"],"epoch_subject_ids")
    events = integer_values(arrays["epoch_source_event_index"],"epoch_source_event_index")
    need(len(subjects) == len(events) <= 10000 and all(v in SUBJECTS for v in subjects)
         and all(v >= 0 for v in events), "epoch key domains")
    keys = list(zip(subjects,events)); expected = list(map(tuple,reference["epoch_keys"]))
    need(len(keys) == len(set(keys)) and set(keys) == set(expected), "source eligible epoch membership")
    order = {key:i for i,key in enumerate(keys)}
    eo = [order[key] for key in expected]
    ptp = real_array(arrays["epoch_peak_to_peak_uv"], (len(keys),30), "trial PTP")
    need(np.all(ptp >= 0), "nonnegative trial PTP")
    baseline = real_array(arrays["epoch_po8_baseline_uv"], (len(keys),), "trial PO8 baseline")
    io.close(ptp[np.ix_(eo,ho)], reference["epoch_peak_to_peak_uv"], atol=1e-6, rtol=1e-6)
    io.close(baseline[eo], reference["epoch_po8_baseline_uv"], atol=1e-6, rtol=1e-6)
    return np.ascontiguousarray(evoked), defined


def normalize_row(row, kind, *, submitted):
    columns = ANNOTATION_COLUMNS if kind == "annotations" else TRIAL_COLUMNS
    need(set(columns) <= set(row), kind+": fields")
    sid = row["subject_id"]
    need(type(sid) is str and sid in SUBJECTS, kind+": literal subject")
    result = dict(subject_id=sid,source_event_index=exact_integer(row["source_event_index"]))
    need(result["source_event_index"] >= 0, "nonnegative event index")
    if kind == "annotations":
        for key in columns[2:6]:
            value = row[key]
            need(type(value) is str, "documentary JSON cell")
            result[key] = io.json_bytes(value.encode("utf-8"))
        token = row["normalized_event_code"]
        result["normalized_event_code"] = None if token == "" or token is None else exact_integer(token)
        result["event_role"] = row["event_role"]
    else:
        for key in ("event_sample","epoch_first_sample","epoch_last_sample"):
            result[key] = exact_integer(row[key])
        for key in ("condition","epoch_status","rejection_reason"):
            result[key] = row[key]
        result["accepted"] = io.boolean(row["accepted"]) if submitted else row["accepted"]
        need(type(result["accepted"]) is bool, "accepted Boolean")
    return result


def validate_ledger(rows, expected, kind):
    a = keyed([normalize_row(r,kind,submitted=True) for r in rows], ("subject_id","source_event_index"))
    b = keyed([normalize_row(r,kind,submitted=False) for r in expected], ("subject_id","source_event_index"))
    need(set(a) == set(b), kind+": complete source membership")
    for key in b:
        match(a[key],b[key],path=kind)


def participant_replay(waveforms, defined, reference):
    records = []; times = np.asarray(OFFSETS,dtype=np.float64)*(1000./256.)
    for index,sid in enumerate(SUBJECTS):
        source = {name:reference["evoked_po8_uv"][index,j] if defined[index,j] else None
                  for j,name in enumerate(CONDITIONS)}
        accepted = {name:waveforms[index,j] if defined[index,j] else None for j,name in enumerate(CONDITIONS)}
        measured = wc.replay_conditions(times,accepted,source)["measurement"]
        selected = [r for r in reference["trials"] if r["subject_id"] == sid]
        row = dict(subject_id=sid,waveform_status="ok" if bool(defined[index].all()) else "missing_condition")
        for name in CONDITIONS:
            rows = [r for r in selected if r["condition"] == name]
            n = sum(r["accepted"] for r in rows)
            row.update({f"n_{name}_candidates":len(rows),f"n_{name}_accepted":n,f"n_{name}_rejected":len(rows)-n})
        for output,key in (("amp_po8_uv","amplitude_uv"),("amplitude_status","amplitude_status"),
                           ("onset_ms","onset_ms"),("onset_status","onset_status"),
                           ("measurement_baseline_uv","measurement_baseline_uv"),
                           ("peak_selection","peak_selection"),("peak_time_ms","peak_time_ms"),
                           ("peak_uv","peak_uv"),("half_height_uv","half_height_uv")):
            row[output] = measured[key]
        row["peak_sample_offset"] = None if measured["peak_index"] is None else OFFSETS[measured["peak_index"]]
        row["crossing_sample_offset"] = None if measured["crossing_index"] is None else OFFSETS[measured["crossing_index"]]
        records.append(row)
    return records


def validate_participants(rows, expected):
    actual = keyed(rows,("subject_id",)); wanted = keyed(expected,("subject_id",))
    need(set(actual) == set(wanted), "complete participant membership")
    integer_keys = {k for k in PERSON_COLUMNS if k.startswith("n_")} | {"peak_sample_offset","crossing_sample_offset"}
    string_keys = {"subject_id","waveform_status","amplitude_status","onset_status","peak_selection"}
    for key,ref in wanted.items():
        row = actual[key]
        for field in PERSON_COLUMNS:
            need(field in row, "participant required field")
            value,canonical = row[field],ref[field]
            if canonical is None:
                need(value == "", field+": CSV null")
            elif field in integer_keys:
                need(exact_integer(value) == canonical, field+": exact count/offset")
            elif field in string_keys:
                need(type(value) is str and value == canonical, field+": status/identity")
            else:
                got = io.number(value)
                rtol = 0 if field in ("onset_ms","peak_time_ms") else 1e-6
                need(abs(got-canonical) <= 1e-6+rtol*abs(canonical), field+": measurement replay")


def group_replay(records):
    groups = []
    for field in ("amp_po8_uv","onset_ms"):
        result = mk.aggregate_complete([r[field] for r in records],expected_n=37)
        result["missing_subject_ids"] = [SUBJECTS[i] for i in result.pop("missing_indices")]
        groups.append(result)
    amp,onset = groups
    return dict(schema_version="n170-output-v1",n_subjects=37,electrode="PO8",
                amp_po8_uv=amp["mean"],amp_po8_ci95=amp["ci95"],
                onset_latency_ms=onset["mean"],onset_ci95=onset["ci95"],
                amplitude_summary=amp,onset_summary=onset)


def validate_groups(given, expected):
    need(type(given) is dict and set(expected) <= set(given), "group required fields")
    for key,value in expected.items():
        time_metric = key.startswith("onset")
        match(given[key],value,atol=1e-6,rtol=0 if time_metric else 1e-6,path=key)
    for key in ("amplitude_summary","onset_summary"):
        summary = given[key]
        for field in ("sample_sd","standard_error"):
            if summary[field] is not None:
                need(io.number(summary[field],True) >= 0, "nonnegative group dispersion")
        ci = summary["ci95"]
        if ci is not None:
            need(io.number(ci[0],True) <= io.number(ci[1],True), "ordered group CI")
    for key in ("amp_po8_ci95","onset_ci95"):
        ci = given[key]
        if ci is not None:
            need(io.number(ci[0],True) <= io.number(ci[1],True), "ordered headline CI")


def source_path(value):
    """Canonical manifest spelling, without opening or resolving submitted paths."""
    need(type(value) is str and bool(value) and "\0" not in value and "\\" not in value,
         "source path string")
    prefix = "/app/data/n170profile/"
    if value.startswith("/"):
        need(value.startswith(prefix), "source path root")
        value = value[len(prefix):]
    need(all(part not in ("", ".", "..") for part in value.split("/")),
         "source path components")
    return value


def condition_flags(value):
    """Metadata-only Boolean encoding; the NPZ evidence mask is unchanged."""
    if type(value) is dict:
        need(set(value) == set(CONDITIONS), "condition flags exact names")
        value = [value[name] for name in CONDITIONS]
    need(type(value) is list and len(value) == 2 and all(type(v) is bool for v in value),
         "condition flags Boolean pair")
    return list(value)


def documentary_empty_fields(given, expected, fields):
    """Only named optional MAT fields already proven empty by the source reader."""
    if type(given) is not dict or type(expected) is not dict:
        return given
    result = dict(given)
    for field in fields:
        if (field in given and field in expected and expected[field] is None
                and type(given[field]) is list and len(given[field]) == 0):
            result[field] = None
    return result


def metadata_view(given, reference):
    """Normalize documentary aliases in fresh mappings, never submitted bytes."""
    need(type(given) is dict, "metadata record")
    view = dict(given)
    need(type(given.get("source_files")) is list, "source files list")
    records = []
    for row in given["source_files"]:
        need(type(row) is dict and "path" in row, "source file path required")
        record = dict(row, path=source_path(row["path"]))
        if "manifest_path" in row:
            need(source_path(row["manifest_path"]) == record["path"], "conflicting manifest path")
        records.append(record)
    view["source_files"] = records
    original_people = keyed(reference["source_observed"]["persons"], ("subject_id",))
    for section in ("source_observed", "analysis_observed"):
        value = given.get(section)
        need(type(value) is dict and type(value.get("persons")) is list, section+": persons required")
        people = []
        for row in value["persons"]:
            need(type(row) is dict, section+": person record")
            person = dict(row)
            if section == "source_observed":
                for field in ("set_path", "fdt_path"):
                    need(field in row, "required source "+field)
                    person[field] = source_path(row[field])
                if row.get("mat_layout") == "EEG":
                    person["mat_layout"] = "scalar_EEG_struct"
                need(type(row.get("subject_id")) is str, "literal metadata subject")
                expected = original_people.get((row["subject_id"],), {})
                if "header_fields" in row:
                    person["header_fields"] = documentary_empty_fields(
                        row["header_fields"], expected.get("header_fields"),
                        ("subject", "group", "condition", "session"))
                if type(row.get("channel_records")) is list:
                    channels = expected.get("channel_records", [])
                    person["channel_records"] = [documentary_empty_fields(
                        record, channels[i] if i < len(channels) else None,
                        ("ref", "theta", "radius", "X", "Y", "Z", "sph_theta",
                         "sph_phi", "sph_radius", "type", "urchan"))
                        for i, record in enumerate(row["channel_records"])]
            else:
                need("condition_defined" in row, "required condition flags")
                person["condition_defined"] = condition_flags(row["condition_defined"])
            people.append(person)
        view[section] = dict(value, persons=people)
    return view


def validate_metadata(given, reference):
    expected = dict(schema_version="n170-output-v1",task_id="N170PROFILE-001",status="complete",
                    **pins(),measurement_kernel_sha256=KERNEL_SHA,cohort=list(SUBJECTS),
                    source_files=reference["source_files"])
    given = metadata_view(given, reference)
    match(given,expected)
    for name in ("source_observed","analysis_observed"):
        need(name in given, "required metadata "+name)
        match(given[name],reference[name],atol=1e-9,rtol=1e-9,path=name)
    software = given.get("software_versions")
    need(type(software) is dict and bool(software), "software versions")
    need(all(type(k) is str and k and type(v) is str and v.strip() for k,v in software.items()), "descriptive software strings")
    warnings = given.get("warnings")
    need(type(warnings) is list and all(type(w) is str for w in warnings), "warnings strings")


def validate_bundle(output_dir, reference):
    need(reference.get("status") == "complete" and reference.get("pins") == pins(), "private reference scope/pins")
    need(reference.get("subjects") == list(SUBJECTS)
         and list(reference["condition_labels"]) == list(CONDITIONS)
         and np.array_equal(reference["sample_offsets"],OFFSETS)
         and list(reference["rejection_channel_labels"]) == list(CHANNELS), "private canonical axes")
    files = io.output_files(output_dir)
    metadata = io.json_bytes(io.read_bytes(files["run_metadata.json"]))
    validate_metadata(metadata,reference)
    validate_ledger(io.csv_read(files["annotations.csv"],ANNOTATION_COLUMNS,40000),reference["annotations"],"annotations")
    validate_ledger(io.csv_read(files["trials.csv"],TRIAL_COLUMNS,10000),reference["trials"],"trials")
    waveforms,defined = canonical_primitives(io.npz_read(files["erp_evidence.npz"]),reference)
    replay = participant_replay(waveforms,defined,reference)
    validate_participants(io.csv_read(files["per_subject.csv"],PERSON_COLUMNS,37),replay)
    validate_groups(io.json_bytes(io.read_bytes(files["n170.json"])),group_replay(replay))
    findings = io.read_bytes(files["findings.md"],limit=65536).decode("utf-8")
    need(bool(findings.strip()), "nonempty findings")
    need(not os.path.lexists(Path(output_dir)/"failure_report.json"), "late authoritative failure marker")
    return dict(status="accepted",n_subjects=37,n_events=len(reference["annotations"]),
                n_trials=len(reference["trials"]),n_eligible_epochs=len(reference["epoch_keys"]))
