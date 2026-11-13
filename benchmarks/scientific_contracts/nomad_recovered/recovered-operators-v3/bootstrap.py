"""Concrete captured-byte entry for the inactive recovered-operator component.

The eventual installed caller must bind this bootstrap's own bytes. This file
cannot retroactively attest its interpreter/initial exec image or OS custody.
It does authenticate and execute the entire selected descendant source capture.
"""
import argparse
import hashlib
import importlib.abc
import importlib.util
import json
import os
from pathlib import Path,PurePosixPath
import stat
import sys


def require(value,message):
    if not value:raise ValueError(message)


def decode(raw):
    def unique(rows):
        out={}
        for k,v in rows:
            require(k not in out,'duplicate metadata key');out[k]=v
        return out
    def invalid(v):raise ValueError('nonfinite metadata number')
    return json.loads(raw.decode('utf-8'),object_pairs_hook=unique,parse_constant=invalid)


def capture(path,cap,sha=None):
    p=Path(path).absolute();fd=None;primary=None;raw=None
    require(not any(x.is_symlink() for x in (p,*p.parents)),'ordinary source/request path')
    try:
        fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK);s=os.fstat(fd)
        require(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and s.st_size<=cap,'bounded ordinary source/request')
        pieces=[];n=0
        while n<=s.st_size:
            b=os.read(fd,min(65536,s.st_size+1-n))
            if not b:break
            n+=len(b);pieces.append(b)
        raw=b''.join(pieces);e=os.fstat(fd)
        stamp=lambda v:(v.st_dev,v.st_ino,v.st_size,v.st_mtime_ns,v.st_ctime_ns)
        require(stamp(s)==stamp(e) and len(raw)==s.st_size,'complete stable source/request bytes')
        if sha is not None:require(hashlib.sha256(raw).hexdigest()==sha,'independent exact selected digest')
    except BaseException as error:primary=error
    finally:
        if fd is not None:
            try:os.close(fd)
            except BaseException as error:
                if primary is None:primary=error
                else:setattr(primary,'source_close_secondary',type(error).__name__)
    if primary is not None:raise primary
    return raw


class CapturedModules(importlib.abc.MetaPathFinder,importlib.abc.Loader):
    def __init__(self,namespace,captured,root):
        self.namespace=namespace;self.captured=captured;self.root=root;self.owned=set()

    def _key(self,name):
        require(name==self.namespace or name.startswith(self.namespace+'.'),'owned module only')
        suffix=name[len(self.namespace):].lstrip('.').replace('.','/')
        base='source'+('/'+suffix if suffix else '')
        if base+'/__init__.py' in self.captured:return base+'/__init__.py',True
        require(base+'.py' in self.captured,'no live-file source fallback');return base+'.py',False

    def find_spec(self,fullname,path=None,target=None):
        if fullname!=self.namespace and not fullname.startswith(self.namespace+'.'):return None
        key,package=self._key(fullname)
        return importlib.util.spec_from_loader(fullname,self,origin=str(self.root/key),is_package=package)

    def create_module(self,spec):return None

    def exec_module(self,module):
        key,package=self._key(module.__name__);self.owned.add(module.__name__)
        module.__file__=str(self.root/key)
        if package:module.__path__=[]
        exec(compile(self.captured[key],module.__file__,'exec',dont_inherit=True),module.__dict__)

    def close(self):
        if self in sys.meta_path:sys.meta_path.remove(self)
        for name in sorted(self.owned,key=len,reverse=True):
            m=sys.modules.get(name)
            if m is not None and getattr(m,'__loader__',None) is self:sys.modules.pop(name,None)


def execute(root,manifest_path,manifest_sha,request_path,request_sha):
    root=Path(root).absolute();raw=capture(manifest_path,1048576,manifest_sha);reads=len(raw)
    manifest=decode(raw)
    require(type(manifest) is dict and set(manifest)=={'schema','files','source_data','scope'},'closed source manifest')
    require(manifest['schema']=='nomad_recovered_operator_runtime_v1','source manifest schema')
    files=manifest['files'];require(type(files) is dict and 0<len(files)<=256,'finite complete source roster')
    captured={};total=0
    for path,pin in files.items():
        pp=PurePosixPath(path)
        require(type(path) is str and str(pp)==path and not pp.is_absolute()
             and not set(pp.parts)&{'.','..'} and '\\' not in path,'canonical source member path')
        require(type(pin) is dict and set(pin)=={'bytes','sha256'} and type(pin['bytes']) is int
             and 0<=pin['bytes']<=1048576,'ordinary source member pin/cap')
        total+=pin['bytes'];require(total<=16777216,'complete source byte cap before member capture')
        value=capture(root/path,max(pin['bytes'],1),pin['sha256'])
        require(len(value)==pin['bytes'],'exact source member extent')
        captured[path]=value;reads+=len(value)
    require('source/__init__.py' in captured and 'source/nomad_entry.py' in captured,
         'actual production entry and package included')
    source_data={}
    for name,path in manifest['source_data'].items():
        require(type(name) is str and path in captured and path.startswith('source_data/'),
             'exact captured scientific metadata')
        source_data[name]=captured[path]
    request_raw=capture(request_path,1048576,request_sha);reads+=len(request_raw);request=decode(request_raw)
    namespace='_nomad_recovered_'+manifest_sha
    require(not any(n==namespace or n.startswith(namespace+'.') for n in sys.modules),
         'fresh captured-source module lifetime')
    loader=CapturedModules(namespace,captured,root);sys.meta_path.insert(0,loader)
    primary=None;result=None
    try:
        module=__import__(namespace+'.nomad_entry',fromlist=['run'])
        result=module.run(request,{'source_data':source_data,'bootstrap_read_bytes':reads,
            'source_manifest_pin':{'bytes':len(raw),'sha256':manifest_sha}})
    except BaseException as error:primary=error
    finally:
        try:loader.close()
        except BaseException as error:
            if primary is None:primary=error
            else:setattr(primary,'captured_module_close_secondary',type(error).__name__)
    if primary is not None:raise primary
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source-root',required=True);parser.add_argument('--manifest',required=True)
    parser.add_argument('--manifest-sha256',required=True);parser.add_argument('--request',required=True)
    parser.add_argument('--request-sha256',required=True);args=parser.parse_args()
    try:
        result=execute(args.source_root,args.manifest,args.manifest_sha256,args.request,args.request_sha256)
        raw=json.dumps(result,allow_nan=False,sort_keys=True)
        require(len(raw.encode())<=1048576,'finite ordinary result metadata')
        print(raw);return 0
    except BaseException as error:
        result={'schema':'nomad_recovered_bootstrap_failure_v1','type':type(error).__name__,
                'message':str(error),'prefix':getattr(error,'nomad_failure_prefix',None)}
        sys.stderr.write(json.dumps(result,allow_nan=False,sort_keys=True)+'\n');return 1


if __name__=='__main__':raise SystemExit(main())
