"""Public IVIM recipe reproduction and paired QC, not perfusion truth."""
import pytest

from proof_of_work import OUT, load_reference, load_parameters, load_f_map, read_json
from ivim_contract import (primary_choice, validate_parameters, validate_f_maps,
                           validate_results, validate_metadata, validate_source_summary)


@pytest.fixture(scope="module")
def reference():
    return load_reference()


@pytest.fixture(scope="module")
def parameters():
    return load_parameters(OUT / "parameters_voxelwise.csv")


def test_source_bound_parameters_and_fit_status(reference, parameters):
    validate_parameters(parameters, reference)


def test_primary_and_sweep_link_to_parameters(reference, parameters):
    selected = primary_choice(read_json(OUT / "ivim_results.json"))
    validate_f_maps(load_f_map(OUT / "f_voxelwise.csv"), load_f_map(OUT / "f_sweep.csv", sweep=True),
                    parameters, reference, selected)


def test_own_valid_and_paired_common_valid_summaries(reference, parameters):
    arrays, common = validate_parameters(parameters, reference)
    result = read_json(OUT / "ivim_results.json")
    validate_results(result, arrays, common)
    validate_source_summary(result, reference)


def test_public_metadata_and_findings(reference):
    result = read_json(OUT / "ivim_results.json")
    validate_metadata(read_json(OUT / "run_metadata.json"), reference, primary_choice(result))
    assert (OUT / "findings.md").read_text(encoding="utf-8").strip(), "nonempty findings required"
