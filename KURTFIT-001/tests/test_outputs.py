"""Check complete voxel maps and arithmetic for the public DKI shell-cap recipe."""
import pytest

from proof_of_work import OUT, load_reference, read_json, match_contract
from voxel_contract import validate_maps, validate_results


@pytest.fixture(scope="module")
def reference():
    return load_reference()


def test_primary_and_all_submitted_sweep_maps(reference):
    validate_maps(OUT, reference)


def test_reported_means_and_counts_recompute(reference):
    primary, groups = validate_maps(OUT, reference)
    validate_results(OUT, reference, primary, groups)


def test_public_source_and_estimator_metadata(reference):
    metadata = read_json(OUT / "run_metadata.json")
    match_contract(metadata, reference["stats"]["metadata_contract"])
    assert metadata["source_sha256"] == reference["stats"]["source_sha256"]


def test_findings_are_present():
    assert (OUT / "findings.md").read_text(encoding="utf-8").strip(), "findings.md is empty"
