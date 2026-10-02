import pytest
import proof_of_work as proof


@pytest.fixture(scope="session")
def source_reference():
    """One authenticated immutable source basis, never cached output verdicts."""
    return proof.load_reference()
