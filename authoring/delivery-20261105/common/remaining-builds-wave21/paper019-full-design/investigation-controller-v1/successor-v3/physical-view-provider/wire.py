"""Bounded plain wire values and attempted-work accounting, no production I/O."""
import hashlib
import json
import math
import time
from contextlib import contextmanager

class Refusal(ValueError): pass

def need(ok, reason):
    if not ok: raise Refusal(reason)

def integer(x, minimum=0):
    need(type(x) is int and x>=minimum,'exact integer extent');return x

def token(x):
    need(type(x) is str and 0<len(x)<=128 and all(c.isascii() and (c.isalnum() or c in '-_.') for c in x),'opaque token')
    return x

def relative(x):
    need(type(x) is str and 0<len(x)<=1024 and '\\' not in x and
         all(p not in ('','..','.') for p in x.split('/')),'canonical relative name')
    return x

def plain(value, depth=0):
    need(depth<=32,'wire depth')
    if value is None or type(value) in (str,int,bool):return
    if type(value) is float:need(math.isfinite(value),'finite wire float');return
    if type(value) is list:
        for x in value:plain(x,depth+1)
        return
    if type(value) is dict:
        need(all(type(k) is str for k in value),'string keys')
        for x in value.values():plain(x,depth+1)
        return
    raise Refusal('plain wire value')

def encode(value, cap):
    integer(cap,1);plain(value)
    stack=[value];nodes=0;lower=0
    while stack:
        item=stack.pop();nodes+=1;need(nodes<=cap,'metadata node bound')
        if type(item) is str:
            lower+=2
            for c in item:
                code=ord(c);lower+=2 if c in '\\"\b\f\n\r\t' else (1 if 32<=code<127 else (6 if code<=65535 else 12))
                need(lower<=cap,'metadata string bound before encoding')
        elif type(item) is dict:
            lower+=2+max(0,len(item)-1)+len(item);stack.extend(item.keys());stack.extend(item.values())
        elif type(item) is list:lower+=2+max(0,len(item)-1);stack.extend(item)
        else:lower+=1
        need(lower<=cap,'metadata minimum extent')
    raw=json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()
    need(len(raw)<=cap,'encoded metadata cap');return raw

def decode(raw, cap):
    need(type(raw) is bytes and len(raw)<=integer(cap,1),'bounded wire bytes')
    def pairs(items):
        result={}
        for k,v in items:need(k not in result,'duplicate wire key');result[k]=v
        return result
    def bad(value):raise Refusal('nonfinite JSON')
    value=json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_constant=bad);plain(value);return value

def body_pin(raw):
    need(type(raw) is bytes,'exact bytes');return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

def pin(value, cap=1048576):return body_pin(encode(value,cap))

def check_pin(value):
    need(type(value) is dict and set(value)=={'bytes','sha256'},'pin schema');integer(value['bytes'])
    need(type(value['sha256']) is str and len(value['sha256'])==64 and all(c in '0123456789abcdef' for c in value['sha256']),'sha256')
    return value

