"""All people, original parcel pairs, graph recipes and source-bound summaries."""
import os
from pathlib import Path
from proof_of_work import load_reference,validate_output_directory

def test_complete_source_connectomes_graphs_and_rankings():
    validate_output_directory(Path(os.environ.get("OUTPUT_DIR","/app/output")),load_reference())
