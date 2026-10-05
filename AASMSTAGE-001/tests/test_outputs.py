"""Complete source-keyed Welch/LOSO evidence, not a performance or prose gate."""
from proof_of_work import OUT, load_reference, validate_output_directory


def test_complete_source_bound_output():
    validate_output_directory(OUT, load_reference())
