"""Bounded identities, original-clock accounting and externally selected authority."""
import hashlib, json, math, os, stat, time
from pathlib import Path
class Refusal(ValueError): pass
def need(value, reason):
    if not value: raise Refusal(reason)
def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
def digest(value): return hashlib.sha256(canonical(value)).hexdigest()
def byte_pin(raw): return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
def pin_ok(row):
    return (type(row) is dict and type(row.get('bytes')) is int and row['bytes'] >= 0
            and type(row.get('sha256')) is str and len(row['sha256']) == 64
            and all(c in '0123456789abcdef' for c in row['sha256']))
def absolute(path):
    raw=os.fspath(path)
    need(type(raw) is str and raw.startswith('/') and '\\' not in raw and '\0' not in raw, 'canonical absolute path')
    need(raw=='/' or all(p not in ('','.','..') for p in raw.split('/')[1:]), 'raw path aliases forbidden')
    p=Path(raw);need(all(not x.is_symlink() for x in (p,*p.parents)), 'symlink path forbidden')
    return p
def capture(path, cap, expected=None, budget=None):
    p=absolute(str(Path(path).absolute()));need(type(cap) is int and cap>=0,'finite cap')
    if budget: budget.reserve(read=cap+1, hashed=cap if expected is not None else 0)
    fd=None;parts=[];n=0;hashed=0
    try:
        fd=os.open(p, os.O_RDONLY|os.O_NONBLOCK|os.O_NOFOLLOW)
        a=os.fstat(fd);need(stat.S_ISREG(a.st_mode) and a.st_nlink==1 and a.st_size<=cap,'ordinary single-link bounded input')
        while True:
            if budget: budget.tick()
            b=os.read(fd,min(65536,cap+1-n))
            if not b: break
            parts.append(b);n+=len(b);need(n<=cap,'capture exceeded cap')
        z=os.fstat(fd)
        need((a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns,a.st_ctime_ns)==
             (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns) and n==a.st_size,
             'input changed during capture')
        raw=b''.join(parts)
        if expected is not None:
            need(pin_ok(expected),'valid expected identity')
            actual=byte_pin(raw);hashed=n
            need(actual=={k:expected[k] for k in ('bytes','sha256')},'exact captured identity')
        return raw
    finally:
        # Known completed I/O survives identity, stability and deadline failures.
        # Reservation already bounds each chunk. Recording cannot mask its error.
        if budget: budget.record_known(read=n,hashed=hashed)
        if fd is not None: os.close(fd)
def json_bytes(raw):
    def pairs(items):
        d={}
        for k,v in items: need(k not in d,'duplicate JSON key');d[k]=v
        return d
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:need(False,'nonfinite JSON'))
def read_json(path,cap=4*1024**2,expected=None,budget=None):
    return json_bytes(capture(path,cap,expected,budget))
def write_new(path,raw,budget=None):
    p=absolute(str(Path(path).absolute()));need(type(raw) is bytes,'bytes required')
    if budget:budget.reserve(written=len(raw));budget.tick()
    fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        offset=0
        while offset<len(raw):
            if budget:budget.tick()
            n=os.write(fd,raw[offset:]);need(n>0,'short write');offset+=n
            if budget:budget.record_known(written=n)
        if budget:budget.tick()
        os.fsync(fd)
        if budget:budget.tick()
    finally:os.close(fd)
    return {'path':str(p),**byte_pin(raw)}
def save(path,value,budget=None): return write_new(path,canonical(value)+b'\n',budget)
def descriptor(path,cap,budget=None):
    raw=capture(path,cap,budget=budget)
    if budget:budget.reserve(hashed=len(raw));budget.observe(hashed=len(raw))
    return {'path':str(Path(path).absolute()),**byte_pin(raw)}

