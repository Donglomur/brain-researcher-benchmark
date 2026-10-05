"""Full frozen-source receipts, matrix arithmetic, missingness and tied maxima."""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from proof_of_work import OUT, load_reference, load_experiment_targets, load_matrix, load_support, load_strongest, read_json
from matrix_contract import (validate_experiment_targets, validate_matrix, validate_strongest,
                              validate_results, validate_metadata)


@pytest.fixture(scope="module")
def reference():
    return load_reference()


@pytest.fixture(scope="module")
def receipts(reference):
    return validate_experiment_targets(load_experiment_targets(OUT / "experiment_targets.csv"), reference)


@pytest.fixture(scope="module")
def matrix(receipts, reference):
    return validate_matrix(load_matrix(OUT / "connectivity_matrix.csv", reference["target_ids"]),
                           load_support(OUT / "matrix_support.csv"), receipts, reference)


@pytest.fixture(scope="module")
def descriptors(matrix, reference):
    return validate_strongest(load_strongest(OUT / "source_strongest.csv"), *matrix, reference)


def test_entire_experiment_target_receipt_matches_frozen_source(receipts):
    assert receipts


def test_matrix_is_available_case_equal_experiment_mean(matrix):
    assert matrix[0].size > 0


def test_full_target_ties_and_eligible_source_denominator(descriptors, receipts, reference):
    validate_results(read_json(OUT / "self_projection.json"), descriptors, receipts, reference)


def test_public_metadata_and_nonempty_findings(descriptors, receipts, reference):
    expected = validate_results(read_json(OUT / "self_projection.json"), descriptors, receipts, reference)
    validate_metadata(read_json(OUT / "run_metadata.json"), expected, reference)
    assert (OUT / "findings.md").read_text(encoding="utf-8").strip()
