"""Build the v2 bank from retained oracle outputs and hash-verified raw EDFs.

The source epoch identities/labels are reread independently of the output CSV.
Predictions must come from a retained execution of solution/compute.py; this
authoring tool does not fabricate a bank from aggregate target scores.
"""
import argparse
import csv
import importlib.util
import json
from pathlib import Path

import numpy as np

TASK = Path(__file__).resolve().parents[1]


def oracle_module():
    spec = importlib.util.spec_from_file_location("sleepedf_oracle", TASK / "solution/compute.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def integer(value, field):
    result = int(value)
    if str(result) != str(value):
        raise ValueError(f"noncanonical integer in {field}: {value!r}")
    return result


def build(output_dir, data_dir, destination):
    from sklearn.metrics import accuracy_score, cohen_kappa_score, confusion_matrix

    oracle = oracle_module()
    output_dir = Path(output_dir)
    inputs, hashes = oracle.load_inputs(data_dir)
    metadata = json.loads((output_dir / "run_metadata.json").read_text())
    contract = oracle.metadata_contract(hashes)
    if metadata.get("status") != "ok" or any(metadata.get(k) != v for k, v in contract.items()):
        raise ValueError("oracle metadata does not match the pinned source/pipeline contract")
    with (output_dir / "epoch_predictions.csv").open(newline="") as stream:
        reader = csv.DictReader(stream)
        if set(reader.fieldnames or ()) != set(oracle.PREDICTION_FIELDS):
            raise ValueError("unexpected prediction CSV fields")
        rows = list(reader)
    expected, observations = [], []
    for subject in oracle.SUBJECTS:
        _, labels, onsets, observed = oracle.subject_epochs(
            inputs[subject, "psg"], inputs[subject, "hypnogram"], preload=False)
        observations.append({"subject": subject, "recording": oracle.RECORDING, **observed})
        expected.extend((subject, oracle.RECORDING, int(onset), oracle.CLASSES[int(label)])
                        for onset, label in zip(onsets, labels))
    if metadata.get("per_subject_observations") != observations:
        raise ValueError("reported crop/count observations differ from raw EDF annotations")
    observed_keys, predictions = [], []
    for row in rows:
        subject = integer(row["subject"], "subject")
        observed_keys.append((subject, integer(row["recording"], "recording"),
                              integer(row["onset_sample"], "onset_sample"), row["true_class"]))
        if integer(row["heldout_subject"], "heldout_subject") != subject:
            raise ValueError("prediction has the wrong held-out subject")
        if row["predicted_class"] not in oracle.CLASSES:
            raise ValueError("prediction has an unknown class")
        predictions.append(row["predicted_class"])
    if observed_keys != expected:
        raise ValueError("oracle epoch identities/order/labels differ from the raw source")
    subjects = np.asarray([key[0] for key in expected], dtype=np.int64)
    truth = np.asarray([key[3] for key in expected], dtype="U3")
    predictions = np.asarray(predictions, dtype="U3")
    per_subject, expected_counts = [], []
    for subject in oracle.SUBJECTS:
        selected = subjects == subject
        per_subject.append({
            "subject": subject, "n_test_epochs": int(selected.sum()),
            "accuracy": float(accuracy_score(truth[selected], predictions[selected])),
            "kappa": float(cohen_kappa_score(truth[selected], predictions[selected])),
        })
        matrix = confusion_matrix(truth[selected], predictions[selected], labels=oracle.CLASSES)
        for i, true_class in enumerate(oracle.CLASSES):
            for j, predicted_class in enumerate(oracle.CLASSES):
                expected_counts.append({"subject": str(subject), "true_class": true_class,
                                        "predicted_class": predicted_class, "n_epochs": str(matrix[i, j])})
    with (output_dir / "confusion_counts.csv").open(newline="") as stream:
        if list(csv.DictReader(stream)) != expected_counts:
            raise ValueError("oracle confusion table differs from its epoch predictions")
    with (output_dir / "per_subject.csv").open(newline="") as stream:
        submitted_subjects = list(csv.DictReader(stream))
    if len(submitted_subjects) != len(per_subject):
        raise ValueError("oracle per-subject table has the wrong number of rows")
    for row, actual in zip(submitted_subjects, per_subject):
        for key, value in actual.items():
            if not np.isclose(float(row[key]), value, rtol=0, atol=1e-12):
                raise ValueError(f"oracle per-subject {key} differs from epoch predictions")
    accuracy = float(accuracy_score(truth, predictions))
    kappa = float(cohen_kappa_score(truth, predictions))
    result = json.loads((output_dir / "staging_results.json").read_text())
    exact_results = {"pipeline_id": oracle.PIPELINE_ID, "cv_scheme": "leave-one-subject-out",
                     "n_epochs": len(expected), "n_subjects": 6, "n_classes": 5,
                     "classes": oracle.CLASSES}
    if any(result.get(key) != value for key, value in exact_results.items()):
        raise ValueError("oracle headline identity/count contract is inconsistent")
    if not np.isclose(result["accuracy"], accuracy, rtol=0, atol=1e-12):
        raise ValueError("oracle headline accuracy differs from epoch predictions")
    if not np.isclose(result["cohen_kappa"], kappa, rtol=0, atol=1e-12):
        raise ValueError("oracle pooled kappa differs from epoch predictions")
    stats = {"pipeline_id": oracle.PIPELINE_ID, "source_sha256": hashes,
             "metadata_contract": contract, "per_subject": per_subject,
             "n_epochs": len(expected), "accuracy": accuracy, "cohen_kappa": kappa}
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        destination, ref_subject=subjects,
        ref_recording=np.asarray([key[1] for key in expected], dtype=np.int64),
        ref_onset_sample=np.asarray([key[2] for key in expected], dtype=np.int64),
        ref_true_class=truth, ref_predicted_class=predictions,
        ref_stats=np.asarray(json.dumps(stats, sort_keys=True, allow_nan=False)),
    )
    print(json.dumps({"reference": str(destination), "pipeline_id": oracle.PIPELINE_ID,
                      "n_epochs": len(expected), "accuracy": accuracy, "cohen_kappa": kappa}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path, help="retained real oracle output")
    parser.add_argument("--data-dir", required=True, type=Path, help="hash-pinned EDF/manifest directory")
    parser.add_argument("--reference", type=Path, default=TASK / "tests/reference.npz")
    args = parser.parse_args()
    build(args.output_dir, args.data_dir, args.reference)


if __name__ == "__main__":
    main()
