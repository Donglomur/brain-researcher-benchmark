"""Load measured epoch predictions for the declared Sleep-EDF LOSO recipe."""
import json
import math
import os
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
REF_PATH = Path(__file__).with_name("reference.npz")
PIPELINE_ID = "sleepedf-loso-v2"
SUBJECT_TOL = 1e-6
HEADLINE_TOL = 1e-5
CLASSES = ("W", "N1", "N2", "N3", "REM")


def number(value):
    assert not isinstance(value, (bool, np.bool_)), "finite numeric value required"
    value = float(value)
    assert math.isfinite(value), "finite numeric value required"
    return value


def integer(value):
    value = number(value)
    assert value >= 0 and value.is_integer(), "nonnegative integer required"
    return int(value)


def read_json(path):
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), f"{path.name} must contain a JSON object"
    return value


def match_contract(actual, expected, field="metadata"):
    """Require the public contract while permitting extra descriptive fields."""
    if isinstance(expected, dict):
        assert isinstance(actual, dict), f"{field} must be an object"
        for key, value in expected.items():
            assert key in actual, f"missing {field}.{key}"
            match_contract(actual[key], value, f"{field}.{key}")
    elif isinstance(expected, list):
        assert isinstance(actual, list) and len(actual) == len(expected), f"incorrect {field}"
        for index, value in enumerate(expected):
            match_contract(actual[index], value, f"{field}[{index}]")
    elif isinstance(expected, bool):
        assert actual is expected, f"incorrect {field}"
    elif isinstance(expected, (int, float)):
        assert abs(number(actual) - expected) <= 1e-12, f"incorrect {field}"
    else:
        assert actual == expected, f"incorrect {field}"


def load_reference():
    with np.load(REF_PATH, allow_pickle=False) as data:
        stats = json.loads(str(data["ref_stats"]))
        assert stats.get("pipeline_id") == PIPELINE_ID, "failed_precondition: stale sleep-staging reference"
        reference = {name: data["ref_" + name].copy() for name in
                     ("subject", "recording", "onset_sample", "true_class", "predicted_class")}
    reference["stats"] = stats
    count = integer(stats["n_epochs"])
    assert count > 0 and isinstance(stats["metadata_contract"], dict)
    hashes = stats["source_sha256"]
    assert isinstance(hashes, dict) and hashes, "reference input hashes are required"
    for digest in hashes.values():
        assert isinstance(digest, str) and len(digest) == 64 and set(digest) <= set("0123456789abcdef")
    for field in ("subject", "recording", "onset_sample", "true_class", "predicted_class"):
        assert reference[field].shape == (count,), f"invalid reference array: {field}"
    source = {}
    matrices = {str(subject): np.zeros((5, 5), dtype=np.int64) for subject in range(6)}
    for subject, recording, onset, truth, predicted in zip(
        reference["subject"], reference["recording"], reference["onset_sample"],
        reference["true_class"], reference["predicted_class"],
    ):
        subject, recording, onset = integer(subject), integer(recording), integer(onset)
        assert subject in range(6) and recording == 1
        assert truth in CLASSES and predicted in CLASSES
        key = (subject, recording, onset)
        assert key not in source, "duplicate source epoch in reference"
        source[key] = (str(truth), str(predicted))
        matrices[str(subject)][CLASSES.index(truth), CLASSES.index(predicted)] += 1
    from confusion_counts import metrics

    per_subject = stats["per_subject"]
    assert len(per_subject) == 6
    retained = {}
    for row in per_subject:
        subject = str(integer(row["subject"]))
        assert subject in matrices and subject not in retained
        retained[subject] = row
        n, accuracy, kappa = metrics(matrices[subject])
        assert integer(row["n_test_epochs"]) == n
        assert abs(number(row["accuracy"]) - accuracy) <= 1e-12
        assert abs(number(row["kappa"]) - kappa) <= 1e-12
    n, accuracy, kappa = metrics(sum(matrices.values()))
    assert n == count
    assert abs(number(stats["accuracy"]) - accuracy) <= 1e-12
    assert abs(number(stats["cohen_kappa"]) - kappa) <= 1e-12
    reference["source"] = source
    reference["matrices"] = matrices
    return reference
