"""Grade complete source-derived model comparisons, without scientific truth claims."""
import os
from pathlib import Path

import numpy as np
import pytest

import proof_of_work as q

OUTPUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))


@pytest.fixture(scope="module")
def reference():
    return q.load_reference()


@pytest.fixture(scope="module")
def entries(reference):
    q.require_files(OUTPUT)
    return q.read_parameter_table(OUTPUT, reference)


def test_complete_source_parameter_receipts(reference, entries):
    for model, entry in entries.items(): q.validate_entry(entry, reference, model)


def test_selected_model_support_and_fa_tables(reference, entries):
    result = q.load_json(OUTPUT/"results.json")
    main = result.get("main_model")
    assert main in entries, "main_model must be selected"
    common = np.logical_and.reduce([entry["eligible"] for entry in entries.values()])
    for entry in entries.values():
        assert np.array_equal(entry["common_valid"], common), "common support must use selected models"
    q.validate_fa_tables(OUTPUT, entries, main, reference)


def test_result_arithmetic_and_public_source_metadata(reference):
    q.validate_output_directory(OUTPUT, reference)
