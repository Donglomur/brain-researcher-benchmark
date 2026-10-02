"""Keyed source-canonical validation, with no bank or participant-derived truth."""
from collections import Counter
import numpy as np
import io_contract as io_c
import lifespan_statistics as science

need = io_c.need
ARRAYS = ("subject_id", "roi_index", "subject_frame_offsets", "frame_index",
          "roi_timeseries", "vertex_offsets", "vertex_index", "parcel_status",
          "edge_roi_index", "edge_valid", "raw_r", "fisher_z", "group_valid", "group_features")


def json_number(value):
    need(type(value) in (int, float), "JSON number required, not text/Boolean")
    return io_c.number(value)


def json_integer(value):
    json_number(value)
    return io_c.integer(value)


def close(actual, expected, atol, rtol, label):
    a, e = np.asarray(actual, dtype=np.float64), np.asarray(expected, dtype=np.float64)
    need(a.shape == e.shape and np.isfinite(a).all() and np.isfinite(e).all(), label + ": finite shape")
    need(np.all(np.abs(a-e) <= atol + rtol*np.abs(e)), label + ": numerical mismatch")


def neighbors(actual, expected, label):
    a, q = np.asarray(actual, dtype=np.float64), np.asarray(expected, dtype=np.float32)
    with np.errstate(over="ignore"):
        low = np.nextafter(q, np.float32(-np.inf)).astype(np.float64)
        high = np.nextafter(q, np.float32(np.inf)).astype(np.float64)
    low = np.where(np.isfinite(low), low, q.astype(np.float64))
    high = np.where(np.isfinite(high), high, q.astype(np.float64))
    need(a.shape == q.shape and np.isfinite(a).all() and np.all((a >= low) & (a <= high)), label + ": float32 neighbors")


def keyed(rows, key, expected, numeric=False):
    need(isinstance(rows, list), "record list required")
    out = {}
    for row in rows:
        need(isinstance(row, dict) and key in row, "missing record key")
        k = io_c.integer(row[key]) if numeric else row[key]
        need(isinstance(k, (str, int)) and not isinstance(k, bool) and k not in out, "duplicate/invalid record key")
        out[k] = row
    need(set(out) == set(expected), "record key coverage: " + key)
    return out


def exact_subset(a, e, label):
    """Only declared fields; bool is not a numeric alias; extras survive."""
    if isinstance(e, dict):
        need(isinstance(a, dict) and set(e) <= set(a), label + ": object fields")
        for k, v in e.items(): exact_subset(a[k], v, label + "/" + k)
    elif isinstance(e, list):
        need(isinstance(a, list) and len(a) == len(e), label + ": list shape")
        for x, y in zip(a, e): exact_subset(x, y, label)
    elif e is None or isinstance(e, (str, bool)):
        need(type(a) is type(e) and a == e, label + ": categorical mismatch")
    elif isinstance(e, (int, np.integer)):
        need(json_integer(a) == e, label + ": integer mismatch")
    else:
        need(json_number(a) == e, label + ": scalar mismatch")


def scalar(a, e, key, *, csv=False):
    if e is None:
        need(a == "" if csv else a is None, key + ": undefined must remain empty/null")
    elif isinstance(e, str):
        need(isinstance(a, str) and a == e, key + ": text mismatch")
    elif isinstance(e, (int, np.integer)):
        need(io_c.integer(a) == e, key + ": integer mismatch")
    else:
        value = io_c.number(a)
        if key in ("age", "age_computational"):
            need(value >= 0, "negative age")
            neighbors(value, e, key)
        elif key == "age_source":
            need(value >= 0, "negative age")
            close(value, e, 1e-9, 0, key)
        else:
            close(value, e, 1e-6, 1e-7, key)


def table(raw, expected, key, *, numeric=False, fields=None):
    got = keyed(io_c.csv_bytes(raw), key, [r[key] for r in expected], numeric)
    for row in expected:
        actual, required = got[row[key]], fields or row.keys()
        need(set(required) <= set(actual), "missing CSV columns")
        for field in required: scalar(actual[field], row[field], field, csv=True)
    return got


def axis(values, expected, label, numeric=False):
    a = io_c.integers(values) if numeric else io_c.strings(values)
    need(a.shape == (len(expected),), label + ": axis shape")
    items = a.tolist()
    need(len(set(items)) == len(items) and set(items) == set(expected), label + ": identities")
    return np.asarray([items.index(v) for v in expected], dtype=np.int64), a


def real_array(a):
    a = np.asarray(a)
    need(a.dtype.kind == "f" and a.dtype.itemsize in (4, 8), "real array requires float32/float64")
    return a.astype(np.float64)


def masked(actual, expected, mask, label):
    need(actual.shape == expected.shape and np.isnan(actual[~mask]).all(), label + ": invalid must be NaN")
    close(actual[mask], expected[mask], 1e-8, 1e-7, label)


