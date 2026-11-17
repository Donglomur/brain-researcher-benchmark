"""Literal-entry captured-source bootstrap. Trusted interpreter/literal entry remain external TCB."""
import argparse
import hashlib
import importlib.abc
import importlib.util
import json
import os
from pathlib import Path
import signal
import stat
import sys
import time
import types

REL='authoring/delivery-20261105/common/remaining-builds-wave20/neural-program-g/central-integration'
PARENT=REL.rsplit('/',1)[0]
REGISTRY='benchmarks/neuroscience/neural-007-whole-night-sleep-scoring/manifest.json'
BASE={'bytes':26686,'sha256':'b17b4317427f83ce28ab7ea5a4fbc42b689870ef2a7144a7e094ecb0bef9e59e'}
BOOTSTRAP_BOUND=256*1024*1024


def need(ok,message):
    if not ok: raise ValueError(message)


def pin(raw):
    return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


def parse(raw):
    def pairs(rows):
        result={}
        for k,v in rows:
            need(k not in result,'Duplicate bootstrap metadata key'); result[k]=v
        return result
    return json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_constant=lambda _:need(False,'Nonfinite metadata'))


class Reader:
    def __init__(self,end): self.end=end; self.used=0; self.external_upper_charge=0
    def read(self,p,expected=None,cap=1048576):
        p=Path(p); need(p.is_absolute() and '..' not in p.parts and not any(x.is_symlink() for x in (p,*p.parents)), 'Ordinary bootstrap source path')
        need(time.monotonic()<self.end and self.used+self.external_upper_charge+cap+1<=BOOTSTRAP_BOUND,'Startup full read reservation')
        fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            before=os.fstat(fd); need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and 0<before.st_size<=cap,'Bounded source metadata')
            if expected is not None: need(before.st_size==expected['bytes'],'Exact source extent')
            chunks=[]; total=0
            while total<=before.st_size:
                need(time.monotonic()<self.end,'Original bootstrap clock')
                raw=os.read(fd,min(65536,before.st_size+1-total)); self.used+=len(raw)
                if not raw: break
                chunks.append(raw); total+=len(raw)
            after,current=os.fstat(fd),p.lstat()
            fields=('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_nlink')
            need(total==before.st_size and all(getattr(before,k)==getattr(after,k)==getattr(current,k) for k in fields),'Stable compiled source capture')
            raw=b''.join(chunks); need(expected is None or pin(raw)==expected,'Exact captured source bytes'); return raw
        finally: os.close(fd)


def route_identity(doc,manifest_raw,freeze_raw,entry_raw):
    """Known metadata only: legacy passed finite qualification cannot get past this gate."""
    need(doc.get('id')=='NEURAL-007','Known Sleep registry')
    meta=doc.get('program_execution'); need(type(meta) is dict,'Known default programme')
    preferred={'path':REL,'source':{'path':REL+'/SOURCE_MANIFEST.json',**pin(manifest_raw)}}
    need(meta.get('preferred_source_interface')==preferred,'Exact new full preferred source interface required before review operand')
    entry=meta.get('entrypoint',{}); argv=entry.get('argv')
    need(type(argv) is list and len(argv)>=9 and argv[:5]==['python3','-I','-S','-B','-X']
         and argv[5].startswith('pycache_prefix=') and argv[6]==REL+'/entry.py'
         and entry.get('sha256')==pin(entry_raw)['sha256'] and entry.get('working_directory')=='.', 'Exact full captured wrapper before qualification')
    need(meta.get('source_freeze')=={'path':REL+'/QUALIFICATION_SOURCE.json','sha256':pin(freeze_raw)['sha256']}, 'Exact new qualification source freeze')
    frozen=parse(freeze_raw); manifest=parse(manifest_raw)
    need(type(frozen.get('files')) is dict and 0<len(frozen['files'])<=512
         and all(type(d.get('bytes')) is int and d['bytes']>=0 for d in frozen['files'].values())
         and sum(d['bytes'] for d in frozen['files'].values())<=32*1024*1024,
         'Bounded exact qualification-source closure supports conservative helper I/O charge')
    for name,desc in manifest['files'].items():
        need(frozen['files'].get(REL+'/'+name)==desc,'Every central runtime member in qualified source freeze')
    need(frozen['files'].get(REL+'/SOURCE_MANIFEST.json')==pin(manifest_raw),'Qualification includes exact runtime manifest')
    return meta


class Captured(importlib.abc.MetaPathFinder,importlib.abc.Loader):
    def __init__(self,namespace,root,files): self.namespace,self.root,self.files=namespace,Path(root),files
    def member(self,name):
        need(name==self.namespace or name.startswith(self.namespace+'.'),'Owned import namespace')
        suffix='' if name==self.namespace else name[len(self.namespace)+1:].replace('.','/')
        for item in ((suffix+'/__init__.py').lstrip('/'),suffix+'.py'):
            if item in self.files: return item
        raise ImportError('Uncaptured owned source: '+name)
    def find_spec(self,fullname,path=None,target=None):
        if fullname!=self.namespace and not fullname.startswith(self.namespace+'.'): return None
        member=self.member(fullname)
        return importlib.util.spec_from_loader(fullname,self,is_package=member.endswith('__init__.py'))
    def create_module(self,spec): return None
    def exec_module(self,module):
        member=self.member(module.__name__); module.__file__=str(self.root/member)
        if member.endswith('__init__.py'): module.__path__=[str((self.root/member).parent)]
        exec(compile(self.files[member],'<captured:'+self.namespace+':'+member+'>','exec'),module.__dict__)


