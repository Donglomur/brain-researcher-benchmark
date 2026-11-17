"""Shared strict metadata and accounting; import performs no scientific operation."""
import hashlib, json, math, os, re, stat, time
from pathlib import Path
from .legacy.delivery_io import exact, need, canonical, decode, check_pin
PIN_KEYS=("bytes","sha256")
def pin(body): return {"bytes":len(body),"sha256":hashlib.sha256(body).hexdigest()}
def object_pin(value): return pin(canonical(value))
def relative(name):
    need(type(name) is str and name and not name.startswith("/") and "\\" not in name and "\0" not in name
         and all(x not in ("",".","..") for x in name.split("/")),"Canonical relative path")
    return name
def absolute(path):
    p=Path(path);need(p.is_absolute() and str(p)==str(path) and all(x not in (".","..") for x in str(path).split("/")),"Canonical absolute path")
    need(not any(x.is_symlink() for x in (p,*p.parents)),"No symlink path")
    return p
class Ledger:
    """One original interval; all attempts, controls, tools and failures debit it."""
    def __init__(self,limits,clock=time.monotonic):
        exact(limits,["wall_seconds","read_bytes","write_bytes","provider_requests","input_tokens","output_tokens"])
        for key,value in limits.items():need(type(value) is int and value>0,"Positive integral selected limits")
        self.limits=dict(limits);self.used={k:0 for k in limits if k!="wall_seconds"}
        self.clock=clock;self.started=clock();self.deadline=self.started+limits["wall_seconds"];self.work_deadline=self.deadline;self.events=[]
        self.observed={k:0 for k in self.used};self.event_hash=hashlib.sha256();self.read_failures=[]
    def live(self):
        need(self.clock()<self.work_deadline,"Original programme work interval exhausted")
    def charge(self,kind,amount,role):
        need(kind in self.used and type(amount) is int and amount>=0,"Typed cost")
        self.live();need(self.used[kind]+amount<=self.limits[kind],"Cumulative "+kind+" exhausted")
        self.used[kind]+=amount;event={"kind":kind,"amount":amount,"role":role,"type":"reservation"}
        self.events.append(event);self.event_hash.update(canonical(event))
    def observe(self,kind,amount,role):
        need(kind in self.observed and type(amount) is int and amount>=0,"Known typed observation")
        self.observed[kind]+=amount;event={"kind":kind,"amount":amount,"role":role,"type":"observed"}
        self.events.append(event);self.event_hash.update(canonical(event))
    def reserved_write(self,amount,role):
        # EvidenceReserve already deducted this capacity from this root's total.
        need(type(amount) is int and amount>=0,"Known reserved root evidence")
    def record_read_failure(self,observation):self.read_failures.append(observation)
    def summary(self,compact=False):
        return {"limits":self.limits,"used":self.used,"elapsed_seconds":max(0,self.clock()-self.started),
                "observed":self.observed,"events":None if compact else self.events,"event_count":len(self.events),"event_sha256":self.event_hash.hexdigest(),
                "original_read_failures":self.read_failures,
                "original_deadline":self.deadline,"work_deadline":self.work_deadline,"unmeasured":"OS/Git internal physical I/O; runtime native counters reported separately"}
def read(path,expected,ledger,role,retain=True):
    h=hashlib.sha256();out=[];n=0;opened=False;eof=False
    try:
        check_pin(expected,2**63-1,empty=True);p=absolute(path)
        ledger.charge("read_bytes",expected["bytes"]+1,role)
        fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK);opened=True
        with os.fdopen(fd,"rb") as f:
            s=os.fstat(f.fileno());need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and s.st_size==expected["bytes"],"Exact single-link regular file")
            while True:
                ledger.live();b=f.read(min(1048576,max(1,expected["bytes"]-n+1)))
                if not b:eof=True;break
                n+=len(b);h.update(b);ledger.observe("read_bytes",len(b),role)
                if retain:out.append(b)
                need(n<=expected["bytes"],"File grew")
            t=os.fstat(f.fileno())
            need(all(getattr(s,k)==getattr(t,k) for k in ("st_dev","st_ino","st_size","st_nlink","st_mtime_ns","st_ctime_ns")),"Stable file")
        need(n==expected["bytes"] and h.hexdigest()==expected["sha256"],"Exact full file identity")
        return b"".join(out) if retain else dict(expected)
    except BaseException as error:
        observation={"path":str(path),"role":role,"opened":opened,"seen_bytes":n,"seen_sha256":h.hexdigest(),"EOF":eof,
                     "retained_in_memory_bytes":sum(map(len,out)),"failure_type":type(error).__name__,"expected":expected}
        ledger.record_read_failure(observation);error.original_read_observation=observation
        raise
def read_json(path,expected,ledger,role):
    return decode(read(path,expected,ledger,role))
def fresh_dir(path):
    p=absolute(path);need(p.parent.is_dir() and not p.exists(),"Fresh operator directory")
    p.mkdir(mode=0o700);return p
def observed_write(writer,body,ledger,role):
    """Credit only returned logical bytes; reservation and durable closure are separate."""
    try:n=writer(body)
    except BlockingIOError as error:
        n=getattr(error,"characters_written",0)
        need(type(n) is int and 0<=n<=len(body),"Known partial write progress")
        if n:ledger.observe("write_bytes",n,role)
        raise
    need(type(n) is int and 0<=n<=len(body),"Known returned write progress")
    ledger.observe("write_bytes",n,role)
    return n
def publish(path,value,ledger,role):
    p=absolute(path);body=canonical(value);ledger.charge("write_bytes",len(body),role)
    fd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,"wb") as f:
        ledger.live();n=observed_write(f.write,body,ledger,role);need(n==len(body),"Complete publication")
        ledger.live();f.flush();ledger.live();os.fsync(f.fileno())
    ledger.live();return pin(body)
def number(v):return type(v) in (int,float) and math.isfinite(v)

