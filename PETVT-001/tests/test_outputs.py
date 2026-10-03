"""One production source-bound test; no historical bank or authoring mutations."""
import hashlib
from pathlib import Path
import types

def test_source_bound_petvt_sensitivity():
    path=Path(__file__).resolve().with_name('grader_bootstrap.py')
    if path.is_symlink():raise ValueError('private bootstrap symlink')
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!='974e8bd41bcdabe44948ab906f4bcf512eb7968abbec08b4920791be346d74f3':
        raise ValueError('private bootstrap identity')
    module=types.ModuleType('petvt_private_bootstrap');module.__file__=str(path)
    exec(compile(raw,str(path),'exec'),module.__dict__)
    assert module.grade()=={'status':'ok','n_subjects':7,'n_records':28}
