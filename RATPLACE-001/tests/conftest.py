"""Full-QA bootstrap only; production uses the isolated retained entrypoint."""
import hashlib
from pathlib import Path
import types
import pytest

ROOT=Path(__file__).parent
raw=(ROOT/'entrypoint.py').read_bytes()
assert hashlib.sha256(raw).hexdigest()=='e913e178bc5cff1db611a535c0e3dca793a1cd1c28d341c1538e900434e99be0'
entry=types.ModuleType('_qa_entry');entry.__file__=str(ROOT/'entrypoint.py')
exec(compile(raw,entry.__file__,'exec'),entry.__dict__)
context=entry.load_entries(ROOT,{k:entry.ENTRY_PINS[k] for k in entry.GRADER_ORDER})

@pytest.fixture(scope='session')
def actual_context():
    guard=context['modules']['code_guard'];boot=context['modules']['grader_bootstrap']
    closure=guard.load_closure(ROOT,boot.MODULE_PINS,boot.DOCUMENT_PINS,boot.PUBLIC_PATHS)
    modules=closure['modules']
    reference=modules['source_reference'].reconstruct('/app/data/ratplace',ROOT)
    actual=modules['artifact_reader'].read_output('/app/output')
    modules['proof_v2'].verify(actual,reference)
    yield modules,reference,actual
    modules['artifact_reader'].recheck(actual);guard.recheck(closure)
