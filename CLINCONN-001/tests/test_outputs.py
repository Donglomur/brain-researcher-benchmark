"""Complete source-bound method-control outputs; no scientific-direction gate."""
import os
from pathlib import Path
import connectivity_contract as contract
import proof_of_work


def test_complete_original_source_analysis():
    reference = proof_of_work.load_reference(Path(__file__).with_name('reference.npz'))
    contract.validate_output_directory(os.environ.get('OUTPUT_DIR', '/app/output'), reference)
