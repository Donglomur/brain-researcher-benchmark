"""Bounded primitive I/O. No pickle, arbitrary classes or path-selected code."""
import ast
import hashlib
import io
import json
import math
import os
from pathlib import Path
import stat
import struct
from .budget import Failure
from .contract import canonical

DTYPES={'float64':('<f8',8),'float32':('<f4',4),'bool':('|b1',1),'int64':('<i8',8)}


def path_admit(value,roots=None):
    if type(value) is not str or not value.startswith('/') or value.startswith('//'):
        raise ValueError('canonical absolute path required')
    path=Path(value)
    if str(path)!=value or '..' in path.parts or '.' in path.parts:
        raise ValueError('noncanonical path')
    if roots is not None and not any(path!=r and r in path.parents for r in roots):
        raise ValueError('outside admitted input roots')
    for item in reversed((path,)+tuple(path.parents)):
        try: s=item.lstat()
        except FileNotFoundError:
            if item==path: continue
            raise
        if stat.S_ISLNK(s.st_mode): raise ValueError('symlink path component')
    return path


def pin_admit(pin):
    if type(pin) is not dict or set(pin)!={'bytes','sha256'} or type(pin['bytes']) is not int or pin['bytes']<0:
        raise ValueError('body pin')
    h=pin['sha256']
    if type(h) is not str or len(h)!=64 or any(c not in '0123456789abcdef' for c in h): raise ValueError('sha256 pin')
    return pin


def stamp(s):
    return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_nlink)


