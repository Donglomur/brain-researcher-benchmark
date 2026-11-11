"""Bounded numeric wire format; no pickle, NumPy loading, compression or implicit axes."""
import math
import hashlib
import os
import stat
import struct
from .strict import require, integer, number, unique

DTYPES={"float64-le":("d",8),"float32-le":("f",4),"int64-le":("q",8),"uint8":("B",1)}

def descriptor(d):
    require(d.get("format")=="jaxley-flat-numeric-v1","array format")
    require(d.get("dtype") in DTYPES,"array dtype")
    shape=d.get("shape")
    require(type(shape) is list and shape,"array shape")
    count=1
    for size in shape:count*=integer(size,"array dimension",1)
    code,width=DTYPES[d["dtype"]]
    require(count*width==integer(d.get("bytes"),"array byte count"),"array shape/bytes mismatch")
    require(type(d.get("axes")) is list and len(d["axes"])==len(shape),"explicit array axes")
    for axis,size in zip(d["axes"],shape):
        unique(axis,"array axis");require(len(axis)==size,"complete unique axis identifiers")
    require(d.get("unit") and d.get("sha256") and d.get("path"),"array scientific identity")
    return count,code,width

def validate_stream(root,d,*,clock,byte_cap):
    """Authenticate and validate every numeric value, using one bounded chunk.

    All wire dtypes are little endian and have widths dividing 65536. Masked or
    presently unconsumed products receive the same finite-value rule. There is
    no implicit NaN/missing-value policy in this version of the output format.
    """
    count,code,width=descriptor(d)
    require(d["bytes"]<=byte_cap,"numeric stream cap")
    p,leaf=root.parent(d["path"])
    try:fd=os.open(leaf,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=p)
    finally:os.close(p)
    try:
        before=os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size==d["bytes"],"numeric stream identity")
        h=hashlib.sha256();read=0;values=0;tail=b""
        while True:
            clock.check();block=os.read(fd,65536)
            if not block:break
            read+=len(block);require(read<=byte_cap,"numeric stream grew");h.update(block)
            data=tail+block;stop=len(data)-len(data)%width
            for (x,) in struct.iter_unpack("<"+code,data[:stop]):
                number(x,"nonfinite required numeric product");values+=1
                if d["unit"]=="boolean":
                    require(d["dtype"]=="uint8" and x in (0,1),"invalid boolean required product")
            tail=data[stop:]
        after=os.fstat(fd)
        require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns),"numeric stream mutated")
        require(not tail and read==d["bytes"] and values==count,"numeric stream size/content count")
        require(h.hexdigest()==d["sha256"],"numeric stream pin")
        clock.check();return {"bytes":read,"values":values,"finite":True}
    finally:os.close(fd)

def load_flat(root,d,*,clock,byte_cap,memory_cap):
    count,code,width=descriptor(d)
    require(d["bytes"]<=byte_cap,"declared full-array byte cap")
    # Python scalar/list overhead is reserved separately, not asserted equal to wire bytes.
    require(count*40+d["bytes"]<=memory_cap,"full-array Python allocation not admitted")
    body=root.read(d["path"],byte_cap,pin=d,clock=clock)
    values=[]
    for (x,) in struct.iter_unpack("<"+code,body):
        number(x,"nonfinite array")
        values.append(x)
    require(len(values)==count,"array count")
    return values

def reshape2(values,shape):
    require(len(shape)==2 and len(values)==shape[0]*shape[1],"matrix shape")
    return [values[i*shape[1]:(i+1)*shape[1]] for i in range(shape[0])]