class Ledger:
    """Selected logical counters only; physical unknowns remain explicit."""
    def __init__(self, limits, origin_ns, scientific_ns, closeout_ns, outer_ns, clock=time.monotonic_ns):
        need(type(limits) is dict and {'read_bytes','write_bytes','retained_bytes','live_bytes','processes','requests'}<=set(limits), 'all counter limits')
        need(all(type(k) is str and k for k in limits),'named counters')
        self.limits={k:integer(v,1) for k,v in limits.items()};self.used={k:0 for k in limits}
        self.origin=integer(origin_ns,1);self.scientific=integer(scientific_ns,1)
        self.closeout=integer(closeout_ns,1);self.outer=integer(outer_ns,1)
        need(self.origin<self.scientific<self.closeout<self.outer,'distinct original cutoffs')
        self.clock=clock;self.failures=[];self.unknown=['total physical filesystem I/O','total process RSS','kernel and imported-code work']
        self.live_current=0;self.live_tokens={};self.live_serial=0
        self.tick()

    def tick(self, phase='scientific'):
        deadline={'scientific':self.scientific,'closeout':self.closeout,'outer':self.outer}[phase]
        now=integer(self.clock(),1);need(self.origin<=now<deadline,'original strict '+phase+' cutoff');return now

    def reserve(self, charges, phase, *, cutoff='scientific'):
        self.tick(cutoff);need(type(charges) is dict and set(charges)<=set(self.used) and 'live_bytes' not in charges,'known cumulative charges; live requires acquire/release')
        for n in charges.values():integer(n)
        for k,n in charges.items():self.used[k]+=n
        exceeded=[k for k in self.used if self.used[k]>self.limits[k]]
        if exceeded:
            self.failures.append({'phase':phase,'charges':dict(charges),'exceeded':exceeded})
            raise Refusal('attempted allocation exceeded')

    def acquire_live(self, amount, phase, *, cutoff='scientific'):
        self.tick(cutoff);integer(amount);self.live_serial+=1;token=self.live_serial
        self.live_tokens[token]=amount;self.live_current+=amount
        self.used['live_bytes']=max(self.used['live_bytes'],self.live_current)
        if self.live_current>self.limits['live_bytes']:
            self.failures.append({'phase':phase,'live_attempted':amount,'live_current':self.live_current})
            # The attempt is retained in peak accounting but never allocated.
            self.live_current-=amount;del self.live_tokens[token]
            raise Refusal('attempted live allocation exceeded')
        return token

    def release_live(self, token):
        need(type(token) is int and token in self.live_tokens,'owned unreleased live token')
        self.live_current-=self.live_tokens.pop(token)

    @contextmanager
    def live(self, amount, phase, *, cutoff='scientific'):
        token=self.acquire_live(amount,phase,cutoff=cutoff)
        with Cleanup(self) as cleanup:
            cleanup.defer('release live reservation',lambda:self.release_live(token))
            yield

    def note_unknown(self, dimension):
        need(type(dimension) is str and dimension,'unknown dimension')
        if dimension not in self.unknown:self.unknown.append(dimension)

    def fail(self, phase, error):
        self.failures.append({'phase':str(phase)[:192],'type':type(error).__name__,
                              'message':str(error).encode('utf-8','replace')[:1024].decode('utf-8','replace')})

    def report(self):
        return {'selected_logical_counters':dict(self.used),'limits':dict(self.limits),
                'failures':list(self.failures),'unknown':list(self.unknown),'resources_complete':False,
                'live_current_bytes':self.live_current,'outstanding_live_tokens':len(self.live_tokens),
                'origin_ns':self.origin,'scientific_deadline_ns':self.scientific,
                'closeout_deadline_ns':self.closeout,'outer_deadline_ns':self.outer}


class Cleanup:
    """Owned cleanup only, in deterministic LIFO order, without masking failure.

    Every registration is removed before its one attempt. In particular an
    uncertain close is never retried against a potentially reused descriptor.
    These actions cannot supply scientific results or observation authority.
    """
    def __init__(self, ledger=None, record=None):
        self.ledger=ledger;self.record=record;self.pending={};self.serial=0

    def __enter__(self):return self

    def defer(self, label, action):
        need(type(label) is str and label and callable(action),'named owned cleanup')
        self.serial+=1;self.pending[self.serial]=(label,action);return self.serial

    def forget(self, key):
        need(key in self.pending,'owned cleanup transfer');self.pending.pop(key)

    def close_now(self, key):
        need(key in self.pending,'owned immediate cleanup')
        label,action=self.pending.pop(key)
        return action()

    @staticmethod
    def _descriptor(label, error):
        try:message=str(error)[:1024]
        except BaseException:message='<exception message unavailable>'
        result={'operation':label,'type':type(error).__name__,'message':message}
        nested=getattr(error,'ach_cleanup_errors',None)
        if type(nested) is list:result['nested_cleanup_errors']=list(nested)
        return result

    def run(self, primary=None):
        first=primary;secondary=[]
        for key in reversed(tuple(self.pending)):
            label,action=self.pending.pop(key)
            try:action()
            except BaseException as error:
                descriptor=self._descriptor(label,error)
                if self.record is not None:self.record.setdefault('cleanup_failures',[]).append(descriptor)
                if first is None:first=error
                else:secondary.append(descriptor)
                if self.ledger is not None:
                    try:self.ledger.fail(label,error)
                    except BaseException as report_error:
                        report=self._descriptor(label+'/failure_record',report_error)
                        secondary.append(report)
                        if self.record is not None:self.record.setdefault('cleanup_failures',[]).append(report)
        if first is not None and secondary:
            try:first.ach_cleanup_errors=list(getattr(first,'ach_cleanup_errors',[]))+secondary
            except BaseException:pass
        if primary is None and first is not None:raise first

    def __exit__(self, typ, error, traceback):
        self.run(error);return False