def primitives(a, ref):
    b, parcels = ref["basis"], ref["parcels"]
    need(set(ARRAYS) <= set(a), "missing primitive arrays")
    for k, value in a.items():
        if k not in ARRAYS and value.dtype.kind in "fc":
            need(np.isfinite(value).all(), "nonfinite extra primitive")
    s, t, r = b["roi_timeseries"].shape
    e = len(b["edge_roi_index"])
    si, _ = axis(a["subject_id"], b["subject_id"].tolist(), "subject")
    ri, _ = axis(a["roi_index"], b["roi_index"].tolist(), "ROI", True)
    off, frames = io_c.integers(a["subject_frame_offsets"]), io_c.integers(a["frame_index"])
    x = real_array(a["roi_timeseries"])
    need(off.shape == (s+1,) and np.array_equal(off, np.arange(s+1)*t) and frames.shape == (s*t,) and x.shape == (s*t, r), "frame geometry")
    for canonical_i, submitted_i in enumerate(si):
        start, end = off[submitted_i:submitted_i+2]
        fi, _ = axis(frames[start:end], list(range(t)), "frame", True)
        neighbors(x[start:end][fi][:, ri], b["roi_timeseries"][canonical_i], "ROI means")
    vo, vi = io_c.integers(a["vertex_offsets"]), io_c.integers(a["vertex_index"])
    need(vo.shape == (r+1,) and vi.ndim == 1 and vo[0] == 0 and vo[-1] == len(vi) and np.all(np.diff(vo) > 0), "vertex offsets")
    for canonical_j, submitted_j in enumerate(ri):
        block = vi[vo[submitted_j]:vo[submitted_j+1]]
        expected = parcels[canonical_j]["vertices"]
        need(len(block) == len(expected) and np.array_equal(np.sort(block), expected), "source vertex membership")
    status = io_c.strings(a["parcel_status"])
    need(status.shape == (s, r) and np.array_equal(status[np.ix_(si, ri)], b["parcel_status"]), "canonical parcel statuses")
    ij = io_c.integers(a["edge_roi_index"])
    need(ij.shape == (e, 2), "edge identity shape")
    keys = [tuple(sorted(pair)) for pair in ij.tolist()]
    expected_keys = [tuple(pair) for pair in b["edge_roi_index"].tolist()]
    need(len(set(keys)) == e and set(keys) == set(expected_keys), "unordered edge coverage")
    mapping = {key: i for i, key in enumerate(keys)}
    ei = np.asarray([mapping[k] for k in expected_keys])
    valid = io_c.mask(a["edge_valid"])
    need(valid.shape == (s, e) and np.array_equal(valid[np.ix_(si, ei)], b["edge_valid"]), "canonical edge mask")
    delta = {}
    for name in ("raw_r", "fisher_z"):
        values = real_array(a[name])
        need(values.shape == (s, e), name + ": shape")
        values = values[np.ix_(si, ei)]
        masked(values, b[name], b["edge_valid"], name)
        difference = np.abs(values[b["edge_valid"]]-b[name][b["edge_valid"]])
        delta[name] = float(difference.max(initial=0))
    gm, g = io_c.mask(a["group_valid"]), real_array(a["group_features"])
    need(gm.shape == (r,r) and g.shape == (r,r), "group shape")
    gm, g = gm[np.ix_(ri, ri)], g[np.ix_(ri, ri)]
    need(np.array_equal(gm, b["group_valid"]) and np.all(np.diag(g) == 0), "group support/zero diagonal")
    masked(g, b["group_features"], gm, "group features")
    return delta


def partition(snapshot, ref):
    b, expected = ref["basis"], ref["partition_doc"]
    rows = keyed(io_c.csv_bytes(snapshot["roi_partition.csv"]), "roi_index", b["roi_index"].tolist(), True)
    labels = []
    for key in b["roi_index"]:
        row = rows[int(key)]
        need({"roi_index", "network_id", "status"} <= set(row) and row["status"] == expected["status"], "partition CSV status/schema")
        labels.append(row["network_id"])
    if b["partition"]["labels"] is None:
        need(all(label == "" for label in labels), "undefined partition labels")
        clusters = []
    else:
        need(all(isinstance(label, str) and len(label) > 0 for label in labels), "empty cluster label")
        need(science.same_partition(np.asarray(labels), b["partition"]["labels"]), "canonical coassignment mismatch")
        clusters = [dict(network_id=k, n_rois=v) for k, v in Counter(labels).items()]
    doc = io_c.json_bytes(snapshot["partition.json"])
    exact_subset(doc, {k:v for k,v in expected.items() if k not in ("clusters", "incomplete_subject_ids")}, "partition")
    got = keyed(doc.get("clusters"), "network_id", [c["network_id"] for c in clusters])
    for row in clusters: exact_subset(got[row["network_id"]], row, "cluster")
    unordered_ids(doc.get("incomplete_subject_ids"), expected["incomplete_subject_ids"])
    if "fit_diagnostics" in doc:
        d = doc["fit_diagnostics"]
        need(isinstance(d, dict), "fit diagnostics object")
        if "inertia" in d: need(json_number(d["inertia"]) >= 0, "negative inertia")
        for key in ("n_iter", "n_iter_", "iterations"):
            if key in d: need(1 <= json_integer(d[key]) <= 300, "iteration diagnostic domain")
        for key in ("centers", "cluster_centers"):
            if key in d:
                centers = np.asarray(d[key])
                need(centers.dtype.kind in "iuf", "center JSON numeric values")
                centers = centers.astype(np.float64)
                need(centers.ndim == 2 and centers.shape[1] == len(labels) and
                     len(clusters) <= centers.shape[0] <= 7 and np.isfinite(centers).all(), "centers shape/finite")
                ra = d.get("roi_index", d.get("roi_order"))
                na = d.get("network_id", d.get("network_ids"))
                need(ra is not None and na is not None, "center axes required")
                need(isinstance(ra, list), "center ROI list")
                axis(np.asarray([json_integer(v) for v in ra]), b["roi_index"].tolist(), "center ROI", True)
                names = io_c.strings(np.asarray(na))
                need(names.shape == (len(centers),) and all(len(v) for v in names) and
                     len(set(names.tolist())) == len(names) and
                     {c["network_id"] for c in clusters} <= set(names.tolist()), "center network axes")


