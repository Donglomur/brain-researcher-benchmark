"""One authenticated original reconstruction per session; no output cache."""
import os
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def original_reference():
    import source_reference
    private = Path(__file__).resolve().parent
    assert Path(source_reference.__file__).resolve().parent == private
    return source_reference.reconstruct(
        data_dir=os.environ.get("DATA_DIR", "/app/data/fcmatur"),
        method_path=os.environ.get("METHOD_CONTRACT", "/app/method_contract.json"),
        schema_path=os.environ.get("OUTPUT_SCHEMA", "/app/output_schema.json"),
        manifest_path=os.environ.get("SOURCE_MANIFEST", "/app/source_manifest.json"))
