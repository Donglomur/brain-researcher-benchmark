import os
from pathlib import Path
from proof_of_work import validate_output_directory

def test_complete_source_bound_analysis():
    validate_output_directory(Path(os.environ.get('OUTPUT_DIR', '/app/output')))
