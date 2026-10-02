"""External prospective FCSTAB verifier. No source/oracle/stager imports.

The caller supplies a full independently authenticated SourceReference. Source
pins and the shared private kernel pin are frozen constants, never environment
values. Accepted z selects sets; accepted CSV/reliability receipts drive one
downstream replay. No historical or secondary canonical endpoint targets.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import sys
import types

import numpy as np

import artifact_reader as io

SOURCE_SHA = 'c57fed19c165e8a606c2b6a9aef89099103a2642d6ab54b93bf525d71ea46171'
METHOD_SHA = '004a396e4f4f37db956083939c84465819b7d3cd1a69569721c39e7884734ee4'
SCHEMA_SHA = 'bedafa3a91bcb6d6b83dd3ae6d4f2d4d9f7a58cc1f65631be3e5e7e86a47fadf'
IDS_SHA = '7645fc4276e63ed4f09e4135bac9d38da3b036a2e4e522fae432ae490d4d28cb'
KERNEL_SHA = 'a58264a5bb3ffd82b291434b2ca22843c276a42dab66d5e5abe220eb77ed7a49'
SCHEMES = ("forward", "reverse", "independent", "random")
SEGMENTS = ("first", "second", "full")
CSV_COLUMNS = ("subject_id", "n_edges", "forward_first_half", "forward_second_half",
               "forward_delta", "reverse_delta", "independent_delta", "random_delta")
PERSON_FIELDS = ("source_path", "source_sha256", "subject_id", "phenotype_row_index", "tokens",
                 "n_frames", "n_columns", "L", "header", "header_sha256", "source_column_ids",
                 "all_finite", "segment_support", "exact_constant_mask")
OBSERVED_FIELDS = ("n_source_files", "source_bytes", "n_selected_derivatives", "total_frames",
                   "n_phenotype_rows", "n_named_phenotype_rows", "n_no_filename_rows",
                   "phenotype_columns", "phenotype_ledger", "persons", "segment_ids",
                   "roi_ids", "common_roi_mask", "clock")


def need(condition, message):
    io.require(condition, message)


def pins():
    return dict(source_manifest_sha256=SOURCE_SHA, method_contract_sha256=METHOD_SHA,
                output_schema_sha256=SCHEMA_SHA, subject_ids_sha256=IDS_SHA)


def frozen_authority():
    need(all(type(value) is str and re.fullmatch("[0-9a-f]{64}", value)
             for value in (*pins().values(), KERNEL_SHA)), "private authority not frozen")


def load_kernel():
    """Compile only the SHA-verified private sibling buffer, never cached pyc."""
    raw = io.read_bytes(Path(__file__).with_name("selection_kernel.py"), 256*2**10)
    need(hashlib.sha256(raw).hexdigest() == KERNEL_SHA, "private shared kernel identity")
    name = "_fcstab_private_selection_kernel"
    module = types.ModuleType(name)
    module.__file__ = str(Path(__file__).with_name("selection_kernel.py"))
    previous = sys.modules.get(name)
    sys.modules[name] = module
    try:
        exec(compile(raw, module.__file__, "exec"), module.__dict__)
    finally:
        if previous is None: sys.modules.pop(name, None)
        else: sys.modules[name] = previous
    return module


def keyed(records, field, *, numeric=False):
    need(isinstance(records, list), "keyed records must be a list")
    result = {}
    for row in records:
        need(isinstance(row, dict) and field in row, "missing record key: "+field)
        key = io.integer(row[field], json_number=True) if numeric else row[field]
        need(type(key) is int if numeric else type(key) is str and bool(key), "invalid record identity")
        need(key not in result, "duplicate record identity")
        result[key] = row
    return result


def match(given, expected, *, atol=0.0, rtol=0.0, path="root"):
    """Required-field typed match; bounded descriptive extras do not override it."""
    if expected is None:
        need(given is None, path+": expected null")
    elif type(expected) is bool:
        need(type(given) is bool and given == expected, path+": Boolean mismatch")
    elif isinstance(expected, (int, np.integer)):
        need(io.integer(given, json_number=True) == int(expected), path+": integer mismatch")
    elif isinstance(expected, (float, np.floating)):
        value = io.real(given, json_number=True)
        need(abs(value-float(expected)) <= atol+rtol*abs(float(expected)), path+": numerical replay mismatch")
    elif isinstance(expected, str):
        need(type(given) is str and given == expected, path+": string mismatch")
    elif isinstance(expected, dict):
        need(isinstance(given, dict) and set(expected).issubset(given), path+": missing object fields")
        # Person membership and the four numerical families are closed identities,
        # not arbitrary metadata fields. Other finite extras remain descriptive.
        if path.rsplit(".", 1)[-1] in ("persons", "selection_schemes", "source_inference_support", "means"):
            need(set(given) == set(expected), path+": identity membership")
        for key, value in expected.items(): match(given[key], value, atol=atol, rtol=rtol, path=path+"."+key)
    elif isinstance(expected, (list, tuple)):
        need(isinstance(given, list), path+": list required")
        last = path.rsplit(".", 1)[-1]
        field = {"phenotype_ledger":"phenotype_row_index", "source_files":"path", "cohort":"file_id"}.get(last)
        if field:
            a, b = keyed(given, field, numeric=field=="phenotype_row_index"), keyed(list(expected), field, numeric=field=="phenotype_row_index")
            need(set(a) == set(b), path+": keyed membership")
            for key in b: match(a[key], b[key], atol=atol, rtol=rtol, path=path+"[]")
        else:
            need(len(given) == len(expected), path+": list length")
            for i, (a,b) in enumerate(zip(given, expected)): match(a,b,atol=atol,rtol=rtol,path=path+f"[{i}]")
    else:
        raise io.ArtifactError("unsupported trusted reference value: "+path)


def text_axis(array, expected, name):
    need(array.ndim == 1 and array.dtype.kind in "US", name+": string axis")
    values = (np.char.decode(array, "utf-8") if array.dtype.kind == "S" else array).tolist()
    need(len(values) == len(set(values)) and set(values) == set(expected), name+": membership")
    return [values.index(value) for value in expected]


def canonical_primitives(arrays, reference):
    required = {"subject_ids", "segment_ids", "roi_ids", "common_roi_mask", "edge_roi_i", "edge_roi_j", "fisher_z"}
    need(required.issubset(arrays), "missing NPZ arrays")
    ids = reference["subject_ids"]
    need(len(ids) == 40 and len(set(ids)) == 40 and all(type(s) is str for s in ids), "incomplete trusted cohort")
    porder = text_axis(arrays["subject_ids"], ids, "subject_ids")
    sorder = text_axis(arrays["segment_ids"], SEGMENTS, "segment_ids")
    rois = io.integer_array(arrays["roi_ids"])
    need(rois.shape == (200,) and set(rois.tolist()) == set(range(1,201)), "ROI identity")
    mask = arrays["common_roi_mask"]
    need(mask.shape == (200,) and mask.dtype.kind in "biu" and np.isin(mask,[0,1]).all(), "support mask type/shape")
    canonical_mask = mask[[rois.tolist().index(i) for i in range(1,201)]].astype(bool)
    need(np.array_equal(canonical_mask, reference["common_roi_mask"]), "source support mask")
    left, right = io.integer_array(arrays["edge_roi_i"]), io.integer_array(arrays["edge_roi_j"])
    need(left.ndim == right.ndim == 1 and left.shape == right.shape, "edge axis shape")
    submitted_pairs = list(zip(left.tolist(),right.tolist()))
    canonical_pairs = list(zip(map(int,reference["edge_roi_i"]),map(int,reference["edge_roi_j"])))
    need(len(submitted_pairs) == len(set(submitted_pairs)) and set(submitted_pairs) == set(canonical_pairs), "edge membership")
    need(canonical_pairs == sorted(canonical_pairs) and all(i<j for i,j in canonical_pairs), "trusted canonical pair order")
    E = len(canonical_pairs)
    need(1 <= E <= 19900, "edge support")
    z = arrays["fisher_z"]
    need(z.dtype.kind in "iuf" and z.shape == (40,3,E), "Fisher-z type/shape")
    storage_index = {pair:i for i,pair in enumerate(submitted_pairs)}
    canonical_index = {pair:i for i,pair in enumerate(canonical_pairs)}
    eorder = [storage_index[pair] for pair in canonical_pairs]
    aligned = np.ascontiguousarray(z[np.ix_(porder,sorder,eorder)], dtype=np.float64)
    need(np.isfinite(aligned).all(), "nonfinite z")
    # Reverse map supports order-insensitive selected sets expressed in the
    # submitted storage axis. Canonical arithmetic never depends on that order.
    submitted_to_canonical = {i:canonical_index[pair] for i,pair in enumerate(submitted_pairs)}
    return aligned, np.asarray(canonical_pairs,dtype=np.int64), submitted_to_canonical


def csv_rows(rows, ids, E):
    need(len(rows) == len(ids), "CSV subject count")
    found = {}
    for row in rows:
        need(set(CSV_COLUMNS).issubset(row), "CSV required columns")
        sid = row["subject_id"]
        need(type(sid) is str and sid in ids and sid not in found, "CSV identity/duplicate")
        need(io.integer(row["n_edges"]) == E, "CSV n_edges")
        found[sid] = dict(subject_id=sid,n_edges=E,
                          **{key:io.real(row[key]) for key in CSV_COLUMNS[2:]})
    return [found[sid] for sid in ids]


def reliability_receipts(evidence_by_id, ids):
    result = {}
    for sid in ids:
        ev = evidence_by_id[sid]
        need(isinstance(ev.get("reliability"),dict), "reliability object")
        row = ev["reliability"]
        need({"overlap","edge_pearson","edge_spearman","status"}.issubset(row), "reliability fields")
        need(type(row["status"]) is str, "reliability status type")
        out = {"status":row["status"]}
        for key in ("overlap","edge_pearson","edge_spearman"):
            value = row[key]
            if value is None:
                need(key != "overlap", "overlap cannot be null")
            else:
                value = io.real(value,json_number=True)
                need((0 if key=="overlap" else -1) <= value <= 1, "reliability domain")
            out[key] = value
        result[sid] = out
    return result


def validate_metadata(summary, reference):
    ids, fids = reference["subject_ids"], reference["participant_file_ids"]
    expected = dict(schema_version="fcstab-summary-v3",task_id="FCSTAB-001",status="complete",pins=pins(),n_subjects=40,
                    cohort=[dict(file_id=fid,subject_id=sid) for fid,sid in zip(fids,ids)],source_files=reference["source_files"])
    match(summary,expected)
    observed = reference["source_observed"]
    view = {key:observed[key] for key in OBSERVED_FIELDS}
    view["persons"] = {fid:{key:observed["persons"][fid][key] for key in PERSON_FIELDS} for fid in fids}
    match(summary.get("source_observed"),view,path="source_observed")
    software = summary.get("software")
    need(isinstance(software,dict), "software object")
    for name in ("python","numpy","scipy"):
        need(type(software.get(name)) is str and software[name].strip(), "software descriptive string")


def numerical_domains(summary):
    for record in summary["selection_schemes"].values():
        for key in ("delta_sd","delta_se"):
            need(io.real(record[key],json_number=True) >= 0, "nonnegative dispersion")
        need(0 <= io.integer(record["n_negative"],json_number=True) <= 40, "negative count domain")
        if record["p"] is not None: need(0 <= io.real(record["p"],json_number=True) <= 1, "p domain")
        if record["ci95_lo"] is not None:
            need(io.real(record["ci95_lo"],json_number=True) <= io.real(record["ci95_hi"],json_number=True), "CI order")
    for key in ("p_lower","p_upper","tost_p"):
        value = summary["equivalence"][key]
        if value is not None: need(0 <= io.real(value,json_number=True) <= 1, "TOST probability domain")
    reliability = summary["reliability"]
    need(0 <= io.real(reliability["overlap"],json_number=True) <= 1, "overlap summary domain")
    for name in ("edge_pearson","edge_spearman"):
        value = reliability[name]["mean"]
        if value is not None: need(-1 <= io.real(value,json_number=True) <= 1, "correlation summary domain")


def validate(output_dir, reference):
    frozen_authority()
    need(reference.get("status") == "complete" and reference.get("pins") == pins(), "trusted reference scope/pins")
    data = io.read_artifacts(output_dir)
    ids = reference["subject_ids"]
    z, pairs, axis_map = canonical_primitives(data["connectivity.npz"],reference)
    E, k = len(pairs), max(1,len(pairs)//10)
    rows = csv_rows(data["stability.csv"],ids,E)
    evidence, summary = data["selection_evidence.json"],data["summary.json"]
    match(evidence,dict(schema_version="fcstab-selection-v3",task_id="FCSTAB-001",status="complete",pins=pins(),n_edges=E,k=k,seed=0))
    ev_by_id = keyed(evidence.get("subjects"),"subject_id")
    need(set(ev_by_id) == set(ids), "selection subject membership")
    accepted_reliability = reliability_receipts(ev_by_id,ids)
    validate_metadata(summary,reference)
    kernel = load_kernel()
    try:
        replay = kernel.analyze(z,reference["fisher_z"],ids,pairs,accepted_rows=rows,
                                accepted_reliability=accepted_reliability)
    except ValueError as exc:
        raise io.ArtifactError("accepted primitive/row replay: "+str(exc)) from exc
    for sid in ids:
        given, expected = ev_by_id[sid],replay["evidence"][sid]
        training = given.get("training_subject_ids")
        need(isinstance(training,list) and all(type(x) is str for x in training)
             and len(training)==39 and len(set(training))==39
             and set(training)==set(ids)-{sid}, "training membership")
        for scheme in SCHEMES:
            values = given.get(scheme+"_edge_indices")
            need(isinstance(values,list) and len(values)==k, "selected set size")
            indices = [io.integer(v,json_number=True) for v in values]
            need(len(set(indices))==k and all(v in axis_map for v in indices), "selected index domain/duplicate")
            need({axis_map[v] for v in indices} == set(expected[scheme+"_edge_indices"]), "accepted-z selected set")
        match(given.get("means"),expected["means"],atol=1e-6,rtol=1e-6,path="means")
        match(given.get("reliability"),expected["reliability"],atol=1e-6,rtol=1e-6,path="reliability")
    match(summary,replay["summaries"],atol=1e-8,rtol=1e-6)
    support = {scheme:{"status":replay["support_diagnostics"][scheme]["status"]} for scheme in SCHEMES}
    match(summary.get("source_inference_support"),support,path="source_inference_support")
    numerical_domains(summary)
    root = io.guarded_path(output_dir,directory=True)
    need(not os.path.lexists(root/io.FAILURE), "late authoritative failure marker")
    return dict(status="accepted",n_subjects=40,n_edges=E,k=k)


validate_output_directory = validate
