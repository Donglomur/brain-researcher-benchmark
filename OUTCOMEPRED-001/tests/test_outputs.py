import os
from pathlib import Path
from proof_of_work import load_reference
from prediction_contract import validate_output_directory

def test_complete_original_source_analysis():
    validate_output_directory(Path(os.environ.get('OUTPUT_DIR','/app/output')),load_reference())
