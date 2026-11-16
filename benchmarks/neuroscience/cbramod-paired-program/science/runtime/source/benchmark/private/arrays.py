"""Pinned ordinary-file capture and strict numeric NPY admission; never pickle."""
import ast
import hashlib
import os
from pathlib import Path
import stat
import numpy as np


def need(v,message):
    if not v:
        raise ValueError(message)


def inspect_npy(path,shape,dtype):
    with open(path,'rb') as f:
        prefix=f.read(8);need(prefix[:6]==b'\x93NUMPY' and tuple(prefix[6:]) in ((1,0),(2,0),(3,0)),'NPY1/2/3 numeric format')
        width=2 if prefix[6]==1 else 4;raw=f.read(width);need(len(raw)==width,'complete NPY header length')
        size=int.from_bytes(raw,'little');need(1<=size<=4096,'bounded NPY header')
        raw=f.read(size);need(len(raw)==size and raw.endswith(b'\n'),'complete NPY header')
        try:tree=ast.parse(raw.decode('ascii').strip(),mode='eval').body
        except (SyntaxError,UnicodeError) as e:raise ValueError('literal ASCII NPY header') from e
        need(isinstance(tree,ast.Dict) and len(tree.keys)==3 and all(isinstance(k,ast.Constant) and type(k.value) is str for k in tree.keys),'literal exact NPY dictionary')
        need({k.value for k in tree.keys}=={'descr','fortran_order','shape'},'unique exact NPY fields')
        h=ast.literal_eval(tree)
        need(type(h['shape']) is tuple and all(type(x) is int for x in h['shape']) and list(h['shape'])==shape,'exact matrix shape')
        need(h['descr']==dtype and h['fortran_order'] is False,'declared numeric dtype/C order')
        need(f.tell()+shape[0]*shape[1]*int(dtype[-1])==Path(path).stat().st_size,'no truncated/trailing payload')
    array=np.load(path,allow_pickle=False,mmap_mode='r',max_header_size=4096)
    try:
        for begin in range(0,len(array),4096):
            part=array[begin:begin+4096]
            need(np.isfinite(part).all() and (np.abs(part)<=1e100).all(),'finite bounded prediction values')
    except BaseException:
        array._mmap.close();raise
    return array


def snapshot(root,item,destination):
    root=Path(root);source=root/item['path']
    need(root.is_dir() and not root.is_symlink(),'ordinary artifact root')
    relative=Path(item['path']);need(not relative.is_absolute() and '..' not in relative.parts,'relative capture path')
    need(all(not (root/Path(*relative.parts[:i])).is_symlink() for i in range(1,len(relative.parts))),'no linked input directory')
    fd=os.open(source,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd);need(stat.S_ISREG(before.st_mode) and before.st_size==item['bytes'],'exact ordinary artifact extent')
        digest=hashlib.sha256();count=0
        with os.fdopen(fd,'rb',closefd=False) as reader,open(destination,'xb') as writer:
            while True:
                chunk=reader.read(min(1<<20,item['bytes']+1-count))
                if not chunk:break
                count+=len(chunk);need(count<=item['bytes'],'bounded artifact capture')
                digest.update(chunk);writer.write(chunk)
        after=os.fstat(fd)
        need(count==item['bytes'] and digest.hexdigest()==item['sha256'] and all(getattr(before,k)==getattr(after,k) for k in ('st_size','st_ino','st_dev','st_mtime_ns','st_ctime_ns')),'same-capture stable content pin')
    finally:
        os.close(fd)
    Path(destination).chmod(0o400)
    return inspect_npy(destination,item['shape'],item['dtype'])
