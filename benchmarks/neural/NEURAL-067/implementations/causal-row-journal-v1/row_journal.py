"""NEURAL-067 operator-side row/journal primitives; no participant sandbox.

Recovered from the registered lifecycle source. Full-task roster admission,
transport, private targets, runtime selection and scientific grading are separate.
"""
import hashlib, math, os, struct, uuid
from pathlib import Path
from io_utils import capture, encoded, identity, need, ordinary, sync

ARMS=('neural','clock','neural_clock','shifted_neural_clock')
ROW=struct.Struct('<176Hdq')
ACTION=struct.Struct('<Q7d')
HEADER=4096
RECORD=160

class Rows:
    def __init__(self,path,pin,run,arm,n,budget):
        need(arm in ARMS and type(n)is int and 2<=n<=2713,'fixed full query geometry')
        need(pin['bytes']==n*ROW.size,'exact full cache extent')
        budget.read(pin['bytes']);self.raw=capture(path,pin['bytes'],pin)
        self.run=run;self.arm=arm;self.rows=n;self.i=0;self.token=uuid.uuid4().hex
        self.last_trial=None;self.start=None;self.first=None;self.last_time=None
    def next(self):
        if self.i==self.rows:return None
        values=ROW.unpack_from(self.raw,self.i*ROW.size);counts,t,trial=values[:176],values[176],values[177]
        need(all(0<=x<=255 for x in counts) and math.isfinite(t),'exact source count/clock domain')
        need(self.last_time is None or t>self.last_time,'strictly increasing source time')
        need(self.last_trial is None or trial>=self.last_trial,'unchanged monotonic trial identity')
        changed=self.last_trial is None or trial!=self.last_trial
        if changed:self.start=t
        if self.first is None:self.first=t
        observation={}
        if self.arm!='clock':observation['spikes']=list(counts)
        if self.arm!='neural':observation.update(elapsed_run_s=t-self.first,
            observed_segment_age_s=t-self.start,segment_started_now=changed)
        answer={'token':self.token,'ordinal':self.i,'observation':observation}
        self.i+=1;self.last_trial=trial;self.last_time=t
        return answer

class Journal:
    def __init__(self,path,run,arm,n,input_pin,budget):
        self.path=ordinary(path);self.budget=budget;self.rows=n;self.arm=arm;self.i=0
        self.previous=bytes(32);self.closed=False;self.fd=None;self.token=None;self.close_error=None
        need(arm in ARMS and type(n)is int and 2<=n<=2713,'full journal geometry')
        self.extent=HEADER+n*RECORD;budget.debit(self.extent)
        header=encoded({'schema':'neural067_action_journal_v1','run':run,'arm':arm,'rows':n,
            'input':input_pin,'encoding':'<Q7d32s32s32s',
            'record_bytes':RECORD,'header_bytes':HEADER})
        need(len(header)<=HEADER,'fixed journal header')
        self.fd=os.open(self.path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        try:self._write(header+bytes(HEADER-len(header)));os.fsync(self.fd);sync(self.path.parent)
        except BaseException as exc:self._abort(exc)
    def _write(self,b):
        while b:
            n=os.write(self.fd,b);need(n>0,'complete journal write');b=b[n:]
    def append(self,row,vector):
        try:self.budget.tick()
        except BaseException as exc:self._abort(exc)
        need(not self.closed and self.i<self.rows,'open bounded journal')
        need(set(row)=={'token','ordinal','observation'} and row['ordinal']==self.i,'exact current ordinal')
        if self.token is None:self.token=row['token']
        need(row['token']==self.token,'one run token')
        need(type(vector)is list and len(vector)==7 and all(type(x)in (int,float) and math.isfinite(x) for x in vector),'seven finite actions')
        prefix=ACTION.pack(self.i,*vector)+hashlib.sha256(encoded(row)).digest()+self.previous
        need(len(prefix)==128,'fixed action extent');checksum=hashlib.sha256(prefix).digest();raw=prefix+checksum
        try:
            self._write(raw);os.fsync(self.fd);self.budget.tick()
        except BaseException as exc:
            # A partial/unsynced record cannot safely be retried at this ordinal.
            self._abort(exc)
        # No in-memory progression or next observation is allowed until fsync succeeds.
        self.previous=checksum;self.i+=1
        return identity(raw)
    def close(self):
        # Logical closure is permanent even when the OS descriptor state is unknown.
        self.closed=True
        if self.fd is not None:
            fd,self.fd=self.fd,None
            try:os.close(fd)
            except BaseException as exc:
                self.close_error={'descriptor':fd,'type':type(exc).__name__,'descriptor_state':'unknown'}
                raise
    def _abort(self,original):
        try:self.close()
        except BaseException as cleanup:
            # Keep the original write/sync/deadline error primary and expose cleanup failure.
            raise original from cleanup
        raise original
    def seal(self):
        need(self.i==self.rows and not self.closed,'complete journal before seal')
        try:
            self.budget.tick();os.fchmod(self.fd,0o444);os.fsync(self.fd);self.close();sync(self.path.parent)
            self.budget.read(self.extent);b=capture(self.path,self.extent)
            need(len(b)==self.extent,'exact sealed journal length');self.budget.tick();return identity(b)
        except BaseException as exc:
            self._abort(exc)
