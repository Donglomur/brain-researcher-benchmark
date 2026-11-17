"""Closed passive object formats and bounded stable ordinary-file snapshots."""
from pathlib import Path, PurePosixPath
import ast
import hashlib
import json
import math
import os
import stat
import struct
import unicodedata
from .errors import require
from .custody import Custody,observation
from .deadline import boundary


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                       allow_nan=False)+'\n').encode('utf-8')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _pairs(rows):
    out={}
    for k,v in rows:
        require(k not in out, 'duplicate JSON key')
        out[k]=v
    return out


def decode(raw):
    def invalid(_):
        raise ValueError('nonfinite JSON constant')
    return json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs, parse_constant=invalid)


def fields(value, required, optional=()):
    require(type(value) is dict and set(required)<=set(value)<=set(required)|set(optional),
            'wrong closed object fields')
    return value


def positive(value, name, allow_zero=False):
    require(type(value) is int and value >= (0 if allow_zero else 1), 'invalid '+name)
    return value


def rel(name):
    require(type(name) is str and name and '\x00' not in name and '\\' not in name,
            'invalid relative path')
    p=PurePosixPath(name)
    require(not p.is_absolute() and p.as_posix()==name and all(x not in ('','.','..') for x in p.parts),
            'noncanonical path')
    require(unicodedata.normalize('NFC',name)==name and len(name.encode('utf-8'))<=4096, 'noncanonical or overlong Unicode path')
    return p


def pin(raw, path):
    rel(path)
    return {'path':path,'bytes':len(raw),'sha256':digest(raw)}


def check_pin(row):
    fields(row, ('path','bytes','sha256'))
    rel(row['path']);positive(row['bytes'],'bytes',True)
    require(type(row['sha256']) is str and len(row['sha256'])==64 and
            all(x in '0123456789abcdef' for x in row['sha256']), 'bad SHA256')


def unique_paths(rows):
    seen=set()
    for row in rows:
        check_pin(row)
        key=row['path'].casefold()
        require(key not in seen,'duplicate or case-colliding path')
        seen.add(key)


class Reader:
    def __init__(self, root, byte_cap, file_cap, guard=None):
        self.custody=Custody();self.guard=guard;self.consumed_bytes=0;self.partial_observations=[]
        if guard:guard()
        self.root=Path(root).absolute()
        require(self.root.is_dir() and not self.root.is_symlink(),'ordinary input root required')
        self.byte_cap=positive(byte_cap,'read cap');self.file_cap=positive(file_cap,'file cap')
        self.bytes=0;self.files=0;self.observations=[]

    def path(self, name):
        if self.guard:self.guard()
        parts=rel(name).parts;p=self.root
        for i,part in enumerate(parts):
            if self.guard:self.guard()
            require(part in os.listdir(p),'exact directory entry missing')
            p=p/part;s=p.lstat()
            require(not stat.S_ISLNK(s.st_mode),'symlink forbidden')
            if i<len(parts)-1:require(stat.S_ISDIR(s.st_mode),'non-directory ancestor')
        return p

    @boundary
    def capture(self,name,expected=None):
        if self.guard:self.guard()
        if expected is not None:check_pin(expected)
        p=self.path(name);s=p.lstat()
        require(stat.S_ISREG(s.st_mode) and s.st_nlink==1,'ordinary file identity')
        if expected is not None:require(s.st_size==expected['bytes'],'object size mismatch')
        require(self.files+1<=self.file_cap and self.bytes+s.st_size+1<=self.byte_cap,'read budget exceeded')
        self.files+=1;self.bytes+=s.st_size+1
        pieces=[];remaining=s.st_size+1
        observed={'path':name,'reserved_bytes':s.st_size+1,'consumed_bytes':0,'consumed_total':self.consumed_bytes,'opened':False,'closed':False}
        self.partial_observations.append(observed)
        fd=None;original=None
        try:
            fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW);observed['opened']=True
            first=os.fstat(fd)
            require((first.st_dev,first.st_ino)==(s.st_dev,s.st_ino),'open identity changed')
            while remaining:
                if self.guard:self.guard()
                b=os.read(fd,min(remaining,1024*1024))
                self.consumed_bytes+=len(b);observed['consumed_bytes']+=len(b);observed['consumed_total']=self.consumed_bytes
                if not b:break
                pieces.append(b);remaining-=len(b)
                if self.guard:self.guard()
            raw=b''.join(pieces);last=os.fstat(fd)
        except BaseException as exc:
            original=exc;self.custody.fail(exc,'Reader.capture:'+name)
            raise
        finally:
            if fd is not None:
                try:os.close(fd);observed['closed']=True
                except BaseException as secondary:
                    observed['close_error_type']=type(secondary).__name__
                    if original is not None:self.custody.add_secondary(secondary,'Reader.capture:close')
                    else:
                        self.custody.fail(secondary,'Reader.capture:close')
                        raise

        after=p.lstat()
        identity=lambda x:(x.st_dev,x.st_ino,x.st_size,x.st_mtime_ns,x.st_ctime_ns,x.st_nlink)
        require(identity(first)==identity(last)==identity(after),'file changed during capture')
        require(len(raw)==s.st_size,'object length changed')
        row=pin(raw,name)
        if expected is not None:require(row==expected,'object hash mismatch')
        if self.guard:self.guard()
        self.observations.append(row)
        return raw

    def read(self,row):return self.capture(row['path'],row)

    def json(self,row):return decode(self.read(row))


