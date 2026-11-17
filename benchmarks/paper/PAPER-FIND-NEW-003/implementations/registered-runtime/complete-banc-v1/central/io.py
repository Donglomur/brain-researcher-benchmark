"""Bounded capability-relative I/O; failures retain independent close evidence."""
from pathlib import Path
import os,stat
from banc_runtime.codec import need,parse,encode,pin,descriptor,relative
from .custody import acquire,parent,open_file,identity
from .clock import guard
from .failures import FailureEnvelope,combine

def absolute_directory(path):return acquire(path)

def _read(root,name,meter,cap,declared=None):
    need(type(cap) is int and cap>=0,'bounded complete read')
    guard(meter,'before_read');meter.reserve_read((declared['bytes'] if declared else cap)+1)
    fd=None;raw=b'';primary=None;directory=None;read_count=0
    try:
        directory,leaf,fd=open_file(root,name,os.O_RDONLY|os.O_NONBLOCK)
        before=os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size<=cap,'bounded ordinary single-link file')
        if declared:need(before.st_size==declared['bytes'],'exact declared file extent')
        chunks=[];remaining=before.st_size+1
        while remaining:
            chunk=os.read(fd,min(remaining,1048576))
            if not chunk:break
            chunks.append(chunk);remaining-=len(chunk);read_count+=len(chunk)
        raw=b''.join(chunks)
        after=os.fstat(fd);named=os.stat(leaf,dir_fd=directory.fd,follow_symlinks=False)
        fields=('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_nlink')
        need(all(getattr(before,k)==getattr(after,k)==getattr(named,k) for k in fields) and len(raw)==before.st_size,'original complete file/current-name identity')
        if declared:need(pin(raw)=={k:declared[k] for k in ('bytes','sha256')},'exact complete file hash')
        directory.verify();guard(meter,'after_read')
    except BaseException as exc:primary=FailureEnvelope(exc,'read')
    finally:
        try:meter.complete_read(read_count)
        except BaseException as exc:primary=combine(primary,exc,'read_accounting_observation')
        if fd is not None:
            try:os.close(fd)
            except BaseException as exc:primary=combine(primary,exc,'read_close_ambiguous_no_retry')
    if primary is not None:raise primary
    return raw

def read(root,declared,meter,cap):
    d=descriptor(declared);return _read(root,d['path'],meter,cap,d)

def read_json(root,declared,meter,cap=1048576):return parse(read(root,declared,meter,cap))

def metadata(path,meter,cap):
    p=Path(path).absolute();return _read(acquire(p.parent),p.name,meter,cap)

def fresh_directory(root,name,meter=None):
    if meter is not None:guard(meter,'before_directory_creation')
    directory,leaf=parent(root,name);cap=directory.child(leaf,create=True)
    if meter is not None:guard(meter,'after_directory_creation')
    return cap

def _write(root,name,raw,meter,diagnostic=False,already_reserved=False):
    need(type(raw) is bytes,'immutable output bytes')
    if diagnostic:need(already_reserved and len(raw)<=65536,'bounded previously reserved failure-only publication')
    else:guard(meter,'before_output_publication')
    if not already_reserved:meter.reserve_output(len(raw))
    fd=None;directory=None;primary=None;written=0
    try:
        directory,leaf,fd=open_file(root,name,os.O_WRONLY|os.O_CREAT|os.O_EXCL)
        original=identity(os.fstat(fd));remaining=memoryview(raw)
        while remaining:
            n=os.write(fd,remaining);need(n>0,'short output write');written+=n;remaining=remaining[n:]
        os.fsync(fd)
        st=os.stat(leaf,dir_fd=directory.fd,follow_symlinks=False)
        need(identity(st)==original and stat.S_ISREG(st.st_mode) and st.st_nlink==1 and st.st_size==len(raw),'original published file identity')
        directory.verify()
        if not diagnostic:guard(meter,'after_output_publication_before_close')
    except BaseException as exc:primary=FailureEnvelope(exc,'write')
    finally:
        try:meter.complete_output(written)
        except BaseException as exc:primary=combine(primary,exc,'write_accounting_observation')
        if fd is not None:
            try:os.close(fd)
            except BaseException as exc:primary=combine(primary,exc,'write_close_ambiguous_no_retry')
    if directory is not None:
        try:
            directory.verify()
            if not diagnostic:guard(meter,'after_output_close')
        except BaseException as exc:primary=combine(primary,exc,'publication_closure')
    if primary is not None:raise primary
    return {'path':name,**pin(raw)}

def write(root,name,raw,meter):return _write(root,name,raw,meter)
def write_json(root,name,value,meter):return write(root,name,encode(value),meter)
def write_diagnostic(root,name,value,meter):return _write(root,name,encode(value),meter,diagnostic=True,already_reserved=True)

def exact_fields(value,fields,label):need(type(value) is dict and set(value)==set(fields),label+' exact fields')
def text(value,label):need(type(value) is str and value and '\0' not in value,label+' nonempty string');return value
def digest(value):need(type(value) is str and len(value)==64 and all(c in '0123456789abcdef' for c in value),'lowercase SHA256');return value
def integer(value,label,minimum=0):need(type(value) is int and value>=minimum,label+' integer domain');return value
