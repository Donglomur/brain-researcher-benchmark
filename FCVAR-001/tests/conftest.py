"""One independently authenticated original reference per pytest session.

Manufactured tests never request this fixture. No import-time source read;
there is no original output/acceptance cache and no historical bank dependency.
"""
import os
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def original_reference():
    import source_reference
    private = Path(__file__).resolve().parent
    assert Path(source_reference.__file__).resolve().parent == private, "grader-owned private source reconstruction required"
    return source_reference.reconstruct(
        data_dir=os.environ.get("DATA_DIR", "/app/data/fcvar"),
        method_path=os.environ.get("METHOD_CONTRACT", "/app/method_contract.json"),
        schema_path=os.environ.get("OUTPUT_SCHEMA", "/app/output_schema.json"))
