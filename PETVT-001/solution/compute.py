"""Compatibility entrypoint for the source-bound two-assumption repair."""
import hashlib
from pathlib import Path
import types

def main():
    path=Path(__file__).resolve().with_name('compute_v2.py')
    if path.is_symlink():raise ValueError('oracle entry symlink')
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!='d1bd3b7a54339ffd5a1fff8244d67aee4fd5074a80970bbc434746b4104973c8':
        raise ValueError('oracle entry identity')
    module=types.ModuleType('petvt_oracle');module.__file__=str(path)
    exec(compile(raw,str(path),'exec'),module.__dict__)
    return module.main()

if __name__=='__main__':raise SystemExit(main())
