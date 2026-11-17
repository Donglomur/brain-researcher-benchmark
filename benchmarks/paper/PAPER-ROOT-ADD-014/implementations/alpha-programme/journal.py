"""One owned durable JSONL per phase, with a fixed prospective reservation.

Each append closes before returning; failure poisons this writer and no retry is
authorized. Event names and exact records survive for external recovery.
"""
import hashlib
import os
from pathlib import Path
import stat
from common import need, canonical, identity, ordinary, pin, mkdirs
from transport import sync

CAP=1024**2
EVENTS=512 # bounded one-file transport command journal

class Journal:
    def __init__(self,path,budget):
        self.path=ordinary(path);self.budget=budget;self.size=0;self.count=0;self.names=set();self.dead=False;self.digest=hashlib.sha256();self.last=None
        need(not self.path.exists(),'fresh owned journal');mkdirs(self.path.parent,budget)
        budget.metadata(CAP) # upper reservation, not an observed physical-write claim
        fd=os.open(self.path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        try:os.fsync(fd);self.last=identity(os.fstat(fd))
        finally:os.close(fd)
        sync(self.path.parent)
    def append(self,name,value):
        need(not self.dead and type(name)is str and 0<len(name)<=240 and name not in self.names,'fresh unique journal event')
        raw=canonical({'sequence':self.count,'name':name,'event':value})
        need(len(raw)<=1048576 and self.size+len(raw)<=CAP and self.count<EVENTS,'bounded complete journal')
        self.budget.deadline();fd=None;primary=None;self.dead=True
        try:
            fd=os.open(self.path,os.O_WRONLY|os.O_APPEND|os.O_NOFOLLOW|os.O_NONBLOCK)
            before=os.fstat(fd);need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and identity(before)==self.last and before.st_size==self.size,'same exclusively owned append journal')
            data=memoryview(raw)
            while data:
                self.budget.deadline();n=os.write(fd,data);need(n>0,'complete durable journal append');data=data[n:]
            os.fsync(fd);after=os.fstat(fd);need(after.st_size==self.size+len(raw),'exact journal append extent')
            stamp=identity(after)
        except BaseException as e:self.dead=True;primary=e;raise
        finally:
            if fd is not None:
                try:os.close(fd)
                except BaseException as e:
                    self.dead=True
                    if primary is None:raise
                    primary.add_note('Journal close uncertainty: '+type(e).__name__)
        need(identity(self.path.lstat())==stamp,'same journal after closed append')
        self.last=stamp;self.size+=len(raw);self.count+=1;self.names.add(name);self.digest.update(raw);self.dead=False
    def finish(self):
        need(not self.dead and self.count>0 and identity(self.path.lstat())==self.last,'complete unpoisoned owned journal')
        sync(self.path.parent);self.budget.deadline()
        return {'bytes':self.size,'sha256':self.digest.hexdigest(),'events':self.count,'reserved_bytes':CAP}
