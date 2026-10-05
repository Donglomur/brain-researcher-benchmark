"""Source-bound bank and nine-output verifier for the public Welch LOSO recipe."""
import hashlib
import os
from pathlib import Path

import numpy as np

import metric_contract as q

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
REF_PATH = Path(os.environ.get("REPAIR_REFERENCE_PATH", Path(__file__).with_name("reference.npz")))
BUILDER_ID = "sleepedf-direct-edf-manual-welch-source-only-v2"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _integer_array(value, shape, name):
    q.need(value.shape == shape and value.dtype.kind in "iu", f"bank {name} integer shape")
    q.need(np.all(value >= 0), f"bank {name} negative")


def validate_features(features, denominators):
    f = np.asarray(features, dtype=float); d = np.asarray(denominators, dtype=float)
    q.need(f.ndim == 2 and f.shape[1] == 10 and d.shape == (len(f), 2), "feature shape")
    q.need(np.isfinite(f).all() and np.isfinite(d).all(), "nonfinite features/PSD sum")
    upper = np.repeat(1/q.BIN_COUNTS, 2)
    q.need(np.all(f >= 0) and np.all(f <= upper+1e-12+1e-9*upper), "feature domain")
    q.need(np.all(d > 0), "PSD normalization denominator must be positive")
    weighted = (f.reshape(-1, 5, 2)*q.BIN_COUNTS[None, :, None]).sum(axis=1)
    q.need(np.all(np.abs(weighted-1) <= 1.1e-9), "weighted feature normalization")


def validate_metadata(actual, expected):
    q.need(isinstance(actual, dict) and set(expected)-{"software_versions"} <= set(actual), "metadata fields missing")
    versions = actual.get("software_versions")
    q.need(isinstance(versions, dict) and bool(versions) and all(isinstance(k, str) and k.strip()
           and isinstance(v, str) and v.strip() for k, v in versions.items()), "actual software_versions required")
    for key, value in expected.items():
        if key in ("software_versions", "source_observed"):
            continue
        q.match(actual[key], value, key, key in ("method_contract", "source_sha256"))
    a = actual["source_observed"]; b = expected["source_observed"]
    q.need(isinstance(a, dict) and set(b) <= set(a), "source_observed fields missing")
    for key in set(b)-{"subjects"}:
        q.match(a[key], b[key], "source_observed."+key)
    rows = a["subjects"]
    q.need(isinstance(rows, list) and len(rows) == len(b["subjects"]), "source subject coverage")
    indexed = {}
    for row in rows:
        q.need(isinstance(row, dict), "source subject object required")
        q.need(type(row.get("subject")) in (int, float) and type(row.get("recording")) in (int, float), "source subject numeric IDs")
        key = (q.integer(row["subject"]), q.integer(row["recording"]))
        q.need(key not in indexed, "duplicate source subject")
        indexed[key] = row
    q.need(set(indexed) == {(r["subject"], r["recording"]) for r in b["subjects"]}, "source subjects differ")
    for expected_row in b["subjects"]:
        row = dict(indexed[(expected_row["subject"], expected_row["recording"])])
        ref = dict(expected_row)
        for field, names in (("annotation_status_counts", q.ANNOTATION_STATUSES), ("epoch_status_counts", q.EPOCH_STATUSES)):
            q.need(isinstance(row.get(field), dict) and set(row[field]) <= set(names), "unknown/missing status counts")
            normalized = {name: row[field].get(name, 0) for name in names}
            q.match(normalized, {name: ref[field].get(name, 0) for name in names}, field, True)
            row.pop(field); ref.pop(field)
        q.match(row.get("annotation_description_counts"), ref["annotation_description_counts"], "source descriptions", True)
        q.match(row, ref, "source subject")


