"""Public one-selected-model computation, complete source receipt and summaries."""
import os
from pathlib import Path

import pytest

from proof_of_work import (load_reference, read_submission, require_files,
                           validate_summaries, validate_voxel_receipt)

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))


@pytest.fixture(scope="session")
def reference():
    return load_reference()


@pytest.fixture(scope="session")
def submission(reference):
    return read_submission(OUT, reference)


def test_required_outputs_and_findings():
    require_files(OUT)


def test_complete_source_roi_receipt(submission, reference):
    _, table = submission
    assert len(table["md"]) == len(reference["ijk"])


def test_selected_model_coefficients_and_recomputed_quantities(submission, reference):
    config, table = submission
    validate_voxel_receipt(table, reference, config)


def test_summaries_and_public_metadata(submission, reference):
    config, table = submission
    validate_summaries(OUT, table, reference, config)
