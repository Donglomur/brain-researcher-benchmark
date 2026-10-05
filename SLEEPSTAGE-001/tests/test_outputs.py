"""Grade source-identified epochs and metrics for the public Sleep-EDF recipe."""
import pytest

from proof_of_work import OUT, load_reference, match_contract, read_json
from epoch_contract import validate_epochs, validate_metric_outputs


@pytest.fixture(scope="module")
def reference():
    return load_reference()


def test_epoch_identity_and_predictions(reference):
    validate_epochs(OUT / "epoch_predictions.csv", reference)


def test_complete_confusion_counts_and_metrics(reference):
    matrices = validate_epochs(OUT / "epoch_predictions.csv", reference)
    validate_metric_outputs(OUT, matrices)


def test_public_analysis_metadata(reference):
    metadata = read_json(OUT / "run_metadata.json")
    match_contract(metadata, reference["stats"]["metadata_contract"])
    assert metadata["source_sha256"] == reference["stats"]["source_sha256"], "source hashes differ"


def test_findings_are_present():
    assert (OUT / "findings.md").read_text(encoding="utf-8").strip(), "findings.md is empty"
