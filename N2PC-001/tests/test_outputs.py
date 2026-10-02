"""Production: one independently authenticated reconstruction, no bank/cache bypass."""
import os
from pathlib import Path
import pytest
import source_reference
import proof_of_work


@pytest.fixture(scope='session')
def source_basis():
    return source_reference.reconstruct(Path(os.environ.get('SOURCE_DIR','/app/data/n2pc')),
                                        Path(os.environ.get('METHOD_CONTRACT','/app/method_contract.json')))


def test_source_bound_complete_output(source_basis):
    proof_of_work.validate(Path(os.environ.get('OUTPUT_DIR','/app/output')),source_basis)