def module(raw,path,name):
    value=types.ModuleType(name); value.__file__=str(path)
    exec(compile(raw,str(path),'exec'),value.__dict__); return value


def main():
    started=time.monotonic(); initial_end=started+120
    old_handler=signal.getsignal(signal.SIGALRM); old_timer=signal.getitimer(signal.ITIMER_REAL)
    def expired(*_): raise TimeoutError('Sleep central original startup/operation alarm')
    signal.signal(signal.SIGALRM,expired); signal.setitimer(signal.ITIMER_REAL,120)
    reader=Reader(initial_end)
    try:
        parser=argparse.ArgumentParser()
        for name in ('program','review','output','other-reserve-bytes'): parser.add_argument('--'+name,required=True)
        args=parser.parse_args()
        need(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,'Actual isolated no-site no-bytecode startup')
        root=Path.cwd(); here=root/REL
        need(Path(__file__).absolute()==here/'bootstrap.py','Literal known repository bootstrap')
        # Only known registry/source paths precede full-interface/runtime refusal.
        registry_raw=reader.read(root/REGISTRY,cap=131072); doc=parse(registry_raw)
        manifest_raw=reader.read(here/'SOURCE_MANIFEST.json'); manifest=parse(manifest_raw)
        freeze_raw=reader.read(here/'QUALIFICATION_SOURCE.json'); freeze=parse(freeze_raw)
        entry_raw=reader.read(here/'entry.py',manifest['files']['entry.py'])
        need(getattr(sys,'_sleep_central_bootstrap_pin',None)==manifest['files']['bootstrap.py'],'Literal entry captured this exact bootstrap')
        route_identity(doc,manifest_raw,freeze_raw,entry_raw)
        base=module(reader.read(root/'tools/neurobench_campaign.py',BASE),root/'tools/neurobench_campaign.py','_sleep_central_base')
        reader.external_upper_charge+=80*1024*1024
        need(base.verified_program_runtime(root/REGISTRY,doc,root),'Full programme has no independently qualified runtime; operation operands unopened')
        need(time.monotonic()<reader.end,'Startup qualification deadline')
        files={}
        for name,desc in manifest['files'].items():
            need(type(name) is str and not name.startswith('/') and all(x not in ('','.','..') for x in name.split('/')),'Confined runtime source member')
            files[name]=reader.read(here/name,desc)
        bindings=parse(files['DESIGN_BINDINGS.json'])
        parent_files={}; parent_bodies={}
        source_desc=bindings['parent_source_manifest']; parent_raw=reader.read(root/source_desc['path'],{k:source_desc[k] for k in ('bytes','sha256')})
        need(parse(parent_raw)==bindings['parent_source'],'Exact immutable parent source')
        parent_bodies['program/SOURCE_MANIFEST.json']=parent_raw
        for name,desc in bindings['parent_source']['files'].items():
            rel=PARENT+'/program/'+name; raw=reader.read(root/rel,desc)
            need(freeze['files'].get(rel)==desc,'Parent runtime in qualified source closure')
            parent_files[name]=raw; parent_bodies['program/'+name]=raw
        for name,desc in bindings['parent_source']['design'].items():
            rel=PARENT+'/design/'+name; raw=reader.read(root/rel,desc)
            need(freeze['files'].get(rel)==desc,'Parent design in qualified source closure'); parent_bodies['design/'+name]=raw
        launcher_desc=bindings['launcher']; parent_bodies['LAUNCHER.json']=reader.read(root/launcher_desc['path'],{k:launcher_desc[k] for k in ('bytes','sha256')})
        dependencies={}
        for rel,desc in bindings['dependencies'].items():
            # Historical caller/API snapshots are provenance only. The exact old
            # caller is retained locally; mutable sibling successors are not a runtime dependency.
            if 'neural-program-h/central-integration/' in rel:
                continue
            dependencies[rel]=reader.read(root/rel,desc)
            need(freeze['files'].get(rel)==desc,'Exact source helper dependency in qualification freeze')
        for namespace in ('_sleep_central','_sleep_parent'):
            need(not any(n==namespace or n.startswith(namespace+'.') for n in sys.modules),'No preloaded or shadow owned import')
        sys.meta_path.insert(0,Captured('_sleep_parent',root/PARENT/'program',parent_files))
        sys.meta_path.insert(0,Captured('_sleep_central',here,files))
        from _sleep_central.run import execute
        result=execute(args,root,doc,registry_raw,manifest_raw,freeze_raw,files,parent_bodies,dependencies,
            base,started,reader.used,reader.external_upper_charge)
        need(time.monotonic()<result['closeout_deadline'],'Central observer return before original closeout')
        print(json.dumps(result,sort_keys=True,separators=(',',':'),allow_nan=False))
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        signal.signal(signal.SIGALRM,old_handler)
        if old_timer[0]>0:
            remaining=old_timer[0]-(time.monotonic()-started)
            signal.setitimer(signal.ITIMER_REAL,max(.000001,remaining),old_timer[1])
            need(remaining>0,'Inherited alarm expired; no renewal')


if __name__=='__main__': main()
