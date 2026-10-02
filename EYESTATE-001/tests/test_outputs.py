import os
import proof_of_work as p


def test_complete_original_source_and_held_out_analysis():
    p.validate_output_directory(os.environ.get('OUTPUT_DIR', '/app/output'))
