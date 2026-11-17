"""Strict source-only reference artifact contracts; no I/O on import."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat

ID = re.compile(r'[0-9a-f]{24}\Z')
SHA = re.compile(r'[0-9a-f]{64}\Z')
STRONG_GRID = (.01,.03,.1,.2,.3,.4,.5,.6,.7,.8,.9,.95,.99)
MONTAGE_GRID = (.0001,.0003,.001,.003,.01,.03,.1,.3,.5,1.0)
GRID = tuple([{'kind':'logistic','lambda':v} for v in (.0001,.01,1.)] +
             [{'kind':'trees','depth':d,'min_leaf':l,'trees':256} for d in (16,32) for l in (32,128,512)])

def need(ok, message):
    if not ok: raise ValueError(message)

def integer(v, minimum=0, maximum=2**53-1):
    return type(v) is int and minimum <= v <= maximum

def finite(v):
    try:return type(v) in (int,float) and math.isfinite(v)
    except OverflowError:return False

def canonical(v):
    return json.dumps(v,sort_keys=True,ensure_ascii=True,separators=(',',':'),allow_nan=False).encode()

def pin(b): return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}

def pairs(items):
    d={}
    for k,v in items:
        need(k not in d,'duplicate JSON key');d[k]=v
    return d

def parse(b):
    return json.loads(b,object_pairs_hook=pairs,parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))

def exact(obj, keys): need(type(obj) is dict and set(obj)==set(keys),'exact fields: '+','.join(keys))

def descriptor(d, path=True):
    exact(d,('path','bytes','sha256') if path else ('bytes','sha256'))
    need(integer(d['bytes'],1) and type(d['sha256']) is str and SHA.fullmatch(d['sha256']),'exact positive byte/hash descriptor')
    if path:
        p=Path(d['path']);need(p.is_absolute() and not any(q.is_symlink() for q in (p,*p.parents)),'absolute ordinary source path')
    return d

def bootstrap_floor(request_descriptor,reference_source_files):
    """Pure metadata floor; never stats/reads a path or opens task data."""
    exact(request_descriptor,('path','bytes','sha256'));need(integer(request_descriptor['bytes'],1),'request extent')
    need(type(reference_source_files) is list and len(reference_source_files)==9,'manifest plus8 reference source files')
    members={}
    for d in reference_source_files:
        exact(d,('path','bytes','sha256'));need(type(d['path']) is str and integer(d['bytes'],1) and type(d['sha256']) is str and SHA.fullmatch(d['sha256']),'pure source descriptor')
        name=Path(d['path']).name;need(name not in members,'unique source basename');members[name]=d
    need(set(members)=={'SOURCE_MANIFEST.json','common.py','contracts.py','event_protocol.py','features.py','learners.py','math_core.py','reference_cli.py','selection.py'},'complete exact source closure')
    return request_descriptor['bytes']+sum(d['bytes'] for d in members.values())+members['reference_cli.py']['bytes']+10


def open_exact(d):
    descriptor(d);p=Path(d['path']);fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK);before=os.fstat(fd)
    try:need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size==d['bytes'],'ordinary exact source extent')
    except BaseException:os.close(fd);raise
    return p,fd,before


def unchanged(p,fd,before):
    after=os.fstat(fd);named=p.lstat();fields=('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_mode','st_nlink')
    need(all(getattr(before,k)==getattr(after,k)==getattr(named,k) for k in fields),'stable exact ordinary operand')


class IO:
    """Prospective logical reservations; no refund after an entered failure.

    reads/writes are debited extents, not physical-I/O measurements. Artifact
    bytes count successful complete output-file bodies. Unknown partial failure
    usage is covered by retained whole parent allocations, never reported zero.
    """
    def __init__(self,limits):
        fields=('max_rows','max_columns','max_design_bytes','max_model_bytes','max_nodes','max_input_bytes','max_output_bytes')
        exact(limits,fields);need(all(integer(limits[k],1) for k in fields),'positive prospective resource limits')
        self.limits=limits;self.reads=0;self.writes=0;self.artifact_bytes=0;self.source_reservations={'entry':0,'bootstrap':0,'imports':0}
    def charge_read(self,n):
        need(integer(n) and self.reads+n<=self.limits['max_input_bytes'],'whole logical read reservation');self.reads+=n
    def charge_write(self,n):
        need(integer(n) and self.writes+n<=self.limits['max_output_bytes'],'whole logical write reservation');self.writes+=n
    def check(self,d):
        descriptor(d);self.charge_read(d['bytes']+1);p,fd,before=open_exact(d);h=hashlib.sha256();n=0
        try:
            while n<=d['bytes']:
                block=os.read(fd,min(1048576,d['bytes']+1-n))
                if not block:break
                n+=len(block);h.update(block)
            unchanged(p,fd,before);need(n==d['bytes'] and h.hexdigest()==d['sha256'],'exact bounded source hash')
        finally:os.close(fd)
        return p
    def capture(self,d):
        descriptor(d);self.charge_read(d['bytes']+1);p,fd,before=open_exact(d)
        try:
            with os.fdopen(fd,'rb',closefd=False) as f:raw=f.read(d['bytes']+1)
            unchanged(p,fd,before);need(pin(raw)=={k:d[k] for k in ('bytes','sha256')},'complete bounded source capture')
        finally:os.close(fd)
        return raw
    def json(self,d):
        # Preserve both original full passes, and charge both independently.
        self.check(d);return parse(self.capture(d))
    def write_json(self,p,obj,cap=None):
        p=Path(p);need(not p.exists() and not p.is_symlink(),'fresh artifact');cap=min(cap or self.limits['max_output_bytes'],self.limits['max_output_bytes']-self.writes)
        h=hashlib.sha256();n=0
        with p.open('xb') as f:
            for chunk in json.JSONEncoder(sort_keys=True,ensure_ascii=True,separators=(',',':'),allow_nan=False).iterencode(obj):
                b=chunk.encode();need(n+len(b)<=cap,'complete artifact allocation; never truncate');self.charge_write(len(b));written=f.write(b);need(written==len(b),'whole JSON chunk write');h.update(b);n+=len(b)
            f.flush();os.fsync(f.fileno())
        self.artifact_bytes+=n
        return {'path':str(p.resolve()),'bytes':n,'sha256':h.hexdigest()}
    def complete(self,p,base):
        """Self-length fixed point, reserved before one canonical publication."""
        before=self.artifact_bytes;reserved=self.writes;size=0
        for _ in range(32):
            value=dict(base,read_reserved_bytes=self.reads,write_reserved_bytes=reserved+size,artifact_bytes_before_completion=before,completion_bytes=size,artifact_bytes_total=before+size,source_read_reservations=dict(self.source_reservations))
            updated=len(canonical(value))
            if updated==size:break
            size=updated
        else:raise ValueError('completion byte-ledger fixed point did not converge')
        need(reserved+size<=self.limits['max_output_bytes'],'complete publication included in original cap')
        result=self.write_json(p,value)
        need(result['bytes']==size and self.writes==reserved+size and self.artifact_bytes==before+size,'exact final completion/ledger publication')
        return result

def numpy():
    import numpy as np
    need(np.__version__=='2.2.6','prospective exact NumPy2.2.6; runtime remains unqualified')
    return np

class BoundedReader:
    """Header parser cannot consume beyond the already reserved full extent."""
    def __init__(self,f,cap):self.f=f;self.cap=cap
    def read(self,n=-1):
        remaining=self.cap-self.f.tell();need(remaining>=0,'bounded header cursor')
        return self.f.read(remaining if n<0 else min(n,remaining))
    def tell(self):return self.f.tell()


def load_array(io,d,shape,dtype):
    np=numpy();descriptor(d);count=math.prod(shape);target=np.dtype(dtype)
    need(target.kind in 'fiu' and integer(count,1) and d['bytes']<=count*target.itemsize+4096,'complete bounded primitive array before allocation')
    io.check(d);io.charge_read(d['bytes']+1);p,fd,before=open_exact(d)
    try:
        with os.fdopen(fd,'rb',closefd=False) as f:
            header=BoundedReader(f,d['bytes']+1);need(np.lib.format.read_magic(header)==(1,0),'frozen NPY1.0 format')
            declared,fortran,actual=np.lib.format.read_array_header_1_0(header,max_header_size=4096);offset=f.tell()
            need(declared==tuple(shape) and not fortran and actual==target and d['bytes']==offset+count*target.itemsize,'exact complete primitive extent before allocation')
            a=np.fromfile(f,dtype=target,count=count);need(a.size==count and not f.read(1),'complete array and reserved trailing probe')
        unchanged(p,fd,before)
    finally:os.close(fd)
    a=a.reshape(tuple(shape));need(a.flags.c_contiguous,'canonical array layout')
    for start in range(0,len(a),1024):need(bool(np.isfinite(a[start:start+1024]).all()),'finite full array')
    return a


class BoundedWriter:
    """File-like NumPy target without fileno; cannot bypass the byte bound."""
    def __init__(self,f,cap):self.f=f;self.cap=cap;self.bytes=0
    def write(self,b):
        view=memoryview(b).cast('B');n=view.nbytes;need(self.bytes+n<=self.cap,'reserved complete NPY write extent');self.bytes+=n
        result=self.f.write(view);need(result==n,'whole primitive array write');return result
    def flush(self):self.f.flush()
    def tell(self):return self.f.tell()


def save_array(io,p,values):
    np=numpy();p=Path(p);need(not p.exists(),'fresh array');need(values.dtype.kind in 'fiu' and values.flags.c_contiguous,'primitive contiguous output')
    reserve=int(values.nbytes)+256;io.charge_write(reserve)
    with p.open('xb') as f:
        writer=BoundedWriter(f,reserve);np.save(writer,values,allow_pickle=False);f.flush();os.fsync(f.fileno())
    bsize=p.stat().st_size;need(bsize==writer.bytes<=reserve,'bounded complete NPY body/header');io.artifact_bytes+=bsize
    # Output verification is an additional real read, never free accounting.
    io.charge_read(bsize+1);h=hashlib.sha256();n=0
    with p.open('rb') as f:
        while n<=bsize:
            b=f.read(min(1048576,bsize+1-n))
            if not b:break
            n+=len(b);h.update(b)
    need(n==bsize,'complete bounded output rehash')
    return {'path':str(p.resolve()),'bytes':bsize,'sha256':h.hexdigest()}


def signature(labels):
    need(type(labels) is list and 0<len(labels)<=512 and all(type(x) is str and 0<len(x)<=32 for x in labels),'complete exact channel multiset')
    return hashlib.sha256(json.dumps(sorted(labels),ensure_ascii=True,separators=(',',':')).encode()).hexdigest()

def records(doc,role,condition):
    exact(doc,('schema','role','records'));need(doc['schema']=='neural010-reference-records-v1' and doc['role']==role,'exact reference view role')
    rows=doc['records'];need(type(rows) is list and 0<len(rows)<=686,'complete bounded records')
    base={'patient_id','recording_id','duration_seconds','montage_id','channel_count','channel_labels','source_edf','target_free_projection'}
    extra=({'events'} if role in ('train','validation') else set()) | ({'eeg_features','feature_receipt'} if condition=='joint' else {'signal_features','feature_receipt'} if condition=='signal_reference' else set())
    seen=set();order=[];total=0
    for r in rows:
        exact(r,base|extra);pid,rid=r['patient_id'],r['recording_id']
        need(type(pid) is str and ID.fullmatch(pid) and type(rid) is str and ID.fullmatch(rid) and rid not in seen,'unique opaque biological/record identities');seen.add(rid);order.append((pid,rid))
        d=r['duration_seconds'];need(integer(d,1,86400),'full integral duration');total+=d
        need(integer(r['channel_count'],1,512) and r['channel_count']==len(r['channel_labels']) and r['montage_id']==signature(r['channel_labels']),'exact full channel/montage metadata')
        descriptor(r['source_edf'],False);descriptor(r['target_free_projection'],False)
        if 'events' in extra:
            ev=r['events'];need(type(ev) is list and len(ev)<=d,'bounded training intervals');end=0
            for pair in ev:
                need(type(pair) is list and len(pair)==2 and all(integer(v) for v in pair),'integral annotation pair');a,b=pair;need(end<=a<b<=d,'sorted disjoint in-record annotations');end=b
        for name in ('eeg_features','signal_features','feature_receipt'):
            if name in r:descriptor(r[name])
    need(order==sorted(order) and total<=10000000,'full canonical row order and original10M bound')
    return rows

def support_document(rows):
    return {'schema':'neural010-training-support-v1','dataset':'CHB-MIT','dataset_version':'1.0.0','records':[{k:r[k] for k in ('patient_id','recording_id','duration_seconds','source_edf','target_free_projection')} for r in rows]}

def authenticate_support(io,rows,d,digest,expected_people):
    need(expected_people in (21,22) and type(expected_people) is int,'exact21/22 support')
    people=sorted(set(r['patient_id'] for r in rows));need(len(people)==expected_people,'all declared biological training people')
    io.check(d);raw=io.capture(d);want=canonical(support_document(rows));need(raw==want and hashlib.sha256(raw).hexdigest()==digest==d['sha256'],'exact no-newline full training support; no sampled rows')
    return people
