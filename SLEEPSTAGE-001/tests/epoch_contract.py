"""Bind epoch identity to retained real-source predictions and recompute metrics."""
import csv

import numpy as np

from confusion_counts import load_counts, metrics
from proof_of_work import CLASSES, SUBJECT_TOL, HEADLINE_TOL, integer, number, read_json


def validate_epochs(path, reference):
    expected = reference["source"]
    submitted = {}
    matrices = {str(subject): np.zeros((5, 5), dtype=np.int64) for subject in range(6)}
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        required = {"subject", "recording", "onset_sample", "true_class", "predicted_class", "heldout_subject"}
        assert required <= set(reader.fieldnames or ()), "missing epoch-prediction columns"
        for row in reader:
            subject = integer(row["subject"])
            key = (subject, integer(row["recording"]), integer(row["onset_sample"]))
            assert key in expected, "unknown source epoch"
            assert key not in submitted, "duplicate source epoch"
            assert integer(row["heldout_subject"]) == subject, "wrong held-out subject"
            truth, predicted = row["true_class"], row["predicted_class"]
            assert truth == expected[key][0], "wrong source sleep stage"
            assert predicted in CLASSES, "unknown predicted sleep stage"
            submitted[key] = (truth, predicted)
            matrices[str(subject)][CLASSES.index(truth), CLASSES.index(predicted)] += 1
    assert set(submitted) == set(expected), "every scored source epoch is required exactly once"
    assert submitted == expected, "source-indexed predictions differ from the pinned LOSO classifier"
    return matrices


def validate_metric_outputs(output, epoch_matrices):
    expected_subjects = set(epoch_matrices)
    submitted_counts = load_counts(output / "confusion_counts.csv", expected_subjects)
    for subject in expected_subjects:
        assert np.array_equal(submitted_counts[subject], epoch_matrices[subject]), (
            f"subject {subject} confusion cells do not recompute from epoch predictions")
    with (output / "per_subject.csv").open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        required = {"subject", "n_test_epochs", "accuracy", "kappa"}
        assert required <= set(reader.fieldnames or ()), "missing per-subject columns"
        submitted = {}
        for row in reader:
            subject = str(integer(row["subject"]))
            assert subject in expected_subjects and subject not in submitted, "duplicate/unknown subject"
            count, accuracy, kappa = metrics(epoch_matrices[subject])
            assert integer(row["n_test_epochs"]) == count, "source epoch count mismatch"
            assert abs(number(row["accuracy"]) - accuracy) <= SUBJECT_TOL, "subject accuracy mismatch"
            assert abs(number(row["kappa"]) - kappa) <= SUBJECT_TOL, "subject kappa mismatch"
            submitted[subject] = row
    assert set(submitted) == expected_subjects, "all held-out subjects are required"
    count, accuracy, kappa = metrics(sum(epoch_matrices.values()))
    result = read_json(output / "staging_results.json")
    assert result["cv_scheme"] == "leave-one-subject-out"
    assert integer(result["n_subjects"]) == 6 and integer(result["n_classes"]) == 5
    assert integer(result["n_epochs"]) == count
    assert abs(number(result["accuracy"]) - accuracy) <= HEADLINE_TOL, "pooled accuracy mismatch"
    assert abs(number(result["cohen_kappa"]) - kappa) <= HEADLINE_TOL, (
        "headline kappa must be computed from the pooled confusion matrix")
