"""Full original-source released-label/event-count method receipt."""
import os
from pathlib import Path
from proof_of_work import load_reference
from population_contract import validate_output_directory


def test_source_bound_complete_results():
    reference = load_reference(os.environ.get('REPAIR_REFERENCE_PATH',str(Path(__file__).with_name('reference.npz'))))
    validate_output_directory(os.environ.get('OUTPUT_DIR','/app/output'),reference)
