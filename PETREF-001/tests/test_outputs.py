"""Verify the full fixed-source SRTM fit, not an expected-looking binding band."""
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from proof_of_work import OUT, load_reference, load_estimates, load_tac_fit, read_json
from srtm_contract import validate_frames, validate_estimates, validate_results, validate_metadata


@pytest.fixture(scope="module")
def reference(): return load_reference()


@pytest.fixture(scope="module")
def frames(reference): return validate_frames(load_tac_fit(OUT / "tac_fit.csv"), reference)


@pytest.fixture(scope="module")
def estimates(frames, reference): return validate_estimates(load_estimates(OUT / "bp_estimates.csv"), frames, reference)


def test_complete_source_bound_timing_and_tac_inputs(frames):
    assert len(frames["target"]) > 0


def test_parameters_reconstruct_predictions_residuals_and_qc(estimates):
    assert len(estimates) == 4


def test_test_retest_pairs_and_group_arithmetic(estimates):
    validate_results(read_json(OUT / "pet_results.json"), estimates)


def test_public_metadata_and_nonempty_findings(reference):
    validate_metadata(read_json(OUT / "run_metadata.json"), reference)
    assert (OUT / "findings.md").read_text(encoding="utf-8").strip()
