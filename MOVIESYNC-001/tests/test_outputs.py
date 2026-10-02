"""One binary source-bound production grade; original execution is separately gated."""
import os
from pathlib import Path
import proof_of_work as p
import source_reference as s


def test_source_bound_movie_isc():
    reference=s.reconstruct()
    result=p.validate_output_directory(Path(os.environ.get("OUTPUT_DIR","/app/output")),reference)
    assert result["n_subjects"]==40 and result["n_pairs"]==2340
