"""Four independent groups for the public fixed-recipe numerical control."""
import os
from pathlib import Path

import pytest

from qsm_contract import (load_map, load_reference, require_files, validate_map,
                          validate_metadata, validate_roi_table)

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))


@pytest.fixture(scope="session")
def reference():
    return load_reference(Path(__file__).with_name("reference.npz"))


def test_required_outputs_and_nonempty_findings():
    require_files(OUT)


def test_complete_source_derived_map(reference):
    chi = load_map(OUT / "susceptibility_ppm.npy", reference)
    validate_map(chi, reference)


def test_all_six_source_roi_measurements(reference):
    chi = load_map(OUT / "susceptibility_ppm.npy", reference)
    validate_roi_table(OUT / "nuclei_susceptibility.csv", chi, reference)


def test_public_recipe_and_saved_map_metadata(reference):
    chi = load_map(OUT / "susceptibility_ppm.npy", reference)
    validate_metadata(OUT / "run_metadata.json", chi, reference)
