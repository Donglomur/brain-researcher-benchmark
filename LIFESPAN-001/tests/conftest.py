"""Trusted canonical reconstruction once per pytest session; no cached verdict."""
import os
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def source_reference():
    from source_reference import reconstruct
    return reconstruct(
        Path(os.environ.get("SOURCE_DIR", "/app/data/lifespan")),
        Path(os.environ.get("METHOD_CONTRACT", "/app/method_contract.json")),
        Path(os.environ.get("COHORT_MANIFEST", "/app/cohort_manifest.json")),
    )