def metadata_upper(value,depth=0):
    if depth>40: raise ValueError('metadata nesting')
    if value is None or type(value) is bool: return 8
    if type(value) is int: return max(32,(value.bit_length()+2)//3+2)
    if type(value) is float:
        if not math.isfinite(value): raise ValueError('nonfinite metadata')
        return 32
    if type(value) is str: return 12*len(value)+2
    if type(value) in (list,tuple): return 2+sum(metadata_upper(x,depth+1)+1 for x in value)
    if type(value) is dict:
        if any(type(k) is not str for k in value): raise ValueError('nonstring metadata key')
        return 2+sum(metadata_upper(k,depth+1)+metadata_upper(v,depth+1)+2 for k,v in value.items())
    raise ValueError('nonprimitive metadata')


def parse_json(body):
    def pairs(items):
        out={}
        for k,v in items:
            if k in out: raise ValueError('duplicate JSON key')
            out[k]=v
        return out
    def invalid(x): raise ValueError('nonfinite JSON constant')
    value=json.loads(body.decode('utf-8'),object_pairs_hook=pairs,parse_constant=invalid)
    metadata_upper(value)
    return value


class Store:
    def __init__(self,budget,roots):
        self.budget=budget
        self.roots=tuple(path_admit(str(r)) for r in roots)
        if not self.roots: raise ValueError('no admitted input roots')
        for r in self.roots:
            if not r.is_dir(): raise ValueError('input root is not directory')
        self.outputs=[]
    def read(self,descriptor,limit,request=False):
        if type(descriptor) is not dict or set(descriptor)!={'path','pin'}: raise ValueError('body descriptor')
        pin=pin_admit(descriptor['pin']); n=pin['bytes']; b=self.budget
        if n>limit: b.fail('selected body metadata cap')
        b.reserve('bounded-body-read',read_bytes=n+1,allocation_bytes=3*(n+1),live_bytes=3*(n+1),elements=n+1)
        path=path_admit(descriptor['path'],None if request else self.roots)
        fd=None; f=None; primary=None; later=[]; body=None
        try:
            fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW); b.tick()
            initial=os.fstat(fd)
            if not stat.S_ISREG(initial.st_mode) or initial.st_nlink!=1 or initial.st_size!=n: raise ValueError('regular pinned file extent')
            if stamp(path.lstat())!=stamp(initial): raise ValueError('path/open identity mismatch')
            f=os.fdopen(fd,'rb',closefd=True); fd=None
            body=f.read(n+1); b.tick()
            if len(body)!=n or hashlib.sha256(body).hexdigest()!=pin['sha256']: raise ValueError('body digest/extent mismatch')
            if stamp(os.fstat(f.fileno()))!=stamp(initial) or stamp(path.lstat())!=stamp(initial): raise ValueError('body changed during read')
        except BaseException as e: primary=e
        finally:
            try:
                if f is not None: f.close()
                elif fd is not None: os.close(fd)
                b.tick()
                if body is not None and stamp(path.lstat())!=stamp(initial): raise ValueError('path changed after close')
            except BaseException as e: later.append(repr(e))
        if primary is not None or later:
            raise Failure(str(primary) if primary is not None else 'read closeout failure',b.snapshot(),later) from primary
        return body
    def json(self,descriptor,request=False):
        n=pin_admit(descriptor['pin'])['bytes']
        self.budget.reserve('JSON-decode',allocation_bytes=max(1,n*32),live_bytes=max(1,n*32),elements=max(1,n*4),work=max(1,n*8))
        body=self.read(descriptor,64*1024*1024,request)
        result=parse_json(body); self.budget.tick(); return result
    def array(self,descriptor,np):
        if type(descriptor) is not dict or set(descriptor)!={'path','pin','dtype','shape'}: raise ValueError('array descriptor')
        dtype=descriptor['dtype']; shape=descriptor['shape']
        if dtype not in DTYPES or type(shape) is not list or len(shape)>4 or any(type(n) is not int or n<0 for n in shape): raise ValueError('primitive dtype/shape')
        count=math.prod(shape); payload=count*DTYPES[dtype][1]; size=pin_admit(descriptor['pin'])['bytes']
        if not payload+10<=size<=payload+4096+12: raise ValueError('NPY payload/header extent')
        self.budget.reserve('NPY-parse-load',allocation_bytes=payload*3+8192,live_bytes=payload*3+8192,elements=count*3+4096,work=max(1,count*4))
        body=self.read({'path':descriptor['path'],'pin':descriptor['pin']},payload+4108)
        if body[:6]!=b'\x93NUMPY': raise ValueError('NPY magic')
        version=tuple(body[6:8])
        if version==(1,0): offset=10; length=int.from_bytes(body[8:10],'little')
        elif version==(2,0): offset=12; length=int.from_bytes(body[8:12],'little')
        else: raise ValueError('unsupported primitive NPY version')
        if not 0<length<=4096 or offset+length+payload!=len(body): raise ValueError('NPY exact header/payload')
        header=ast.literal_eval(body[offset:offset+length].decode('latin1').strip())
        if type(header) is not dict or set(header)!={'descr','fortran_order','shape'} or header['descr']!=DTYPES[dtype][0] or header['fortran_order'] is not False or header['shape']!=tuple(shape): raise ValueError('NPY header differs from admitted primitive')
        self.budget.tick(); a=np.load(io.BytesIO(body),allow_pickle=False); self.budget.tick()
        if a.dtype!=np.dtype(dtype) or a.shape!=tuple(shape) or not a.flags.c_contiguous: raise ValueError('loaded NPY schema mismatch')
        return a
    def sync_directory(self,path):
        fd=None; primary=None; later=[]; b=self.budget
        try:
            b.tick(); fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY); b.tick()
            os.fsync(fd); b.tick()
        except BaseException as e: primary=e
        finally:
            try:
                if fd is not None: os.close(fd)
                b.tick()
            except BaseException as e: later.append(repr(e))
        if primary is not None or later:
            raise Failure(str(primary) if primary is not None else 'directory closeout failure',b.snapshot(),later) from primary
    def fresh_root(self,value):
        b=self.budget; b.reserve('fresh-output-directory',files=1,write_bytes=4096)
        path=path_admit(value)
        if any(path==r or path in r.parents or r in path.parents for r in self.roots): raise ValueError('output/input overlap')
        if path.exists(): raise ValueError('output root exists; no retry/overwrite')
        b.tick(); path.mkdir(mode=0o700); b.tick()
        self.sync_directory(path.parent)
        self.root=path; return path
    def write_body(self,relative,body):
        b=self.budget
        if type(relative) is not str or Path(relative).is_absolute() or '..' in Path(relative).parts or str(Path(relative))!=relative: raise ValueError('output member')
        b.reserve('output-body',write_bytes=len(body),files=1,work=max(1,len(body)))
        path=path_admit(str(self.root/relative)); fd=None; f=None; primary=None; later=[]
        try:
            b.tick(); fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600); b.tick()
            f=os.fdopen(fd,'wb',closefd=True); fd=None
            written=f.write(body); b.tick()
            if written!=len(body): raise ValueError('short publication')
            f.flush(); b.tick(); os.fsync(f.fileno()); b.tick()
            st=os.fstat(f.fileno())
            if st.st_size!=len(body) or st.st_nlink!=1 or stamp(path.lstat())!=stamp(st): raise ValueError('publication identity')
        except BaseException as e: primary=e
        finally:
            try:
                if f is not None:f.close()
                elif fd is not None:os.close(fd)
                b.tick()
                if primary is None and stamp(path.lstat())!=stamp(st): raise ValueError('publication changed after close')
            except BaseException as e:later.append(repr(e))
        if primary is not None or later: raise Failure(str(primary) if primary is not None else 'publication closeout failure',b.snapshot(),later) from primary
        self.sync_directory(path.parent)
        descriptor={'path':str(path),'pin':{'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}}
        self.outputs.append(descriptor); return descriptor
    def write_json(self,relative,value):
        upper=metadata_upper(value)
        self.budget.reserve('JSON-encoding',serialized_bytes=upper,allocation_bytes=upper*3,live_bytes=upper*3,elements=upper,work=max(1,upper))
        body=canonical(value)
        if len(body)>upper: self.budget.fail('JSON bound calculation')
        return self.write_body(relative,body)
    def write_array(self,relative,a,np):
        if type(a) is not np.ndarray or str(a.dtype) not in DTYPES or not a.flags.c_contiguous: raise ValueError('unsafe output array')
        n=a.nbytes; cap=n+4108
        self.budget.reserve('NPY-encoding',serialized_bytes=cap,allocation_bytes=cap*3,live_bytes=cap*3,elements=a.size*3+4096,work=max(1,a.size*4))
        stream=io.BytesIO(); np.save(stream,a,allow_pickle=False); body=stream.getvalue(); self.budget.tick()
        if len(body)>cap: self.budget.fail('NPY encoding cap')
        d=self.write_body(relative,body); d.update({'dtype':str(a.dtype),'shape':list(a.shape)}); return d
    def save_tree(self,value,np,name='STATE.json'):
        # Parent output closure captures each complete primitive body; it cannot
        # treat STATE.json alone as the fitted model.
        self.budget.reserve('array-directory',files=1,write_bytes=4096)
        directory=self.root/'arrays'; self.budget.tick(); directory.mkdir(mode=0o700); self.budget.tick(); self.sync_directory(self.root)
        index=0
        def visit(v,depth=0):
            nonlocal index
            if depth>40: raise ValueError('state nesting')
            if type(v) is np.ndarray:
                rel=f'arrays/{index:06d}.npy';index+=1
                return {'$array':self.write_array(rel,v,np)}
            if type(v) is dict:
                if any(type(k) is not str or k=='$array' for k in v): raise ValueError('state metadata keys')
                return {k:visit(x,depth+1) for k,x in v.items()}
            if type(v) in (tuple,list): return [visit(x,depth+1) for x in v]
            metadata_upper(v); return v
        return self.write_json(name,{'schema':'neural049_r1_safe_tree_v1','tree':visit(value)})
    def load_tree(self,descriptor,np):
        doc=self.json(descriptor)
        if type(doc) is not dict or set(doc)!={'schema','tree'} or doc['schema']!='neural049_r1_safe_tree_v1': raise ValueError('safe state container')
        def visit(v,depth=0):
            if depth>40: raise ValueError('state nesting')
            if type(v) is dict:
                if '$array' in v:
                    if set(v)!={'$array'}: raise ValueError('mixed array tag')
                    return self.array(v['$array'],np)
                return {k:visit(x,depth+1) for k,x in v.items()}
            if type(v) is list: return [visit(x,depth+1) for x in v]
            metadata_upper(v); return v
        return visit(doc['tree'])
