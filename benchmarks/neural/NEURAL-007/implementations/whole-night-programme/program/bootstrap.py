"""Captured-byte source bootstrap, entered by the exact literal launcher argv.

The external trusted Python/interpreter/argv and qualified dependency image are
explicit TCB. No benchmark module is imported before this closure is captured.
"""
import argparse
import hashlib
import importlib.abc
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import time


def need(value,message):
    if not value:raise ValueError(message)


def capture(path,expected,deadline,cap):
    path=Path(path);need(path.is_absolute() and not any(x.is_symlink() for x in (path,*path.parents)),'Ordinary source custody path')
    need(set(expected)=={'bytes','sha256'} and type(expected['bytes']) is int and 0<expected['bytes']<=cap,'Exact bounded source descriptor')
    need(time.monotonic()<deadline,'Original launch deadline')
    fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
    try:
        before=os.fstat(fd);need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size==expected['bytes'],'Ordinary exact source inode')
        parts=[];left=expected['bytes']+1
        while left:
            need(time.monotonic()<deadline,'Unrenewed capture clock');b=os.read(fd,min(left,65536))
            if not b:break
            parts.append(b);left-=len(b)
        body=b''.join(parts);after=os.fstat(fd)
        need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_nlink)==
             (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,1),'Stable captured source')
    finally:os.close(fd)
    need(len(body)==expected['bytes'] and hashlib.sha256(body).hexdigest()==expected['sha256'],'Exact compiled source bytes')
    return body


class Captured(importlib.abc.MetaPathFinder,importlib.abc.Loader):
    def __init__(self,root,files):self.root,self.files=root,files
    def find_spec(self,fullname,path=None,target=None):
        if fullname!='program' and not fullname.startswith('program.'):return None
        relative='' if fullname=='program' else fullname[len('program.'):].replace('.','/')
        candidates=[(relative+'/__init__.py').lstrip('/'),relative+'.py']
        for p in candidates:
            if p in self.files:return importlib.util.spec_from_loader(fullname,self,is_package=p.endswith('/__init__.py') or p=='__init__.py')
        raise ImportError('No uncaptured benchmark module: '+fullname)
    def create_module(self,spec):return None
    def exec_module(self,module):
        relative='' if module.__name__=='program' else module.__name__[len('program.'):].replace('.','/')
        names=[(relative+'/__init__.py').lstrip('/'),relative+'.py'];name=next(n for n in names if n in self.files)
        module.__file__=str(self.root/name)
        if name.endswith('__init__.py'):module.__path__=[str((self.root/name).parent)]
        exec(compile(self.files[name],'<captured:'+name+'>','exec'),module.__dict__)


def main():
    p=argparse.ArgumentParser();p.add_argument('--source-root',required=True);p.add_argument('--manifest-bytes',type=int,required=True)
    p.add_argument('--manifest-sha256',required=True);p.add_argument('--origin',type=float,required=True);p.add_argument('--deadline',type=float,required=True)
    p.add_argument('--dependency-root',action='append',default=[]);p.add_argument('command',nargs=argparse.REMAINDER)
    a=p.parse_args();now=time.monotonic();need(0<=a.origin<=now<a.deadline,'Original launch origin/cutoff')
    need(not any(n=='program' or n.startswith('program.') for n in sys.modules),'No already-imported/shadow benchmark modules')
    root=Path(a.source_root);expected={'bytes':a.manifest_bytes,'sha256':a.manifest_sha256}
    raw=capture(root/'SOURCE_MANIFEST.json',expected,a.deadline,1048576);manifest=json.loads(raw)
    need(manifest['schema']=='neural007_full153_source_v1','Complete programme source schema')
    need(getattr(sys,'_neural007_bootstrap_pin',None)==manifest['files']['bootstrap.py'] and getattr(sys,'_neural007_literal_deadline',None)==a.deadline,'Exact captured bootstrap and original literal-launch clock')
    launcher=json.loads(capture(root.parent/'LAUNCHER.json',manifest['launcher'],a.deadline,1048576))
    need(hashlib.sha256(launcher['literal_python'].encode()).hexdigest()==getattr(sys,'_neural007_literal_pin',None),'Exact selected literal launcher identity')
    total=sum(d['bytes'] for d in manifest['files'].values())+sum(d['bytes'] for d in manifest['design'].values())
    need(total<=16*1024**2,'Bounded whole source/design capture')
    files={}
    for name,descriptor in manifest['files'].items():
        q=PurePosixPath(name);need(not q.is_absolute() and '..' not in q.parts and str(q)==name,'Canonical captured source member')
        files[name]=capture(root/name,descriptor,a.deadline,1048576)
    for name,descriptor in manifest['design'].items():
        need(Path(name).name==name,'One exact design member');capture(root.parent/'design'/name,descriptor,a.deadline,1048576)
    for directory in a.dependency_root:
        q=Path(directory);need(q.is_absolute() and q.is_dir() and not any(p.is_symlink() for p in (q,*q.parents)),'Qualified explicit dependency root')
    # No .pth/site startup or arbitrary local-cwd import. Scientific libraries
    # must be supplied by a separately qualified dependency image/root inventory.
    sys.path.extend(a.dependency_root)
    sys.meta_path.insert(0,Captured(root,files));sys._neural007_captured_source=expected
    sys._neural007_launch_clock={'origin':a.origin,'deadline':a.deadline}
    sys._neural007_dependency_roots=list(a.dependency_root)
    sys.argv=['captured-neural007',*a.command]
    from program.cli import main as entry
    entry()


if __name__=='__main__':main()