def unordered_ids(a, expected):
    need(isinstance(a, list) and all(isinstance(v, str) for v in a) and len(set(a)) == len(a) and set(a) == set(expected), "subject ID list")


def results(raw, ref):
    a, e = io_c.json_bytes(raw), ref["basis"]["results"]
    exact_subset(a, {k:e[k] for k in ("status", "n_subjects")}, "results")
    ar = a.get("age_range")
    need(isinstance(ar, list) and len(ar) == 2, "age range shape")
    ar = [json_number(v) for v in ar]
    need(0 <= ar[0] <= ar[1], "age range domain")
    neighbors(ar, e["age_range"], "age range")
    for name in ("overall_connectivity_vs_age", "system_segregation_vs_age"):
        need(name in a and isinstance(a[name], dict), "missing endpoint")
        x, y = a[name], e[name]
        exact_subset(x, {k:y[k] for k in ("status", "n_expected", "n_defined")}, name)
        unordered_ids(x.get("undefined_subject_ids"), y["undefined_subject_ids"])
        need({"pearson_r", "p", "ci95"} <= set(x), "missing endpoint values")
        if y["status"] != "ok":
            need(all(x[k] is None for k in ("pearson_r", "p", "ci95")), "undefined endpoint numeric")
        else:
            close(json_number(x["pearson_r"]), y["pearson_r"], 1e-6, 0, "endpoint r")
            p = json_number(x["p"])
            need(0 <= p <= 1, "p domain")
            close(p, y["p"], 1e-10, 1e-7, "endpoint p")
            need(isinstance(x["ci95"], list) and len(x["ci95"]) == 2, "CI shape")
            ci = [json_number(v) for v in x["ci95"]]
            need(ci[0] <= ci[1], "reversed CI")
            close(ci, y["ci95"], 1e-6, 0, "CI")


def metadata(raw, ref):
    a, e = io_c.json_bytes(raw), ref["metadata"]
    exact_subset(a, {k:v for k,v in e.items() if k not in ("source_files", "source_observed", "software_versions", "warnings")}, "metadata")
    need(isinstance(a.get("software_versions"), dict), "software versions object")
    need(isinstance(a.get("warnings"), list) and all(isinstance(v, str) for v in a["warnings"]), "warning strings")
    files = keyed(a.get("source_files"), "path", [r["path"] for r in e["source_files"]])
    for row in e["source_files"]: exact_subset(files[row["path"]], row, "source file")
    observed = a.get("source_observed")
    need(isinstance(observed, dict), "source observed object")
    exact_subset(observed, {k:v for k,v in e["source_observed"].items() if k != "subjects"}, "source observed")
    people = keyed(observed.get("subjects"), "subject_id", ref["basis"]["subject_id"].tolist())
    for row in e["source_observed"]["subjects"]: exact_subset(people[row["subject_id"]], row, "source header")


def validate(output_dir, reference):
    """No fits here: original-source reconstruction is completed by the caller."""
    snap = io_c.output_snapshot(output_dir)
    table(snap["cohort.csv"], reference["cohort_rows"], "subject_id")
    table(snap["parcels.csv"], reference["parcels"], "roi_index", numeric=True,
          fields=("roi_index", "hemisphere", "annotation_id", "label_name", "vertex_count"))
    delta = primitives(snap["connectome_primitives.npz"], reference)
    partition(snap, reference)
    table(snap["connectome_summary.csv"], reference["basis"]["summary_rows"], "subject_id")
    results(snap["results.json"], reference)
    metadata(snap["run_metadata.json"], reference)
    need(bool(snap["findings.md"].decode("utf-8").strip()), "empty findings")
    return dict(status="ok", n_subjects=len(reference["basis"]["subject_id"]),
                n_parcels=len(reference["parcels"]), max_abs_edge_differences=delta)
