"""Lazy once-session full original reconstruction; no collection-time source IO."""
import os
from pathlib import Path

import pytest

import grader_bootstrap


@pytest.fixture(scope='session')
def private_modules():
    assert Path(grader_bootstrap.__file__).absolute().parent == Path(__file__).absolute().parent
    return grader_bootstrap.load_private()


@pytest.fixture(scope='session')
def original_reference(private_modules):
    paths = dict(data_dir=os.environ.get('DATA_DIR', '/app/data/n170profile'),
                 manifest_path=os.environ.get('SOURCE_MANIFEST', '/app/source_manifest.json'),
                 method_path=os.environ.get('METHOD_CONTRACT', '/app/method_contract.json'),
                 schema_path=os.environ.get('OUTPUT_SCHEMA', '/app/output_schema.json'))
    documents = [paths[key] for key in ('manifest_path', 'method_path', 'schema_path')]
    grader_bootstrap.disjoint_output(os.environ.get('OUTPUT_DIR', '/app/output'),
                                    paths['data_dir'], documents, Path(__file__).absolute().parent)
    paths.update(grader_bootstrap.authenticated_documents(paths, private_modules['io_contract']))
    reference = private_modules['source_reference'].reconstruct(**paths)
    assert reference['status'] == 'complete'
    assert reference['subjects'] == list(private_modules['source_reference'].SUBJECTS)
    return reference
