"""Pre-admitted evidence capacity within original totals and the original lifetime."""
import os,sys,hashlib
from pathlib import Path
from .common import exact,need,canonical,pin,absolute
class EvidenceFailure(RuntimeError):
    def __init__(self,primary,observation):
        super().__init__("Original failure evidence incomplete: "+canonical(observation).decode().strip())
        self.primary=primary;self.observation=observation
class Reserve:
    def __init__(self,ledger,policy):
        exact(policy,["write_bytes","wall_seconds","terminal_bytes","job_receipt_bytes","provider_receipt_bytes"])
        for key,value in policy.items():need(type(value) is int and value>0,"Positive evidence reservation")
        need(policy["wall_seconds"]<ledger.limits["wall_seconds"],"Closure is part of original wall budget")
        need(policy["terminal_bytes"]<=policy["write_bytes"],"Terminal fits reserved total")
        ledger.charge("write_bytes",policy["write_bytes"],"independent failure/stream/closure reservation")
        ledger.work_deadline=ledger.deadline-policy["wall_seconds"]
        self.ledger=ledger;self.policy=policy;self.remaining=policy["write_bytes"];self.allocations=[];self.clock=ledger.clock
        self.deadline=ledger.deadline;self.terminal=self.allocate(policy["terminal_bytes"],"whole programme terminal",ledger)
    def allocate(self,cap,role,budget):
        need(type(cap) is int and cap>0 and cap<=self.remaining,"Pre-reserved evidence capacity exhausted")
        budget.reserved_write(cap,role);self.remaining-=cap
        token={"cap":cap,"role":role,"used":0,"claimed":False,"failures":[]}
        self.allocations.append(token);return token
    def live(self):need(self.clock()<self.deadline,"Original evidence cutoff; no new interval")
    def write(self,token,path,body):
        need(type(body) is bytes and not token["claimed"] and len(body)<=token["cap"],"Bounded one-time evidence body")
        token["claimed"]=True;fd=None
        try:
            self.live();fd=os.open(absolute(path),os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            sent=0
            while sent<len(body):
                self.live();n=os.write(fd,body[sent:]);need(n>0,"Original evidence write progress");sent+=n;token["used"]+=n
                self.ledger.observe("write_bytes",n,token["role"])
            self.live();os.fsync(fd);self.live()
            return {"path":str(path),**pin(body),"timely":True}
        except BaseException as error:
            token["failures"].append({"type":type(error).__name__,"known_written_bytes":token["used"]})
            raise
        finally:
            if fd is not None:os.close(fd)
    def emit(self,token,path,value):
        # Reservation is already held before serialization. Oversize never extends it.
        return self.write(token,path,canonical(value))
    def stream(self,path,cap,budget,role):
        budget.charge("read_bytes",cap+65536,role+" full original stream plus one overflow-read boundary")
        token=self.allocate(cap,role,budget)
        return Stream(self,token,path,budget)
    def summary(self):
        return {"policy":self.policy,"remaining_reserved_bytes":self.remaining,"allocation_count":len(self.allocations),
                "known_written_bytes":sum(x["used"] for x in self.allocations),"allocation_sha256":pin(canonical(self.allocations))["sha256"],
                "original_deadline":self.deadline,"own_terminal_publication_not_self_attested":True}
    def terminal_or_fallback(self,path,value,primary):
        try:
            need(path is not None,"No admitted private output custody; outer fallback only")
            return self.emit(self.terminal,path,value)
        except BaseException as secondary:
            observation={"schema":"neural047-original-failure-evidence-fallback-v2","primary":None if primary is None else {"type":type(primary).__name__,"message":str(primary)[:512]},
                         "secondary":{"type":type(secondary).__name__,"message":str(secondary)[:256]},
                         "known":value,"terminal_persistence":"failed_or_uncertain","scientific_success":False,
                         "scope":"Reserved original outer stderr fallback; not a timely file or a new work interval"}
            body=canonical(observation)
            if len(body)>self.terminal["cap"]:
                # The root retains all aggregate known costs and exact prior evidence refs;
                # full source value stays attached to the exception, never called persisted.
                observation["known"]={"accounting":value.get("accounting"),"completed":value.get("completed"),
                                      "failure":value.get("failure"),"method_summaries":value.get("method_summaries"),
                                      "original_value_pin":pin(canonical(value)),"full_value_in_exception_only":True}
                body=canonical(observation)
            try:
                need(len(body)<=self.terminal["cap"],"Fallback exceeds original outer reservation")
                sys.stderr.write("NEURAL047_FAILURE_OBSERVATION "+body.decode());sys.stderr.flush()
            except BaseException as tertiary:
                observation["fallback_persistence_error"]=type(tertiary).__name__
            error=EvidenceFailure(primary,observation);error.full_original_observation=value
            raise error from (primary if primary is not None else secondary)
class Stream:
    def __init__(self,reserve,token,path,budget):
        self.reserve=reserve;self.token=token;self.path=absolute(path);self.budget=budget
        self.seen=0;self.retained=0;self.seen_hash=hashlib.sha256();self.kept_hash=hashlib.sha256()
        self.errors=[];self.fsync_returned=False;self.closed=False;self.eof=False
        reserve.live();self.fd=os.open(self.path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        token["claimed"]=True
    def append(self,data):
        # These facts are known already: never charge/refuse before preserving them.
        self.seen+=len(data);self.seen_hash.update(data)
        self.budget.observe("read_bytes",len(data),self.token["role"])
        keep=data[:max(0,self.token["cap"]-self.retained)]
        try:
            sent=0
            while sent<len(keep):
                self.reserve.live();n=os.write(self.fd,keep[sent:]);need(n>0,"Original stream write progress")
                part=keep[sent:sent+n];sent+=n;self.retained+=n;self.token["used"]+=n;self.kept_hash.update(part)
                self.budget.observe("write_bytes",n,self.token["role"])
            need(self.seen<=self.token["cap"],"Original stream overflow; retained bounded prefix")
        except BaseException as error:
            self.errors.append({"type":type(error).__name__,"message":str(error)[:256]});raise
    def close(self,eof):
        self.eof=eof
        try:
            self.reserve.live();os.fsync(self.fd);self.fsync_returned=True;self.reserve.live()
        except BaseException as error:self.errors.append({"phase":"stream_fsync","type":type(error).__name__})
        finally:os.close(self.fd);self.closed=True
        return self.summary()
    def summary(self):
        return {"path":str(self.path),"seen_bytes":self.seen,"seen_sha256":self.seen_hash.hexdigest(),
                "retained_bytes":self.retained,"sha256":self.kept_hash.hexdigest(),"EOF":self.eof,
                "fsync_returned":self.fsync_returned,"closed":self.closed,"errors":self.errors,
                "within_original_interval":self.reserve.clock()<self.reserve.deadline}

