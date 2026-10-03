"""One production source-bound test; no historical bank or authoring mutations."""
import hashlib
from pathlib import Path
import types

def test_source_bound_petvt_sensitivity():
    path=Path(__file__).resolve().with_name('grader_bootstrap.py')
    if path.is_symlink():raise ValueError('private bootstrap symlink')
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!='557e431e4ea5774b76ac632acdcf57d652fc3381ba08b9b6b31468b2cd589bdd':
        raise ValueError('private bootstrap identity')
    module=types.ModuleType('petvt_private_bootstrap');module.__file__=str(path)
    exec(compile(raw,str(path),'exec'),module.__dict__)
    assert module.grade()=={'status':'ok','n_subjects':7,'n_records':28}
