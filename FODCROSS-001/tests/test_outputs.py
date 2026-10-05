"""Pinned paper-derived estimator comparison, not biological crossing ground truth."""
import pytest

from peak_contract import primary_choice, validate_maps, validate_metadata, validate_results
from proof_of_work import OUT, load_maps, load_reference, read_json


@pytest.fixture(scope="module")
def reference():
    return load_reference()


@pytest.fixture(scope="module")
def outputs():
    report = read_json(OUT / "crossing.json")
    primary = load_maps(OUT / "peaks_voxelwise.csv")
    groups = load_maps(OUT / "peaks_sweep.csv", sweep=True)
    return report, primary, groups


def test_every_map_matches_its_declared_public_recipe(reference, outputs):
    report, primary, groups = outputs
    validate_maps(primary, groups, reference, primary_choice(report, groups))


def test_all_summaries_recompute(reference, outputs):
    report, primary, groups = outputs
    values, arrays = validate_maps(primary, groups, reference, primary_choice(report, groups))
    validate_results(report, values, arrays)


def test_source_and_public_recipe_metadata(reference, outputs):
    report, _, groups = outputs
    metadata = read_json(OUT / "run_metadata.json")
    validate_metadata(metadata, reference, primary_choice(report, groups), groups)


def test_findings_present():
    assert (OUT / "findings.md").read_text(encoding="utf-8").strip(), "findings.md must be nonempty"
