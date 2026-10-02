"""One binary full-source acceptance test; no shipped numerical answer bank."""
import os
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
import proof_of_work as p


def test_complete_source_bound_output():
    reference=p.load_reference()
    receipt=p.validate_output_directory(os.environ.get("OUTPUT_DIR","/app/output"),reference)
    assert receipt["participants"]==20 and receipt["rois"]==111 and receipt["fits"]==40