def inventory(root, byte_cap, file_cap, guard=None):
    if guard:guard()
    """Inventory metadata first; reject links/collisions before any file read."""
    root=Path(root);rows=[];total=0;seen=set()
    for folder,dirs,files in os.walk(root,followlinks=False):
        if guard:guard()
        for name in [*dirs,*files]:
            if guard:guard()
            p=Path(folder)/name;s=p.lstat();n=p.relative_to(root).as_posix();rel(n)
            key=n.casefold();require(key not in seen,'case-colliding output');seen.add(key)
            require(not stat.S_ISLNK(s.st_mode),'output symlink')
            require(stat.S_ISDIR(s.st_mode) or (stat.S_ISREG(s.st_mode) and s.st_nlink==1),'nonordinary output')
            require(len(seen)<=file_cap,'output file/dir cap')
            if stat.S_ISREG(s.st_mode):
                total+=s.st_size;require(total<=byte_cap,'output byte cap')
                rows.append((n,s.st_size))
    return sorted(rows)


def snapshot(root, byte_cap, file_cap, guard=None, observations=None):
    rows=inventory(root,byte_cap,file_cap,guard=guard);reader=Reader(root,byte_cap+file_cap,file_cap,guard=guard)
    out=[]
    details={'reserved_bytes':0,'consumed_bytes':0,'completed_objects':out,'partial_observations':reader.partial_observations}
    if observations is not None:observations.append(details)
    with observation(reader,'snapshot',details,refresh=lambda d:d.update(reserved_bytes=reader.bytes,consumed_bytes=reader.consumed_bytes)):
        for name,size in rows:
            raw=reader.capture(name);require(len(raw)==size,'unstable snapshot census')
            out.append(pin(raw,name))
        require(rows==inventory(root,byte_cap,file_cap,guard=guard),'output census changed')
        return out


def write_new(path, raw, guard=None):
    state=Custody();details={'path':str(path),'requested_bytes':len(raw),'written_bytes':0,'opened':False,'closed':False,'durable':False}
    state.observations.append(details);fd=None;original=None
    try:
        if guard:guard()
        path=Path(path);require(path.parent.is_dir() and not path.parent.is_symlink(),'ordinary destination parent')
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600);details['opened']=True
        while details['written_bytes']<len(raw):
            if guard:guard()
            n=os.write(fd,memoryview(raw)[details['written_bytes']:]);details['written_bytes']+=n
            require(n>0,'write made no progress')
        os.fsync(fd);details['durable']=True
        if guard:guard()
    except BaseException as exc:
        original=exc;state.fail(exc,'write_new')
        raise
    finally:
        if fd is not None:
            try:os.close(fd);details['closed']=True
            except BaseException as secondary:
                if original is not None:state.add_secondary(secondary,'write_new:close')
                else:
                    state.fail(secondary,'write_new:close')
                    raise


def npy_header(raw, expected):
    """Passive ndarray container validation only; never allow pickle/object dtype."""
    require(raw[:6]==b'\x93NUMPY' and raw[6:8] in (b'\x01\x00',b'\x02\x00'),'unsupported NPY')
    width=2 if raw[6]==1 else 4;start=8+width
    require(len(raw)>=start,'short NPY')
    n=int.from_bytes(raw[8:start],'little');require(0<n<=65536 and start+n<=len(raw),'NPY header length')
    header=ast.literal_eval(raw[start:start+n].decode('latin1'))
    fields(header,('descr','fortran_order','shape'))
    sizes={'<f4':4,'<f8':8,'<i4':4,'<i8':8,'|u1':1,'|b1':1}
    require(header['descr'] in sizes and header['fortran_order'] is False,'nonpassive dtype/layout')
    shape=header['shape'];require(type(shape) is tuple and 1<=len(shape)<=5 and all(type(x) is int and x>0 for x in shape),'shape')
    require(list(shape)==expected['shape'] and header['descr']==expected['dtype'],'array ABI mismatch')
    require(start+n+math.prod(shape)*sizes[header['descr']]==len(raw),'array byte length')
    return {'offset':start+n,'shape':list(shape),'dtype':header['descr']}


def finite_rows(raw, shape, dtype):
    """Future grader's passive finite numeric decoder; not used by inert controls."""
    head=npy_header(raw,{'shape':shape,'dtype':dtype});fmt={'<f4':'f','<f8':'d','<i4':'i','<i8':'q','|u1':'B','|b1':'?'}[dtype]
    out=[x[0] for x in struct.iter_unpack('<'+fmt,raw[head['offset']:])]
    require(all(math.isfinite(x) for x in out),'nonfinite array')
    return out
