"""Lazy source fixture: no source access at import or collection.

Manufactured tests do not request this fixture. Production and separately
gated actual-output controls share exactly one reconstruction per session.
"""
import pytest

import source_reference


@pytest.fixture(scope="session")
def original_reference():
    return source_reference.reconstruct()