def validate_bank(ref, pilot=False):
    payload = ref["payload"]
    q.need(payload.get("builder_id") == BUILDER_ID, "failed_precondition: stale reference builder")
    q.need(digest(payload["method_json"].encode()) == q.METHOD_SHA, "reference method digest")
    q.need(digest(payload["manifest_json"].encode()) == q.SOURCE_SHA, "reference source digest")
    method = q.json_loads(payload["method_json"]); manifest = q.json_loads(payload["manifest_json"])
    meta = payload["metadata"]
    q.need(isinstance(meta, dict), "reference metadata object required")
    q.match(meta["method_contract"], method, "reference method", True)
    q.need(meta["method_contract_sha256"] == q.METHOD_SHA and meta["source_manifest_sha256"] == q.SOURCE_SHA, "reference pins")
    q.match(meta["source_sha256"], {f["path"]: f["sha256"] for f in manifest["files"]}, "reference source map", True)
    q.need(meta["status"] == ("resource_pilot" if pilot else "ok"), "reference must be a complete genuine run")
    q.need(len(meta["source_observed"]["subjects"]) == 6, "reference six source subjects")
    keys = ref["keys"]; n = len(keys)
    _integer_array(keys, (n, 3), "keys"); _integer_array(ref["truth"], (n,), "truth")
    expected_epochs = {}
    for row in payload["epochs"]:
        key = tuple(row[k] for k in ("subject", "recording", "onset_sample"))
        q.need(key not in expected_epochs, "reference duplicate candidate key")
        q.need(type(row["retained"]) is bool and row["retained"] == (row["drop_reason"] == "retained"), "reference epoch retention")
        q.need(row["n_samples"] == 3000 and row["end_sample_exclusive"] == row["onset_sample"]+3000, "reference sample bounds")
        expected_epochs[key] = row
    retained = {key: row for key, row in expected_epochs.items() if row["retained"]}
    actual_keys = [tuple(int(x) for x in row) for row in keys]
    q.need(len(set(actual_keys)) == n and set(actual_keys) == set(retained), "reference retained key coverage")
    q.need(actual_keys == sorted(actual_keys), "reference canonical fit order")
    q.need({k[0] for k in actual_keys} == set(range(6)) and all(k[1] == 1 for k in actual_keys), "reference subject/recording")
    q.need(np.array_equal(ref["truth"], [retained[k]["stage_id"] for k in actual_keys]), "reference source truth")
    validate_features(ref["features"], ref["psd_sum"])
    q.need(ref["probabilities"].shape == (n, 5), "reference probability shape")
    q.own_predictions(ref["probabilities"][keys[:, 0] == 0] if pilot else ref["probabilities"])
    annkeys = set()
    for row in payload["annotations"]:
        key = (row["subject"], row["recording"], row["annotation_index"])
        q.need(key not in annkeys, "reference duplicate annotation")
        annkeys.add(key)
    q.need(meta["source_observed"]["n_source_annotations"] == len(annkeys), "reference annotation count")
    q.need(meta["source_observed"]["n_candidate_epochs"] == len(expected_epochs), "reference candidate count")
    q.need(meta["source_observed"]["n_retained_epochs"] == n, "reference retained count")
    q.need(meta["source_observed"]["n_dropped_epochs"] == len(expected_epochs)-n, "reference drop count")
    validate_metadata(meta, meta)
    ref["method"] = method
    return ref


def load_reference(path=REF_PATH, pilot=False):
    with np.load(path, allow_pickle=False) as z:
        q.need("reference_json" in z.files, "failed_precondition: obsolete unbound reference")
        payload = q.json_loads(str(z["reference_json"].item()))
        ref = {name: z["ref_"+name].copy() for name in ("keys", "truth", "features", "psd_sum", "probabilities")}
    ref["payload"] = payload
    return validate_bank(ref, pilot)


def validate_source_table(path, rows, specification):
    submitted = q.table(path, specification["columns"], specification["key"])
    expected = {tuple(r[k] for k in specification["key"]): r for r in rows}
    q.need(set(submitted) == set(expected), f"{Path(path).name}: source key coverage differs")
    for key, row in expected.items():
        for field in specification["columns"]:
            q.compare_csv_value(submitted[key][field], row[field], Path(path).name+"."+field)


def validate_feature_output(path, ref):
    spec = ref["method"]["outputs"]["epoch_features.csv"]
    rows = q.table(path, spec["columns"], spec["key"])
    keys = [tuple(int(x) for x in row) for row in ref["keys"]]
    q.need(set(rows) == set(keys), "feature source epoch coverage")
    features = np.array([[q.number(rows[k][name]) for name in q.FEATURES] for k in keys])
    denom = np.array([[q.number(rows[k][name]) for name in ("psd_sum_fpz_cz", "psd_sum_pz_oz")] for k in keys])
    validate_features(features, denom)
    q.need(np.all(np.abs(features-ref["features"]) <= 1e-12+1e-9*np.abs(ref["features"])), "features differ from original source Welch")
    q.need(np.all(np.abs(denom-ref["psd_sum"]) <= 1e-9*np.abs(ref["psd_sum"])), "PSD sums differ from original source")


