import os
import proof_of_work as p


def test_complete_source_bound_analysis():
    p.validate_output_directory(os.environ.get('OUTPUT_DIR', '/app/output'))
