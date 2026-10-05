"""Small count fixtures test arithmetic/schema, not synthetic scientific cohorts."""
import csv
import importlib.util
from pathlib import Path
import sys
import numpy as np
import pytest

path = Path(__file__).resolve().parents[1] / "tests/confusion_counts.py"
sys.path.insert(0, str(path.parent))
spec = importlib.util.spec_from_file_location("sleep_count_contract", path)
counts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(counts)


@pytest.mark.parametrize("defect", [None, "equivalent_format", "duplicate", "missing", "negative", "fractional", "subject", "class", "nan"])
def test_count_schema(tmp_path, defect):
    rows = [{"subject": "0", "true_class": a, "predicted_class": b,
             "n_epochs": "2" if a == b else "1"} for a in counts.CLASSES for b in counts.CLASSES]
    if defect == "equivalent_format":
        rows.reverse()
        for row in rows:
            row["subject"] = "0.0"
            row["n_epochs"] += ".0"
            row["note"] = "harmless extra column"
    elif defect == "duplicate":
        rows.append(rows[0])
    elif defect == "missing":
        rows.pop()
    elif defect == "negative":
        rows[0]["n_epochs"] = "-1"
    elif defect == "fractional":
        rows[0]["n_epochs"] = "0.5"
    elif defect == "subject":
        rows[0]["subject"] = "6"
    elif defect == "class":
        rows[0]["true_class"] = "N4"
    elif defect == "nan":
        rows[0]["n_epochs"] = "nan"
    output = tmp_path / "counts.csv"
    with output.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)
    if defect not in (None, "equivalent_format"):
        with pytest.raises(AssertionError):
            counts.load_counts(output, ["0"])
    else:
        matrix = counts.load_counts(output, ["0"])["0"]
        n, accuracy, kappa = counts.metrics(matrix)
        assert n == 30 and accuracy == pytest.approx(1 / 3) and kappa == pytest.approx(1 / 6)


def test_pooled_kappa_is_not_subject_average():
    a, b = np.zeros((5, 5), dtype=int), np.zeros((5, 5), dtype=int)
    a[:2, :2] = [[80, 10], [5, 5]]
    b[:2, :2] = [[5, 5], [10, 80]]
    assert counts.metrics(a + b)[2] != pytest.approx((counts.metrics(a)[2] + counts.metrics(b)[2]) / 2)


def test_class_permutation_preserves_metrics_but_changes_cells():
    """The reason a count-only accuracy/kappa reference cannot establish labels."""
    matrix = np.zeros((5, 5), dtype=int)
    matrix[:3, :3] = [[80, 10, 2], [5, 9, 1], [2, 0, 10]]
    permutation = [1, 2, 3, 4, 0]
    changed = matrix[np.ix_(permutation, permutation)]
    assert not np.array_equal(changed, matrix)
    assert counts.metrics(changed) == pytest.approx(counts.metrics(matrix))