def validate_prediction_output(path, ref):
    spec = ref["method"]["outputs"]["epoch_predictions.csv"]
    rows = q.table(path, spec["columns"], spec["key"])
    keys = [tuple(int(x) for x in row) for row in ref["keys"]]
    q.need(set(rows) == set(keys), "prediction source epoch coverage")
    probabilities = np.array([[q.number(rows[k][name]) for name in q.PROBS] for k in keys])
    predicted = np.array([q.integer(rows[k]["predicted_stage"]) for k in keys])
    q.need(np.array_equal(predicted, q.own_predictions(probabilities)), "predicted class differs from own probability argmax")
    for index, k in enumerate(keys):
        q.need(q.integer(rows[k]["heldout_subject"]) == k[0], "held-out subject differs")
        q.need(q.integer(rows[k]["true_stage"]) == int(ref["truth"][index]), "true stage differs from original source")
    q.need(np.all(np.abs(probabilities-ref["probabilities"]) <= 1e-10+1e-9*np.abs(ref["probabilities"])), "probabilities differ from source-bound LOSO forest")
    return q.matrices(keys, ref["truth"], predicted)


def validate_metric_outputs(output, mats, ref):
    spec = ref["method"]["outputs"]
    rows = q.table(output/"confusion_counts.csv", spec["confusion_counts.csv"]["columns"], spec["confusion_counts.csv"]["key"])
    expected_keys = {(s, a, b) for s in range(6) for a in range(1, 6) for b in range(1, 6)}
    q.need(set(rows) == expected_keys, "complete 150 confusion cells required")
    for s, a, b in expected_keys:
        q.need(q.integer(rows[s, a, b]["n_epochs"]) == int(mats[s][a-1, b-1]), "confusion does not recompute")
    rows = q.table(output/"per_subject.csv", spec["per_subject.csv"]["columns"], ["subject"])
    q.need(set(rows) == {(s,) for s in range(6)}, "six subject metrics required")
    for s, matrix in mats.items():
        row = rows[s,]; m = q.confusion_metrics(matrix)
        q.need(q.integer(row["recording"]) == 1, "subject recording")
        train = q.json_loads(row["training_subjects"])
        q.need(isinstance(train, list) and len(train) == 5 and all(type(x) in (int, float) for x in train), "five training subjects required")
        train = [q.integer(x) for x in train]
        q.need(len(set(train)) == 5 and set(train) == set(range(6))-{s}, "training subject leakage/coverage")
        train_counts = sum(v for key, v in mats.items() if key != s).sum(axis=1)
        q.need(q.integer(row["n_train_epochs"]) == int(train_counts.sum()) and q.integer(row["n_test_epochs"]) == m["n"], "fold sample counts")
        for k, stage in enumerate(("w", "n1", "n2", "n3", "rem")):
            q.need(q.integer(row["n_train_"+stage]) == int(train_counts[k]), "training class support")
            q.need(q.integer(row["n_test_"+stage]) == int(matrix.sum(axis=1)[k]), "test class support")
        for field, key in (("overall_accuracy", "overall"), ("balanced_accuracy", "balanced"), ("kappa", "kappa")):
            q.compare_metric(row[field], m[key], field, is_kappa=key == "kappa")
        q.need(row["kappa_status"] == m["kappa_status"] and q.integer(row["n_supported_classes"]) == m["n_supported"], "metric support/status")
    q.validate_results(q.read_json(output/"staging_results.json"), q.results_from_matrices(mats))


def validate_output_directory(output, reference=None):
    output = Path(output); ref = reference if reference is not None else load_reference()
    for name in ref["method"]["outputs"]:
        q.need((output/name).is_file() and (output/name).stat().st_size > 0, f"missing/empty required output {name}")
    for name, field in (("annotations.csv", "annotations"), ("epochs.csv", "epochs")):
        validate_source_table(output/name, ref["payload"][field], ref["method"]["outputs"][name])
    validate_feature_output(output/"epoch_features.csv", ref)
    mats = validate_prediction_output(output/"epoch_predictions.csv", ref)
    validate_metric_outputs(output, mats, ref)
    validate_metadata(q.read_json(output/"run_metadata.json"), ref["payload"]["metadata"])
    q.need((output/"findings.md").read_text(encoding="utf-8").strip(), "findings is empty")
    return mats
