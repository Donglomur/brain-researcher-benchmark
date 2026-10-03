"""Same-buffer private code/document authority; no public Python imports."""
import hashlib
import os
from pathlib import Path
import re
import stat
import sys
import types

CODE_PINS={
    'artifact_reader':'6b26c0fbd252b811fd36434debd46aca7a5e9fa3b615cedd1ed7bf3213f35a9e',
    'reference_math':'6841ccc60e3dfc7fef453b75459956f1888e012f157ffaa7fe4486305e260edb',
    'source_reference':'f37ef45967fa2f47e557772f71d282e76c142b960a039fa3b4c08bfb5fa65de7',
    'proof_of_work':'f31769805f037a8498a0f2e6343e2da4a0ab4cc68c70dd5ed6b8d585f897bd89'}
DOC_PINS={'source_manifest.json':'2e45467d3ef720a686b13a16ac33288369e3685044d243a5fe55128910adcfc8',
    'method_contract.json':'260a010f65be9a850b3ff46eaed0f5c7ec9b76c2d48cddbbd15e6636eecb8178',
    'output_schema.json':'23f68ffbbaefb40081fe9d33e1f020af85c69f0cec88d5216394766f267a97d0'}


def read_pinned(path,pin,cap):
    if type(pin)is not str or not re.fullmatch('[0-9a-f]{64}',pin):raise ValueError('unfrozen private pin')
    path=Path(path)
    if any(p.is_symlink()for p in (path,*path.parents)):raise ValueError('authority symlink')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd)
        if not stat.S_ISREG(before.st_mode)or not 0<before.st_size<=cap:raise ValueError('authority file bound')
        with os.fdopen(fd,'rb',closefd=False)as stream:raw=stream.read(cap+1)
        sig=lambda s:(s.st_dev,s.st_ino,s.st_mode,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        if len(raw)!=before.st_size or sig(before)!=sig(os.fstat(fd))or sig(before)!=sig(path.lstat()):raise ValueError('authority changed')
        if hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('authority hash mismatch')
        return raw
    finally:os.close(fd)


def load_private(private_root=None,public_root='/app'):
    private=Path(__file__).resolve().parent if private_root is None else Path(private_root)
    codes={name:read_pinned(private/(name+'.py'),pin,262144)for name,pin in CODE_PINS.items()}
    documents={name:read_pinned(private/name,pin,1048576)for name,pin in DOC_PINS.items()}
    for name,pin in DOC_PINS.items():
        if read_pinned(Path(public_root)/name,pin,1048576)!=documents[name]:raise ValueError('public document changed')
    modules={}
    for name,raw in codes.items():
        module=types.ModuleType(name);module.__file__=str(private/(name+'.py'));sys.modules[name]=module
        exec(compile(raw,module.__file__,'exec'),module.__dict__);modules[name]=module
    return dict(modules=modules,private_dir=private,documents={name:private/name for name in DOC_PINS})


def grade(output='/app/output',data='/app/data/petvt'):
    private=Path(__file__).resolve().parent;out=Path(output).resolve();source=Path(data).resolve()
    for protected in (private,source,*(Path('/app')/n for n in DOC_PINS)):
        if out==protected or out in protected.parents or protected in out.parents:raise ValueError('output/source/authority overlap')
    context=load_private();docs=context['documents'];modules=context['modules']
    reference=modules['source_reference'].reconstruct(source,docs['source_manifest.json'],docs['method_contract.json'],docs['output_schema.json'])
    return modules['proof_of_work'].validate(out,reference)