class Budget:
    """All attempted reservations remain charged, including failed operations.
    Hard physical memory/storage and whole-process accounting are external gates.
    """
    KEYS=('read','written','hashed','process_starts','fits','model_calls','input_tokens','output_tokens','cpu_ns')
    def __init__(self,limits,started_ns,deadline_ns,clock=time.monotonic_ns):
        need(set(limits)==set(self.KEYS) and all(type(v)is int and v>=0 for v in limits.values()),'all finite cumulative dimensions')
        need(type(started_ns)is int and type(deadline_ns)is int and deadline_ns>started_ns,'one original interval')
        self.limits=dict(limits);self.reserved=dict.fromkeys(self.KEYS,0);self.actual=dict.fromkeys(self.KEYS,0)
        self.started=started_ns;self.deadline=deadline_ns;self.evidence_deadline=deadline_ns;self.clock=clock;self.events=[];self.tick()
    def tick(self):
        need(self.clock()<self.deadline,'original deadline reached')
    def reserve(self,**values):
        self.tick();need(set(values)<=set(self.KEYS),'unknown reservation')
        need(all(type(v)is int and v>=0 and self.reserved[k]+v<=self.limits[k] for k,v in values.items()),'cumulative budget exceeded before operation')
        for k,v in values.items():self.reserved[k]+=v
        self.events.append({'kind':'reserve','at_ns':self.clock(),'values':values})
    def record_known(self,**values):
        need(set(values)<=set(self.KEYS) and all(type(v)is int and v>=0 for v in values.values()),'nonnegative observed costs')
        for k,v in values.items():self.actual[k]+=v
        self.events.append({'kind':'observed','at_ns':self.clock(),'values':values})
    def observe(self,**values):
        self.record_known(**values)
        need(all(self.actual[k]<=self.reserved[k] for k in self.KEYS),'observed cost exceeded reservation')
    def compact(self):
        return {'started_ns':self.started,'deadline_ns':self.deadline,'evidence_deadline_ns':self.evidence_deadline,
                'observed_at_ns':self.clock(),'limits':dict(self.limits),'reserved':dict(self.reserved),
                'observed':dict(self.actual),'event_count':len(self.events),
                'overruns':{k:self.actual[k]-self.reserved[k] for k in self.KEYS if self.actual[k]>self.reserved[k]},
                'unknown_physical_OS_IO':True}
    def report(self):
        return {'started_ns':self.started,'deadline_ns':self.deadline,'observed_at_ns':self.clock(),
                'reserved':self.reserved,'observed':self.actual,'events':self.events}

def qualified(record, source_id, profile_pin, evidence_root):
    """The record is an operator-selected immutable input, never actor supplied.
    Exact records do not themselves establish independent empirical qualification.
    """
    need(record.get('schema')=='neural056_execution_selection_v1' and record.get('build_only') is False,
         'scientific execution has no selected authority')
    need(record.get('source_id')==source_id and record.get('profile')==profile_pin,'source/profile selection mismatch')
    required=('source_and_coordinate_alignment','checkpoint_and_feature_backend','native_numerical_parity',
              'root_issuer_and_custody','cgroup_subtree','read_only_mounts','output_quota','provider_abi',
              'reference_competence','whole_programme_capacity')
    need(set(record.get('evidence',{}))==set(required),'all independent qualification records required')
    root=absolute(evidence_root)
    for key,row in record['evidence'].items():
        p=absolute(row['path']);need(p.is_relative_to(root),'qualification outside selected root')
        capture(p,4*1024**2,row)
    return record

class ScopedBudget:
    """One case ceiling nested in the whole attempt; no refund on failures."""
    def __init__(self,parent,limits,wall_ns,clock=time.monotonic_ns,terminal_ns=0):
        start=clock();self.parent=parent
        evidence=min(parent.deadline,start+wall_ns)
        self.inner=Budget(limits,start,evidence-terminal_ns,clock)
        self.inner.evidence_deadline=evidence;self.evidence_deadline=evidence
        self.deadline=self.inner.deadline
    def tick(self):self.parent.tick();self.inner.tick()
    def reserve(self,**values):self.inner.reserve(**values);self.parent.reserve(**values)
    def record_known(self,**values):
        self.inner.record_known(**values);self.parent.record_known(**values)
    def observe(self,**values):
        # Record at both levels before either ceiling may refuse.
        self.record_known(**values)
        for ledger in (self.inner,self.parent):
            if isinstance(ledger,ScopedBudget):ledger=ledger.inner
            need(all(ledger.actual[k]<=ledger.reserved[k] for k in ledger.KEYS),'observed scoped cost exceeded reservation')
    def compact(self):return self.inner.compact()
    def report(self):return self.inner.report()

