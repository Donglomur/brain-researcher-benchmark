"""Inspect declared local public source only; never import benchmark modules."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import stat

def inspect(root):
    index = root / 'PUBLIC_FILES.json'
    info = index.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > 262144:
        raise ValueError('Bounded ordinary inventory required')
    rows = json.loads(index.read_text(encoding='utf-8'))['files']
    if type(rows) is not list or not 1 <= len(rows) <= 256:
        raise ValueError('Bounded closed public roster required')
    seen = set()
    total = python_files = 0
    for row in rows:
        name = row['path']
        if type(name) is not str:
            raise ValueError('Relative string path required')
        path = Path(name)
        if path.is_absolute() or '..' in path.parts or str(path) != name or name in seen:
            raise ValueError('Unique normalized relative path required')
        seen.add(name)
        for i in range(1,len(path.parts)):
            if not stat.S_ISDIR((root / Path(*path.parts[:i])).lstat().st_mode):
                raise ValueError('Ordinary directory required')
        p = root / path
        st = p.lstat()
        if not stat.S_ISREG(st.st_mode) or st.st_size != row['bytes'] or st.st_size > 1048576:
            raise ValueError('Ordinary exact bounded source member required: '+name)
        total += st.st_size
        if total > 2097152:
            raise ValueError('Inspection allowance exceeded')
        body = p.read_bytes()
        if hashlib.sha256(body).hexdigest() != row['sha256']:
            raise ValueError('Source hash mismatch: '+name)
        text = body.decode('utf-8')
        if chr(0) in text:
            raise ValueError('NUL source text refused')
        if name.endswith('.py'):
            ast.parse(text,filename=name)
            python_files += 1
    return {'task':'NEURAL-066','source_integrity':True,'declared_files':len(rows)+1,
            'python_files_parsed':python_files,'runtime_qualified':False,
            'scientific_qualified':False,'submission_ready':False,'open_gates':24,
            'missing':['reviewed original operator policy','original inputs and loader',
                       'qualified immutable environment and receipts',
                       'complete resources/method admission','all scientific gates'],
            'benchmark_modules_imported':False,'scientific_or_native_work_executed':False}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-ready',action='store_true')
    args=parser.parse_args()
    print(json.dumps(inspect(Path(__file__).resolve().parent),sort_keys=True))
    return 2 if args.check_ready else 0

if __name__ == '__main__':
    raise SystemExit(main())
