"""Authenticate every supplied runtime body before importing this task package."""
import hashlib
import importlib.abc
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys


def capture(path, maximum):
    p=Path(path)
    if not p.is_absolute() or any(x.is_symlink() for x in (p,*p.parents)):
        raise ValueError('literal captured source path required')
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        st=os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink!=1 or st.st_size>maximum:
            raise ValueError('bounded ordinary source required')
        body=bytearray()
        while len(body)<=maximum:
            part=os.read(fd,min(65536,maximum+1-len(body))); body.extend(part)
            if not part: break
        after=os.fstat(fd)
        if len(body)!=st.st_size or any(getattr(st,k)!=getattr(after,k) for k in
            ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_nlink')):
            raise ValueError('captured source changed during read')
        return bytes(body)
    finally: os.close(fd)


class Loader(importlib.abc.MetaPathFinder,importlib.abc.Loader):
    def __init__(self,root,raw,expected):
        if hashlib.sha256(raw).hexdigest()!=expected: raise ValueError('exact external package manifest')
        self.root=Path(root); self.bodies={}; self.mapping={}; self.bytes=len(raw)
        manifest=json.loads(raw)
        if manifest.get('schema')!='n059_complete_process_source_v1': raise ValueError('fixed source schema')
        for row in manifest['files']:
            rel=row['path']; p=Path(rel)
            if p.is_absolute() or '..' in p.parts or p.as_posix()!=rel or p.suffix!='.py':
                raise ValueError('closed Python source namespace')
            if rel in self.bodies: raise ValueError('duplicate source member')
            body=capture(self.root/rel,row['bytes']); self.bytes+=len(body)
            if len(body)!=row['bytes'] or hashlib.sha256(body).hexdigest()!=row['sha256']:
                raise ValueError('exact complete runtime source body')
            self.bodies[rel]=body
            if rel=='__init__.py': name='n059_owned'
            elif rel.endswith('/__init__.py'): name='n059_owned.'+rel[:-12].replace('/','.')
            else: name='n059_owned.'+rel[:-3].replace('/','.')
            self.mapping[name]=rel
        actual={p.relative_to(self.root).as_posix() for p in self.root.rglob('*.py')}
        if actual!=set(self.bodies): raise ValueError('no unselected Python source in capsule')
        if any(n=='n059_owned' or n.startswith('n059_owned.') for n in sys.modules):
            raise ValueError('no ambient task modules')

    def find_spec(self,fullname,path=None,target=None):
        if fullname in self.mapping:
            rel=self.mapping[fullname]
            return importlib.util.spec_from_loader(fullname,self,is_package=rel.endswith('__init__.py'))
        if fullname=='n059_owned' or fullname.startswith('n059_owned.'):
            raise ImportError('outside exact captured N059 source')
        return None

    def create_module(self,spec): return None

    def exec_module(self,module):
        rel=self.mapping[module.__name__]; module.__file__=str(self.root/rel)
        exec(compile(self.bodies[rel],module.__file__,'exec'),module.__dict__)


def install(root,expected):
    raw=capture(Path(root)/'SOURCE_MANIFEST.json',1048576)
    loader=Loader(root,raw,expected); sys.meta_path.insert(0,loader)
    return loader
