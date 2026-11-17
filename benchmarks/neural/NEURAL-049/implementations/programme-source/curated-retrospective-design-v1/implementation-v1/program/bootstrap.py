"""Authenticate a complete captured module graph without importing working files."""
import hashlib
import importlib.abc
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import time
import math


def load(root, manifest_path, expected, context):
    # Entrypoint itself must be authenticated by its external caller before this
    # function is invoked. This self-capture is an additional source join.
    root = Path(root)
    if type(context) is not dict or set(context) != {'origin','deadline','read_cap','read_reserved','read_observed','attempted_paths'}:
        raise ValueError('explicit inherited source accounting context')
    if type(context['read_cap']) is not int or context['read_cap'] <= 0 or context['read_reserved'] != 0 or context['read_observed'] != 0 or context['attempted_paths'] != []:
        raise ValueError('fresh prospective source budget')
    if any(type(context[k]) not in (int,float) or not math.isfinite(context[k]) for k in ('origin','deadline')):
        raise ValueError('finite original source clocks')
    def tick():
        now=time.monotonic()
        if not context['origin'] <= now < context['deadline']:
            raise ValueError('inherited source clock expired')
    def close(fd):
        primary=sys.exception()
        try: os.close(fd)
        except BaseException as error:
            if primary is not None: raise BaseExceptionGroup('source operation and close failed',[primary,error]) from None
            raise
    tick()
    def capture(path, length, digest):
        tick()
        if type(length) is not int or length < 0 or length > 2<<20:
            raise ValueError('source length ceiling')
        if context['read_reserved'] + length + 1 > context['read_cap']:
            raise ValueError('prospective source budget exhausted')
        context['read_reserved'] += length + 1
        context['attempted_paths'].append(str(path))
        text = str(path)
        if not text.startswith('/') or text.startswith('//') or '..' in path.parts or text != str(Path(text)):
            raise ValueError('noncanonical source path')
        for parent in reversed(path.parents):
            if not stat.S_ISDIR(os.lstat(parent).st_mode):
                raise ValueError('source parent not ordinary directory')
        fd = os.open(path, os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != length or length > 2<<20:
                raise ValueError('bounded exact source extent')
            body = bytearray()
            while len(body) < length:
                tick()
                block = os.read(fd, min(65536,length-len(body)))
                context['read_observed'] += len(block)
                if not block: raise ValueError('short source')
                body.extend(block)
            after = os.fstat(fd)
            fields = lambda s: (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
            extra=os.read(fd,1);context['read_observed'] += len(extra)
            if extra or fields(before)!=fields(after) or fields(after)!=fields(os.lstat(path)):
                raise ValueError('source changed')
            tick()
            raw = bytes(body)
            if hashlib.sha256(raw).hexdigest()!=digest: raise ValueError('source hash')
            return raw
        finally: close(fd)
    raw = capture(Path(manifest_path),expected['bytes'],expected['sha256'])
    def pairs(rows):
        d={}
        for k,v in rows:
            if k in d: raise ValueError('duplicate manifest key')
            d[k]=v
        return d
    manifest=json.loads(raw,object_pairs_hook=pairs)
    if manifest.get('schema')!='neural049_runtime_source_v1': raise ValueError('manifest schema')
    bodies={}; files={}; total=len(raw)
    for name,row in manifest['files'].items():
        parts=name.split('/')
        if not name or any(x in ('','.','..') for x in parts) or '\\' in name: raise ValueError('manifest relative path')
        total+=row['bytes']
        if total>16<<20: raise ValueError('source closure cap')
        body=capture(root/name,row['bytes'],row['sha256']);files[name]=body
        if name.endswith('.py') and not name.startswith('owner-helper-repairs-v1/'):
            module=name[:-3].replace('/','.')
            if module.endswith('.__init__'): module=module[:-9]
            bodies[module]=(body,str(root/name),name.endswith('/__init__.py'))
    expected_overrides={'preparation/prepare.py':'owner-helper-repairs-v1/preparation_prepare.py',
                        'references/r2/budget.py':'owner-helper-repairs-v1/r2_budget.py'}
    if manifest.get('overrides')!=expected_overrides:raise ValueError('exact selected source overlays')
    for logical,actual in expected_overrides.items():
        if logical not in files or actual not in files:raise ValueError('original and effective source captured')
        bodies[logical[:-3].replace('/','.')]=(files[actual],str(root/actual),False)
    # Host program imports use top-level names. Helpers remain namespaced.
    for name,row in tuple(bodies.items()):
        if name.startswith('program.'):
            short=name[len('program.'):]
            if '.' not in short: bodies[short]=row
    packages={'.'.join(k.split('.')[:i]) for k in bodies for i in range(1,len(k.split('.')))}
    class Captured(importlib.abc.MetaPathFinder,importlib.abc.Loader):
        def find_spec(self, fullname, path=None, target=None):
            if fullname in bodies or fullname in packages:
                return importlib.util.spec_from_loader(fullname,self,is_package=fullname in packages or bodies.get(fullname,(None,None,False))[2])
            return None
        def create_module(self,spec): return None
        def exec_module(self,module):
            tick()
            if module.__name__ in bodies:
                body,filename,package=bodies[module.__name__]
                module.__file__=filename
                code=compile(body,filename,'exec',dont_inherit=True)
                tick()
                exec(code,module.__dict__)
                tick()
    for name in bodies:
        if name in sys.modules and name not in ('__main__',):
            raise ValueError('captured module already loaded: '+name)
    tick()
    finder=Captured();sys.meta_path.insert(0,finder)
    tick()
    return {'manifest':manifest,'files':files,'finder':finder,'pin':expected,'logical_read_bytes':total,'source_accounting':dict(context)}
