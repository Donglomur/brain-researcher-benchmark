"""One authenticated full-cohort reconstruction per pytest session.

Path overrides select byte-authenticated inputs, never authority hashes or a
source-skip mode. Actual-output authoring tests reuse this fixture explicitly.
"""
import os
from pathlib import Path

import pytest


def disjoint_output(output, data_dir, documents, private_dir):
    import artifact_reader as io
    out = io.guarded_path(output,directory=True)
    roots = [io.guarded_path(data_dir,directory=True),io.guarded_path(private_dir,directory=True)]
    for protected in roots:
        io.require(out != protected and out not in protected.parents and protected not in out.parents,
                   "output overlaps source/private code")
    for document in documents:
        path = io.guarded_path(document)
        io.require(out != path and out not in path.parents, "output contains protected public input")
    return out


@pytest.fixture(scope="session")
def original_reference():
    import artifact_reader
    import source_reference
    private = Path(__file__).resolve().parent
    for module in (artifact_reader,source_reference):
        assert Path(module.__file__).resolve().parent == private, "untrusted private import path"
    paths = dict(data_dir=os.environ.get("DATA_DIR","/app/data/fcstab"),
                 method_path=os.environ.get("METHOD_CONTRACT","/app/method_contract.json"),
                 schema_path=os.environ.get("OUTPUT_SCHEMA","/app/output_schema.json"),
                 manifest_path=os.environ.get("SOURCE_MANIFEST","/app/source_manifest.json"),
                 subject_ids_path=os.environ.get("SUBJECT_IDS","/app/subject_ids.txt"))
    output = os.environ.get("OUTPUT_DIR","/app/output")
    documents = [paths[key] for key in ("method_path","schema_path","manifest_path","subject_ids_path")]
    disjoint_output(output,paths["data_dir"],documents,private)
    authored = os.environ.get("REPAIR_ORACLE_OUTPUT")
    if authored is not None: disjoint_output(authored,paths["data_dir"],documents,private)
    reference = source_reference.reconstruct(**paths)
    assert reference["status"] == "complete" and len(reference["subject_ids"]) == 40
    return reference
