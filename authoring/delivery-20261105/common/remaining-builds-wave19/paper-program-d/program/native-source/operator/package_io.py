"""Bounded selected-file I/O; no scientific decoding or execution."""
import hashlib,json,os,stat
from pathlib import Path,PurePosixPath

def need(ok,message):
    if not ok:raise ValueError(message)

def relative(value):
    p=PurePosixPath(value)
    need(type(value)is str and p.parts and not p.is_absolute() and '..'not in p.parts and str(p)==value,'Safe relative path')
    return p

def read(path,cap,expected=None,allow_empty=False):
    path=Path(path)
    need(all(not p.is_symlink() for p in (path,*path.parents)),'Unlinked path')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        a=os.fstat(fd)
        need(stat.S_ISREG(a.st_mode)and a.st_nlink==1 and (0<=a.st_size if allow_empty else 0<a.st_size) and a.st_size<=cap,'Bounded ordinary input')
        with os.fdopen(fd,'rb',closefd=False)as stream:body=stream.read(cap+1)
        b=os.fstat(fd);c=path.lstat();fields=('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_nlink','st_mode')
        need(len(body)==a.st_size and all(getattr(a,k)==getattr(b,k)==getattr(c,k)for k in fields),'Stable complete input')
        if expected is not None:
            need(len(body)==expected['bytes']and hashlib.sha256(body).hexdigest()==expected['sha256'],'Exact selected asset pin')
        return body
    finally:os.close(fd)

def metadata(path):return json.loads(read(path,2000000))

def asset_map(root):
    rows=metadata(root/'private/assets.json')['files']
    need(type(rows)is list and len({r['target']for r in rows})==len(rows),'Unique selected assets')
    return {r['target']:r for r in rows}

def bound(root,rows,target):
    relative(target);r=rows[target]
    return read(root/target,r['bytes'],r)
