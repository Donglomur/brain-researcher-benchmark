"""Lazy full-source reconstruction; manufactured tests never request it."""
import os
import pytest
import source_reference

@pytest.fixture(scope="session")
def original_reference():
    return source_reference.reconstruct(
        os.environ.get("DATA_DIR", "/app/data/taskfc"),
        os.environ.get("METHOD_CONTRACT", "/app/method_contract.json"),
        os.environ.get("OUTPUT_SCHEMA", "/app/output_schema.json"))
