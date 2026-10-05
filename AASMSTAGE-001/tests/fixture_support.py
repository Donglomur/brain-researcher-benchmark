"""Serialization helpers and unmistakably synthetic mechanics fixtures, not banks."""
import csv
import json
from pathlib import Path

import numpy as np

import metric_contract as q


def write_csv(path, columns, rows):
    with Path(path).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(columns), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: int(v) if isinstance(v, (bool, np.bool_)) else v for k, v in row.items() if k in columns})


def read_csv(path):
    with Path(path).open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        return reader.fieldnames, list(reader)


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, allow_nan=False), encoding="utf-8")


def emit_output(output, ref, probabilities=None, features=None, psd_sum=None):
    """Participant-format emitter for fixture/mutation data; never fits a model."""
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    probs = ref["probabilities"] if probabilities is None else probabilities
    f = ref["features"] if features is None else features
    d = ref["psd_sum"] if psd_sum is None else psd_sum
    spec = ref["method"]["outputs"]
    for name, field in (("annotations.csv", "annotations"), ("epochs.csv", "epochs")):
        write_csv(output/name, spec[name]["columns"], ref["payload"][field])
    feature_rows, prediction_rows = [], []
    prediction = q.own_predictions(probs)
    for i, key in enumerate(ref["keys"]):
        identity = dict(zip(("subject", "recording", "onset_sample"), (int(v) for v in key)))
        feature_rows.append({**identity, **dict(zip(q.FEATURES, f[i])), "psd_sum_fpz_cz": d[i, 0], "psd_sum_pz_oz": d[i, 1]})
        prediction_rows.append({**identity, "heldout_subject": int(key[0]), "true_stage": int(ref["truth"][i]),
                                "predicted_stage": int(prediction[i]), **dict(zip(q.PROBS, probs[i]))})
    write_csv(output/"epoch_features.csv", spec["epoch_features.csv"]["columns"], feature_rows)
    write_csv(output/"epoch_predictions.csv", spec["epoch_predictions.csv"]["columns"], prediction_rows)
    mats = q.matrices(ref["keys"], ref["truth"], prediction)
    counts, subjects = [], []
    for subject, matrix in mats.items():
        for a in range(5):
            for b in range(5):
                counts.append({"subject": subject, "true_stage": a+1, "predicted_stage": b+1, "n_epochs": int(matrix[a, b])})
        m = q.confusion_metrics(matrix)
        train = sum(v for k, v in mats.items() if k != subject).sum(axis=1)
        row = {"subject": subject, "recording": 1, "training_subjects": json.dumps([s for s in range(6) if s != subject]),
               "n_train_epochs": int(train.sum()), "n_test_epochs": m["n"], "overall_accuracy": m["overall"],
               "balanced_accuracy": m["balanced"], "kappa": m["kappa"], "kappa_status": m["kappa_status"], "n_supported_classes": m["n_supported"]}
        for k, name in enumerate(("w", "n1", "n2", "n3", "rem")):
            row["n_train_"+name] = int(train[k]); row["n_test_"+name] = int(matrix.sum(axis=1)[k])
        subjects.append(row)
    write_csv(output/"confusion_counts.csv", spec["confusion_counts.csv"]["columns"], counts)
    write_csv(output/"per_subject.csv", spec["per_subject.csv"]["columns"], subjects)
    write_json(output/"staging_results.json", q.results_from_matrices(mats))
    write_json(output/"run_metadata.json", ref["payload"]["metadata"])
    (output/"findings.md").write_text("A finite descriptive calculation on the declared inputs.\n", encoding="utf-8")


def toy_reference():
    """Thirty made-up epochs solely to test parsing/arithmetic; never load_reference."""
    method_path = Path(__file__).parents[1]/"environment"/"method_contract.json"
    method = q.read_json(method_path)
    keys = np.array([[s, 1, k*3000] for s in range(6) for k in range(5)], dtype=np.int64)
    truth = np.tile(np.arange(1, 6), 6)
    probabilities = np.full((30, 5), .05)
    probabilities[np.arange(30), truth-1] = .8
    weights = np.array([[.3, .25], [.2, .15], [.1, .1], [.15, .2], [.25, .3]])
    features = np.tile((weights/q.BIN_COUNTS[:, None]).reshape(1, 10), (30, 1))
    annotations, epochs, observed = [], [], []
    for s in range(6):
        for k in range(5):
            annotations.append({"subject": s, "recording": 1, "annotation_index": k, "tal_index": k+1,
                                "onset_s": float(k*30), "duration_s": 30.0, "description": "synthetic stage "+str(k+1),
                                "stage_id": k+1, "effective_onset_s": float(k*30), "effective_stop_s": float(k*30+30),
                                "n_complete_chunks": 1, "discarded_tail_s": 0.0, "status": "used"})
            epochs.append({"subject": s, "recording": 1, "annotation_index": k, "chunk_index": 0,
                           "onset_s": float(k*30), "onset_sample": k*3000, "end_sample_exclusive": (k+1)*3000,
                           "n_samples": 3000, "stage_id": k+1, "retained": True, "drop_reason": "retained"})
        observed.append({"subject": s, "recording": 1, "sfreq_hz": 100.0,
                         "annotation_description_counts": {"synthetic": 5},
                         "annotation_status_counts": {"used": 5}, "epoch_status_counts": {"retained": 5}})
    metadata = {"status": "ok", "task_id": "AASMSTAGE-001", "pipeline_id": q.PIPELINE,
                "method_contract": method, "source_sha256": {"SYNTHETIC_NOT_SOURCE_EVIDENCE": "0"*64},
                "software_versions": {"synthetic-fixture": "1"},
                "source_observed": {"n_subjects": 6, "n_source_annotations": 30, "n_candidate_epochs": 30,
                                    "n_retained_epochs": 30, "n_dropped_epochs": 0, "subjects": observed}}
    return {"method": method, "keys": keys, "truth": truth, "features": features,
            "psd_sum": np.full((30, 2), 1e-12), "probabilities": probabilities,
            "payload": {"annotations": annotations, "epochs": epochs, "metadata": metadata,
                        "fixture_only": True}}
