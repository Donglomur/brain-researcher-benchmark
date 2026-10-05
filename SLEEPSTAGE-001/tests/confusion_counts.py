"""Recompute LOSO outcome metrics from public nonnegative integer counts."""
import csv

import numpy as np

from proof_of_work import CLASSES, integer


def load_counts(path, subject_ids):
    matrices = {str(integer(subject)): np.zeros((5, 5), dtype=np.int64) for subject in subject_ids}
    seen = set()
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        required = {"subject", "true_class", "predicted_class", "n_epochs"}
        assert required <= set(reader.fieldnames or ()), "missing confusion-count columns"
        for row in reader:
            subject = str(integer(row["subject"]))
            assert subject in matrices, "unknown held-out subject"
            truth, predicted = row["true_class"], row["predicted_class"]
            assert truth in CLASSES and predicted in CLASSES, "unknown class"
            key = (subject, truth, predicted)
            assert key not in seen, "duplicate confusion-count cell"
            seen.add(key)
            count = integer(row["n_epochs"])
            assert count <= np.iinfo(np.int64).max, "epoch count overflows the count table"
            matrices[subject][CLASSES.index(truth), CLASSES.index(predicted)] = count
    assert len(seen) == 25 * len(matrices), "require all 25 cells, including zeros, for every subject"
    return matrices


def metrics(matrix):
    matrix = np.asarray(matrix)
    assert matrix.shape == (5, 5) and np.isfinite(matrix).all()
    assert (matrix >= 0).all() and (matrix == np.floor(matrix)).all(), "invalid outcome counts"
    count = sum(int(value) for value in matrix.flat)
    assert count > 0, "no scored epochs"
    accuracy = sum(int(matrix[index, index]) for index in range(5)) / count
    proportions = matrix.astype(float) / count
    chance_agreement = float(np.dot(proportions.sum(axis=0), proportions.sum(axis=1)))
    assert chance_agreement < 1, "kappa is undefined for degenerate marginals"
    return count, accuracy, (accuracy - chance_agreement) / (1 - chance_agreement)
