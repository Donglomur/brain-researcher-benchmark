"""Complete N055 terminal entry. Capture original clocks before project imports."""
import time
ORIGINAL_MONOTONIC=time.monotonic()
ORIGINAL_CPU=time.process_time()
import argparse
import hashlib
import json
import os
import stat
from pathlib import Path
import sys

def note_cleanup(first,message):
    """Best-effort annotation; raw cleanup failures remain authoritative on Python3.9+."""
    try:
        annotate=getattr(first,'add_note',None)
        if annotate is not None:
            annotate(message)
    except BaseException as secondary:
        # Annotation failure must not replace the already retained body error.
        first.__dict__.setdefault('cleanup_failures',[]).append(secondary)

def strict_pairs(rows):
    result={}
    for k,v in rows:
        if k in result:raise ValueError('duplicate source/plan key')
        result[k]=v
    return result

def read_pin(path,n,digest,cap):
    p=Path(path)
    if not p.is_absolute() or any(x.is_symlink() for x in (p,*p.parents)):raise ValueError('canonical unlinked bootstrap source')
    s=p.lstat()
    if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1 or s.st_size!=n or not 0<n<=cap:raise ValueError('bounded exact bootstrap source')
    def identity(value):return (value.st_dev,value.st_ino,value.st_mode,value.st_nlink,value.st_size,value.st_mtime_ns,value.st_ctime_ns)
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
    first=None
    try:
        if identity(os.fstat(fd))!=identity(s):raise ValueError('same original bootstrap handle')
        parts=[];size=0
        while size<=n:
            chunk=os.read(fd,min(65536,n+1-size))
            if not chunk:break
            parts.append(chunk);size+=len(chunk)
        raw=b''.join(parts)
        if identity(os.fstat(fd))!=identity(s):raise ValueError('stable original bootstrap handle')
    except BaseException as error:
        first=error;raise
    finally:
        try:os.close(fd)
        except BaseException as secondary:
            if first is None:raise
            first.__dict__.setdefault('cleanup_failures',[]).append(secondary)
            note_cleanup(first,'Bootstrap source close also failed: '+type(secondary).__name__)
    if len(raw)!=n or hashlib.sha256(raw).hexdigest()!=digest or identity(p.lstat())!=identity(s):raise ValueError('stable complete bootstrap source')
    return raw

def execute_captured(root,captured,args,descriptor,plan,initial):
    """Load only captured runtime bytes and close its namespace on every exit."""
    import importlib.abc
    import importlib.util
    if any(n=='n055' or n.startswith('n055.') for n in sys.modules):
        raise ValueError('fresh exact runtime package namespace required')
    class CapturedRuntime(importlib.abc.MetaPathFinder,importlib.abc.Loader):
        def find_spec(self,fullname,path=None,target=None):
            if fullname!='n055' and not fullname.startswith('n055.'):
                return None
            package=fullname=='n055'
            name='n055/__init__.py' if package else fullname.replace('.','/')+'.py'
            if name not in captured:raise ImportError('unmanifested runtime dependency: '+fullname)
            return importlib.util.spec_from_loader(fullname,self,is_package=package)
        def create_module(self,spec):return None
        def exec_module(self,module):
            name='n055/__init__.py' if module.__name__=='n055' else module.__name__.replace('.','/')+'.py'
            module.__file__=str(root/name)
            if module.__name__=='n055':module.__path__=[]
            exec(compile(captured[name],module.__file__,'exec'),module.__dict__)
    loader=CapturedRuntime();sys.meta_path.insert(0,loader);first=None
    try:
        from n055.central import execute
        return execute(args.mode,plan,args.operator_root,root,descriptor,args.output,
                       ORIGINAL_MONOTONIC,ORIGINAL_CPU,bootstrap_read_bytes=initial)
    except BaseException as error:
        first=error;raise
    finally:
        failures=[]
        try:sys.meta_path.remove(loader)
        except BaseException as secondary:failures.append(secondary)
        for name in tuple(sys.modules):
            if name=='n055' or name.startswith('n055.'):
                try:sys.modules.pop(name,None)
                except BaseException as secondary:failures.append(secondary)
        if failures:
            if first is None:
                first=failures[0]
                for secondary in failures[1:]:
                    first.__dict__.setdefault('cleanup_failures',[]).append(secondary)
                raise first
            first.__dict__.setdefault('cleanup_failures',[]).extend(failures)
            note_cleanup(first,'Captured runtime cleanup also failed; original failure retained.')

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['inspect','prepare','prepare-features','run'],nargs='?',default='inspect')
    parser.add_argument('--source-root',required=True);parser.add_argument('--source-manifest',required=True)
    parser.add_argument('--manifest-bytes',type=int,required=True);parser.add_argument('--manifest-sha256',required=True)
    parser.add_argument('--plan',required=True);parser.add_argument('--plan-bytes',type=int,required=True);parser.add_argument('--plan-sha256',required=True)
    parser.add_argument('--operator-root',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args(argv)
    root=Path(args.source_root);manifest=Path(args.source_manifest)
    if not manifest.is_relative_to(root):raise ValueError('source manifest within exact root')
    manifest_raw=read_pin(manifest,args.manifest_bytes,args.manifest_sha256,1048576)
    source=json.loads(manifest_raw,object_pairs_hook=strict_pairs)
    if set(source)!= {'schema','files'} or source['schema']!='neural055-complete-runtime-source-v1':raise ValueError('complete ordinary runtime manifest')
    seen=set();captured={}
    for d in source['files']:
        if set(d)!={'path','bytes','sha256','mode','role'}:raise ValueError('closed source descriptor')
        rel=Path(d['path'])
        if rel.is_absolute() or '..' in rel.parts or str(rel)!=d['path'] or d['path'] in seen:raise ValueError('canonical unique source path')
        seen.add(d['path'])
        if d['role'] not in ('runtime_source','legacy_source','source_contract','public_instructions'):raise ValueError('ordinary code only before import')
        captured[d['path']]=read_pin(root/rel,d['bytes'],d['sha256'],16777216)
    if 'central_entry.py' not in seen or Path(__file__).resolve()!=root/'central_entry.py':raise ValueError('executed exact selected bootstrap')
    raw=read_pin(Path(args.plan),args.plan_bytes,args.plan_sha256,16777216)
    plan=json.loads(raw,object_pairs_hook=strict_pairs,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('nonfinite JSON')))
    descriptor={'path':str(manifest.relative_to(root)),'bytes':len(manifest_raw),'sha256':hashlib.sha256(manifest_raw).hexdigest(),
                'mode':oct(stat.S_IMODE(manifest.stat().st_mode)),'role':'complete_runtime_manifest'}
    # Admit the complete original bootstrap debit before loading project code.
    initial=len(manifest_raw)+len(raw)+sum(d['bytes'] for d in source['files'])
    if initial>plan['limits']['read_bytes']:raise ValueError('original bootstrap exceeds selected read budget')
    result=execute_captured(root,captured,args,descriptor,plan,initial)
    print(json.dumps({'status':result['status'],'mode':args.mode,'terminal':str(Path(args.output)/'TERMINAL.json')},sort_keys=True))
    return 0

if __name__=='__main__':raise SystemExit(main())

