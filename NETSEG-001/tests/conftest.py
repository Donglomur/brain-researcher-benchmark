"""One authenticated source reconstruction per pytest session, no verdict cache."""
import pytest
import proof_of_work as p


@pytest.fixture(scope="session")
def source_reference():
    return p.load_reference()
