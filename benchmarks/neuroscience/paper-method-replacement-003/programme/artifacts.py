"""Concrete output writer and immutable same-run capture.

This is not a native sandbox or a protected-target issuer. The evaluator must
own its directory and resource lifetime before invoking scientific functions.
"""
import hashlib,json,os,stat
from dataclasses import dataclass
from pathlib import Path

class ArtifactError(ValueError):pass

@dataclass(frozen=True)
class CapturedFile:
    relative: str
    bytes: int
    sha256: str
    kind: str

class Outputs:
    def __init__(self,root,*,max_bytes,max_files,max_member,max_read_bytes=None):
        self.root=Path(root);self.max_bytes=max_bytes;self.max_files=max_files;self.max_member=max_member
        if self.root.is_symlink() or not self.root.is_dir() or any(self.root.iterdir()):
            raise ArtifactError('fresh evaluator-owned output directory required')
        if min(max_bytes,max_files,max_member)<=0:raise ArtifactError('finite positive output caps required')
        self.records=[];self.bytes=0;self.closed=False;self.failures=[]
        if max_read_bytes is not None and (type(max_read_bytes) is not int or max_read_bytes<=0):
            raise ArtifactError('explicit positive captured-input read capacity required')
        self.max_read_bytes=max_read_bytes;self.read_reserved=0

    def read_captured(self,record):
        """Authenticate this owner's exact returned bytes before any consumer.

        No capacity is inferred from an output limit. Failed reads retain their
        full known reservation; physical reads and host ownership remain gates.
        """
        if not any(r is record for r in self.records):raise ArtifactError('not this output owner\'s capture')
        if self.max_read_bytes is None or self.read_reserved+record.bytes>self.max_read_bytes:
            raise ArtifactError('captured-input read capacity absent or exhausted')
        self.read_reserved+=record.bytes
        if Path(record.relative).name!=record.relative:raise ArtifactError('invalid capture path')
        fd=None;first=None;returned=None
        try:
            fd=os.open(self.root/record.relative,os.O_RDONLY|os.O_NOFOLLOW)
            before=os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size!=record.bytes:
                raise ArtifactError('capture extent/type changed')
            body=bytearray()
            while len(body)<record.bytes:
                chunk=os.read(fd,min(65536,record.bytes-len(body)))
                if not chunk:raise ArtifactError('short captured input')
                body.extend(chunk)
            after=os.fstat(fd)
            if any(getattr(before,k)!=getattr(after,k) for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')):
                raise ArtifactError('captured input changed while read')
            if hashlib.sha256(body).hexdigest()!=record.sha256:raise ArtifactError('captured input content changed')
            returned=bytes(body)
        except BaseException as error:
            first=error;self.failures.append(error)
        finally:
            if fd is not None:
                try:os.close(fd)
                except BaseException as error:
                    self.failures.append(error)
                    if first is None:first=error
        if first is not None:raise first
        return returned

    def _path(self,name):
        p=Path(name)
        if p.is_absolute() or '..' in p.parts or len(p.parts)!=1 or not name:
            raise ArtifactError('flat exact output filename required')
        if self.closed or len(self.records)>=self.max_files:raise ArtifactError('output lifetime/extent exhausted')
        return self.root/p

    def _capture(self,path,kind):
        a=path.lstat()
        if not stat.S_ISREG(a.st_mode) or a.st_nlink!=1 or a.st_size>self.max_member:
            raise ArtifactError('invalid output member')
        if self.bytes+a.st_size>self.max_bytes:raise ArtifactError('output aggregate exceeded')
        h=hashlib.sha256();fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
        try:
            before=os.fstat(fd);seen=0
            while True:
                b=os.read(fd,min(65536,before.st_size-seen+1))
                if not b:break
                seen+=len(b)
                if seen>before.st_size:raise ArtifactError('output grew during capture')
                h.update(b)
            after=os.fstat(fd)
            if seen!=before.st_size or any(getattr(before,k)!=getattr(after,k) for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')):
                raise ArtifactError('unstable output capture')
        finally:os.close(fd)
        os.chmod(path,0o444)
        record=CapturedFile(path.name,a.st_size,h.hexdigest(),kind)
        self.records.append(record);self.bytes+=record.bytes;return record

    def array(self,name,array):
        import numpy as np
        a=np.asarray(array)
        if a.dtype.hasobject:raise ArtifactError('object/pickle array output prohibited')
        # Admit a conservative format/header envelope before writing any bytes.
        if a.nbytes+65536>min(self.max_member,self.max_bytes-self.bytes):
            raise ArtifactError('array output pre-admission failed')
        p=self._path(name)
        with p.open('xb') as f:np.save(f,a,allow_pickle=False)
        return self._capture(p,'numpy_array_no_pickle')

    def json(self,name,value):
        b=(json.dumps(value,sort_keys=True,allow_nan=False,default=_json_value)+'\n').encode()
        if len(b)>min(self.max_member,self.max_bytes-self.bytes):raise ArtifactError('JSON output pre-admission failed')
        p=self._path(name)
        with p.open('xb') as f:f.write(b)
        return self._capture(p,'json_metadata')

    def state_dict(self,name,state):
        """Explicit tensor-only NumPy transport, never pickle/model deserialization."""
        result=[]
        for ordinal,(key,value) in enumerate(state.items()):
            array=value.detach().cpu().numpy()
            record=self.array(f'{name}-{ordinal:04d}.npy',array)
            result.append({'parameter':key,'capture':record.__dict__})
        return self.json(name+'-index.json',result)

    def tensor_tree(self,name,value):
        """Finite explicit tensor/scalar/list tree, no arbitrary pickle objects."""
        import numpy as np
        import torch
        nodes=0
        def visit(x):
            nonlocal nodes
            nodes+=1
            if nodes>self.max_files:raise ArtifactError('tensor tree node cap')
            if isinstance(x,torch.Tensor):x=x.detach().cpu().numpy()
            if isinstance(x,np.ndarray):return {'array':self.array(f'{name}-{nodes:06d}.npy',x).__dict__}
            if x is None or type(x) in (str,int,float,bool):return {'scalar':x}
            if type(x) in (list,tuple):return {'sequence_type':type(x).__name__,'items':[visit(v) for v in x]}
            if type(x) is dict and all(type(k) is str for k in x):return {'mapping':{k:visit(v) for k,v in x.items()}}
            raise ArtifactError('unsupported model state type; no opaque serialized substitute')
        descriptor=visit(value)
        return self.json(name+'-tree.json',descriptor)

    def close(self):
        self.closed=True
        return tuple(self.records)

def _json_value(value):
    if hasattr(value,'__dataclass_fields__'):return value.__dict__
    raise TypeError(type(value).__name__)
