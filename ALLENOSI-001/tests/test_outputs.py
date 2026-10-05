"""Complete source receipts and descriptive OSI arithmetic, not prevalence truth."""
import os
from pathlib import Path

import pytest

import proof_of_work as q

OUTPUT=Path(os.environ.get("OUTPUT_DIR","/app/output"))


@pytest.fixture(scope="module")
def reference(): return q.load_reference()


def test_original_presentation_identity_and_source_spike_counts(reference):
    q.require_files(OUTPUT)
    q.read_presentations(OUTPUT,reference)
    q.read_count_table(OUTPUT/"trial_responses.csv",reference,True)


def test_condition_means_and_every_visp_unit(reference):
    q.read_conditions(OUTPUT,reference,reference["primary"])
    q.read_units(OUTPUT,reference,reference["primary"])


def test_all_visp_summary_public_metadata_and_optional_qc(reference):
    q.validate_output_directory(OUTPUT,reference)
