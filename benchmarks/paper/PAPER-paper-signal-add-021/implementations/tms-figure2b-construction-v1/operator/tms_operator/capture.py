"""Finite exact output capture after the trusted host has closed all writers."""
from __future__ import annotations
import hashlib,os,stat
from pathlib import Path
from .schema import *
from tms_figure import outputs
from tms_figure.contract import OUTPUT_SCHEMA

class CaptureFailure(Refusal):
    def __init__(self,first,close_failures):
        self.first=first;self.close_failures=close_failures
        super().__init__('capture failed; original error and independent close failures retained')

def close_owned(descriptors,first=None):
    failures=[]
    for descriptor in descriptors:
        if descriptor is not None:
            try:os.close(descriptor)
            except BaseException as error:failures.append((descriptor,error))
    if failures:
        original=first if first is not None else failures[0][1]
        raise CaptureFailure(original,failures) from original

def identity(st):
    return (st.st_dev,st.st_ino,st.st_mode,st.st_nlink,st.st_size,st.st_mtime_ns,st.st_ctime_ns)

def ordinary(fd,size):
    st=os.fstat(fd)
    require(stat.S_ISREG(st.st_mode) and st.st_nlink==1 and st.st_size==size,'ordinary exact single-link output')
    return st

def names37(fd,budget):
    names=set()
    with os.scandir(fd) as entries:
        for entry in entries:
            budget.charge();require(len(names)<37,'extra output member')
            require(entry.name not in names,'duplicate directory member');names.add(entry.name)
    return names

def read_manifest(rootfd,budget):
    fd=os.open('OUTPUT.json',os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=rootfd);first=None
    try:
        st=os.fstat(fd);integer(st.st_size,1,1048576);ordinary(fd,st.st_size)
        budget.charge(read=st.st_size,write=st.st_size)
        with os.fdopen(fd,'rb',closefd=False) as stream:body=stream.read(st.st_size+1)
        require(len(body)==st.st_size and identity(st)==identity(os.fstat(fd)),'stable manifest capture')
        budget.charge(read=len(body),write=len(body))
        return body,json_body(body),identity(st)
    except BaseException as error:first=error;raise
    finally:close_owned([fd],first)

def size_plan(meta,manifest_bytes,source_bytes,*,copy_count):
    """Full nominal arithmetic only; never constructs scientific arrays."""
    metadata(meta);integer(manifest_bytes,1,1048576);integer(source_bytes);integer(copy_count)
    layout=outputs.specs(meta);binary=sum(x['bytes'] for x in layout.values())
    require(len(layout)==36,'all36 scientific fields')
    return {'schema':'tms_figure2b_extent_plan_v1','binary_output_bytes_per_arm':binary,
        'member_count_per_arm':37,'manifest_bytes_per_arm':manifest_bytes,
        'both_arm_output_bytes':2*(binary+manifest_bytes),'selected_staged_input_copy_bytes':source_bytes*copy_count,
        'scope':'Logical extents only; add all explicit work/log/capture/reference/residual/runtime allocations before native admission.'}

def capture_output(*,source,destination,meta,budget):
    """Trusted internal collector; caller must first validate actual closed host evidence.

    No subprocess, score callback or arbitrary scientific layout parameter exists.
    Return only after exact metadata and byte capture plus inherited full admission.
    Partial private destinations remain on failure for inspection; never reused.
    """
    exact_budget(budget);metadata(meta);source=directory(source)
    target=Path(destination).absolute();separate([source,target])
    fd=os.open(source,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);root_failure=None
    try:
        before=identity(os.fstat(fd));body,manifest,manifest_identity=read_manifest(fd,budget)
        keys(manifest,{'schema','identity','producer','fields'})
        submitted_identity=metadata(manifest['identity'])
        require(manifest['schema']==OUTPUT_SCHEMA and submitted_identity==meta,'full output identity')
        require(type(manifest['producer']) is str and manifest['producer'],'producer description')
        layout=outputs.specs(meta);require(len(layout)==36 and type(manifest['fields']) is dict and set(manifest['fields'])==set(layout),'all36 fields')
        names={'OUTPUT.json'}|{name+'.bin' for name in layout}
        require(names37(fd,budget)==names,'exact37 output members')
        # Admit complete declared geometry and total extent before writing any member.
        for name,spec in layout.items():
            row=manifest['fields'][name];keys(row,{'shape','dtype','bytes','sha256'})
            require(type(row['shape']) is list and all(type(x) is int for x in row['shape']) and type(row['bytes']) is int,'strict field extents')
            require(all(row[k]==spec[k] for k in ('shape','dtype','bytes')),'source-owned field geometry')
            pin({'bytes':row['bytes'],'sha256':row['sha256']})
        target=fresh_directory(target);captured={}
        for name,spec in layout.items():
            row=manifest['fields'][name];filename=name+'.bin'
            inp=os.open(filename,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd)
            out=None;body_failure=None
            try:
                start=ordinary(inp,spec['bytes']);h=hashlib.sha256();remaining=spec['bytes']
                out=os.open(target/filename,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
                while remaining:
                    n=min(65536,remaining);budget.charge(read=n,write=2*n)
                    block=os.read(inp,n);require(len(block)==n,'short output body');h.update(block)
                    offset=0
                    while offset<len(block):
                        wrote=os.write(out,block[offset:]);require(wrote>0,'short capture write');offset+=wrote
                    remaining-=n
                require(identity(start)==identity(os.fstat(inp)),'output changed during capture')
                require(h.hexdigest()==row['sha256'],'captured body hash')
                os.fsync(out);os.fchmod(out,0o400)
                captured[filename]={'bytes':spec['bytes'],'sha256':h.hexdigest(),'source_identity':list(identity(start))}
            except BaseException as error:body_failure=error;raise
            finally:close_owned([inp,out],body_failure)
        verify=os.open('OUTPUT.json',os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd)
        verify_failure=None
        try:require(identity(os.fstat(verify))==manifest_identity,'manifest identity after capture')
        except BaseException as error:verify_failure=error;raise
        finally:close_owned([verify],verify_failure)
        require(identity(os.fstat(fd))==before and names37(fd,budget)==names,'output directory changed')
        budget.charge(write=len(body));out=os.open(target/'OUTPUT.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        output_failure=None
        try:
            with os.fdopen(out,'wb',closefd=False) as stream:stream.write(body);stream.flush();os.fsync(out)
            os.fchmod(out,0o400)
        except BaseException as error:output_failure=error;raise
        finally:close_owned([out],output_failure)
        result=body_pin(body)
        # Actual complete scientific field/undefined/support admission, not just hashes.
        arrays=outputs.admit(target,result,meta,budget);del arrays
        target.chmod(0o500)
        return {'schema':'tms_figure2b_sealed_capture_v1','output':result,'members':captured,
            'source_directory_identity':list(before),'member_count':37,'directory':str(target)}
    except BaseException as error:root_failure=error;raise
    finally:close_owned([fd],root_failure)
