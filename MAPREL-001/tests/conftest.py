"""Lazy source-once fixture shared by production and separately gated QA.

Private pins deliberately fail closed until parent installs frozen identities.
No source access occurs while importing or collecting manufactured tests.
"""
import os

import pytest


SOURCE_MANIFEST_SHA256 = '279658ffc93a8957287298471b539fc034fb7e11f0836325de322acc4b232f7f'
METHOD_CONTRACT_SHA256 = '54c6f851a5027b3e6b7cfe8e97e7b5af620d6f69b7235a681915affdcd23121e'
OUTPUT_SCHEMA_SHA256 = 'bfbd7239bff8015340bc562db4c95c51c6a3a2f529164ec4a97f2d8f45ac550e'


@pytest.fixture(scope="session")
def original_reference():
    pins = dict(source_manifest_sha256=SOURCE_MANIFEST_SHA256,
                method_contract_sha256=METHOD_CONTRACT_SHA256,
                output_schema_sha256=OUTPUT_SCHEMA_SHA256)
    assert all(isinstance(value, str) and len(value) == 64 for value in pins.values()), "Public identities not frozen."
    import source_reference
    data = os.environ.get("DATA_DIR", "/app/data/maprel")
    return source_reference.reconstruct(data,
        os.environ.get("SOURCE_MANIFEST", data+"/source_manifest.json"),
        os.environ.get("METHOD_CONTRACT", "/app/method_contract.json"),
        os.environ.get("OUTPUT_SCHEMA", "/app/output_schema.json"), pins)
