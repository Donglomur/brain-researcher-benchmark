"""Strict source schemas, immutable bodies and full attempted-work accounting."""
import hashlib
import importlib.util
import math
import os
import stat
import sys
from pathlib import Path
from .physical.wire import (Refusal, need, integer, token, relative, encode,
    decode, body_pin, pin, check_pin, Ledger, Cleanup)

PEOPLE=tuple(str(i) for i in range(26))
CHANNELS=tuple('Fp1 AF3 F7 F3 FC1 FC5 T7 C3 CP1 CP5 P7 P3 Pz PO3 O1 Oz O2 PO4 P4 P8 CP6 CP2 C4 T8 FC6 FC2 F4 F8 AF4 Fp2 Fz Cz'.split())
MODES=('P','I'); VIEWS=('B','E','H','EH')
PREDICTION_POLICIES=tuple(m+'/'+v for m in MODES for v in VIEWS)
GLOBAL_POLICIES=PREDICTION_POLICIES+('reconstruction/P','reconstruction/I')

def fields(obj,names):
    need(type(obj) is dict and set(obj)==set(names),'exact fields: '+','.join(names));return obj

def finite(x):
    need(type(x) in (int,float) and math.isfinite(x),'finite numerical scalar');return float(x)

def probability(x):
    x=finite(x);need(0<=x<=1,'forecast in [0,1]');return x

def unique(rows,key):
    need(type(rows) is list,'ordered row list');out={}
    for row in rows:
        value=row[key];need(value not in out,'duplicate '+key);out[value]=row
    return out

def same_roster(actual,expected):
    need(len(actual)==len(set(actual)) and set(actual)==set(expected),'complete unique support')

def hash_source_tree(root,records,ledger):
    result={}
    for record in records:
        name=relative(record['path']);expected={k:record[k] for k in ('bytes','sha256')}
        raw=read_body(Path(root)/name,expected,ledger,expected['bytes'])
        result[name]=body_pin(raw)
    return pin(result,max(1048576,len(result)*2048))

def read_body(path,expected,ledger,cap):
    check_pin(expected);need(expected['bytes']<=integer(cap,1),'body extent before allocation')
    ledger.reserve({'read_bytes':expected['bytes']+1},'immutable body read')
    with Cleanup(ledger) as cleanup:
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW);cleanup.defer('close immutable body',lambda:os.close(fd))
        before=os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size==expected['bytes'],'ordinary exact body')
        with ledger.live(2*(expected['bytes']+1),'immutable body copies'):
            parts=[];total=0
            while total<=expected['bytes']:
                ledger.tick();block=os.read(fd,min(65536,expected['bytes']+1-total))
                if not block:break
                total+=len(block);parts.append(block)
            raw=b''.join(parts)
        after=os.fstat(fd)
        need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==
             (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns),'body unchanged during read')
        need(body_pin(raw)==expected,'exact body identity');return raw

class Bodies:
    """Exclusive immutable source/derived bodies; never load pickle or run code."""
    def __init__(self,root,ledger,cap):
        self.root=Path(root);self.ledger=ledger;self.cap=integer(cap,1)
        need(self.root.is_dir() and not self.root.is_symlink(),'admitted ordinary body root')
        self.records={}
    def put(self,name,raw,*,cutoff='scientific'):
        name=relative(name);need('/' not in name and type(raw) is bytes and len(raw)<=self.cap,'flat bounded complete body')
        self.ledger.reserve({'write_bytes':len(raw),'retained_bytes':len(raw)},'exclusive retained body',cutoff=cutoff)
        with Cleanup(self.ledger) as cleanup:
            parent=os.open(self.root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
            cleanup.defer('close body parent',lambda:os.close(parent))
            cleanup.defer('fsync body parent',lambda:os.fsync(parent))
            fd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400,dir_fd=parent)
            cleanup.defer('close retained body',lambda:os.close(fd));view=memoryview(raw)
            while view:
                self.ledger.tick(cutoff);n=os.write(fd,view);need(n>0,'complete retained write');view=view[n:]
            os.fsync(fd)
        self.ledger.tick(cutoff) # Includes file/parent fsync and every cleanup attempt.
        descriptor={'path':name,**body_pin(raw)};self.records[name]=descriptor;return descriptor
    def put_json(self,name,value,*,cutoff='scientific'):return self.put(name,encode(value,self.cap),cutoff=cutoff)
    def read(self,descriptor):return read_body(self.root/relative(descriptor['path']),{k:descriptor[k] for k in ('bytes','sha256')},self.ledger,self.cap)


class Work:
    def __init__(self,planned,ledger):
        need(len(planned)==len(set(planned)),'unique complete planned work');self.ledger=ledger
        self.rows={k:{'id':k,'status':'planned','attempts':[]} for k in planned}
    def begin(self,key,inputs):
        row=self.rows[key];need(row['status']=='planned','one declared attempt without hidden retries')
        self.ledger.tick();row['status']='running';row['attempts'].append({'inputs':inputs,'started_ns':self.ledger.clock()})
    def finish(self,key,outputs):
        row=self.rows[key];need(row['status']=='running','finish own attempt');self.ledger.tick()
        row.update(status='complete',outputs=outputs,finished_ns=self.ledger.clock())
    def fail(self,key,error):
        row=self.rows[key];need(row['status']=='running','fail own attempt');self.ledger.fail(key,error)
        row.update(status='failed',error_type=type(error).__name__,error=str(error)[:1024])
    def block(self,key,dependencies):
        row=self.rows[key];need(row['status']=='planned' and dependencies,'explicit blocked node');row.update(status='blocked',dependencies=dependencies)
    def report(self):return list(self.rows.values())
