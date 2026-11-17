"""Inactive fixed protected operator intake; no operations occur on import.

This is the pre-Q1 reader, not RootChannel. The fixed installed entry alone
constructs its custodian after admitting the bounded trusted launch operand.
Qualification and original prefix transfer are distinct later fixed callers.
"""
import fcntl
import hashlib
import json
import math
import os
import stat
import time
from collections.abc import MutableMapping

DIMENSIONS=('read_bytes','write_bytes','work_units','retained_bytes','cpu_ns','wall_ns','process_starts')
_CUSTODIAN=object()

class BootstrapLogicalCounterView(MutableMapping):
    """One early view of the same original storage, adopted by Share unchanged."""
    keys_fixed=('read_bytes','write_bytes','work_units','retained_bytes')
    def __init__(self,owner):self.owner=owner;self.storage=owner.spent;self.protected_owner=None
    def __getitem__(self,key):
        require(key in self.keys_fixed,'fixed original logical dimension');return self.storage[key]
    def __setitem__(self,key,value):
        try:
            require(key in self.keys_fixed,'fixed original logical dimension');uint(value)
            require(value>=self.storage[key],'original cumulative charge cannot decrease')
            terminal=0 if self.terminal_entered() else self.owner.terminal[key]
            require(value+terminal<=self.owner.limits[key],'continuous original protected terminal reservation')
            self.storage[key]=value
        except BaseException as error:
            self.owner.retain(error,'BootstrapLogicalCounterView.__setitem__')
            transfer=getattr(self.owner.invocation,'transfer',None)
            parent=None if transfer is None else transfer.parent
            if parent is not None:
                from .early_resources import retain_source_failure
                raise retain_source_failure(parent,error,'BootstrapLogicalCounterView.__setitem__')
            raise
    def bind_partition_owner(self,owner):
        from .early_resources import EarlyResources
        transfer=self.owner.invocation.transfer
        require(self.protected_owner is None and type(owner)is EarlyResources and
                transfer.complete and transfer.custodian is self.owner and
                owner.parent is transfer.parent and owner.parent.owner is owner and
                owner.parent.share is transfer.share and transfer.share.spent is self and
                owner.seed is not None and owner.used is not None and
                owner.terminal_reserve==self.owner.terminal,
                'actual completed protected partition owner; identical original terminal reserve')
        self.protected_owner=owner
    def terminal_entered(self):
        owner=self.protected_owner
        if owner is None:return False
        transfer=self.owner.invocation.transfer
        require(transfer.parent.owner is owner and owner.parent is transfer.parent and
                transfer.share.spent is self and owner.terminal_reserve==self.owner.terminal,
                'same original registered protected owner and terminal obligation')
        return owner.terminal is True
    def __delitem__(self,key):raise TypeError('original counter cannot be deleted')
    def __iter__(self):return iter(self.keys_fixed)
    def __len__(self):return len(self.keys_fixed)

def require(value,message):
    if not value:raise ValueError(message)

def uint(value,minimum=0):
    require(type(value)is int and minimum<=value<=9007199254740991,'exact bounded integer')
    return value

def canonical(value):
    def walk(x,depth=0):
        require(depth<=64,'fixed complete metadata depth')
        if type(x)is dict:
            require(all(type(k)is str for k in x),'exact string keys')
            for k,v in x.items():walk(k,depth+1);walk(v,depth+1)
        elif type(x)is list:
            for v in x:walk(v,depth+1)
        elif type(x)is str:
            require('\0'not in x and not any(0xD800<=ord(c)<=0xDFFF for c in x),'no NUL/surrogates')
        elif type(x)is int:require(-9007199254740991<=x<=9007199254740991,'safe integer domain')
        elif type(x)is float:require(math.isfinite(x),'finite original schema numeric scalar')
        else:require(x is None or type(x)is bool,'no numeric coercion or arbitrary object')
    walk(value)
    return (json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)+'\n').encode('utf-8')

def parse_canonical(raw,cap):
    require(type(raw)is bytes and 0<len(raw)<=cap,'complete prior bounded metadata body')
    def pairs(items):
        out={}
        for k,v in items:
            require(k not in out,'no duplicate keys');out[k]=v
        return out
    value=json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,
                     parse_constant=lambda x:(_ for _ in ()).throw(ValueError('no nonfinite token')))
    require(canonical(value)==raw,'one exact canonical original encoding')
    return value

class BootstrapIntakeCustodian:
    def __init__(self,token,*,invocation,launch_anchor,profile):
        require(token is _CUSTODIAN,'fixed installed-entry issuer only')
        # Ownership precedes every fstat, flag, seal, clock or body-read effect.
        self.invocation=invocation;self.fd=197;self.raw_first=None;self.secondaries=[]
        self.launch_anchor=launch_anchor;self.profile=profile;self.read_prefixes=[]
        self.read_entered=False;self.close_entered=False;self.close_known=False
        self.read_attempts=0;self.observation=None;self.raw=None;self.body=None
        self.unknown=set();self.transferred=False;self.transfer_attempted=False
        self.spent=dict(launch_anchor['native_preentry_reserved']);self.completed={k:0 for k in DIMENSIONS}
        self.logical_counters=BootstrapLogicalCounterView(self)
        self.reservation=launch_anchor['original_reservation']
        self.limits=self.reservation['limits'];self.terminal=self.reservation['terminal_reserve']
        self.origin=self.reservation['original_origin_ns'];self.deadline=self.reservation['original_deadline_ns']
        self.native_prefix=None;self.first_wall=getattr(invocation,'started_wall',None)
        self.first_cpu=getattr(invocation,'started_cpu',None)
        self.last_wall=self.first_wall;self.last_cpu=self.first_cpu
        self.active_span=None if self.first_wall is None or self.first_cpu is None else (self.first_wall,self.first_cpu)
        self.requested_read_bytes=0
        invocation.intake=self

    def retain(self,error,site,unknown=None):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.secondaries.append((error,site))
        if unknown is not None:self.unknown.add(unknown)

    def reserve(self,dimension,amount):
        uint(amount);require(dimension in DIMENSIONS,'closed resource dimension')
        require(not self.transferred,'original custodian no longer independently spends after transfer')
        next_value=self.spent[dimension]+amount
        require(next_value+self.terminal[dimension]<=self.limits[dimension],'original protected terminal reservation')
        self.spent[dimension]=next_value

    def observe_clock(self):
        # Independent original dimensions retain either known value if the
        # other clock fails. Raw first is captured before projections.
        for name,fn in (('wall',time.monotonic_ns),('cpu',time.process_time_ns)):
            try:
                value=fn();uint(value)
                previous=getattr(self,'last_'+name)
                require(previous is None or value>=previous,'nondecreasing original clock')
                setattr(self,'last_'+name,value)
                if getattr(self,'first_'+name)is None:setattr(self,'first_'+name,value)
                if self.active_span is None and self.first_wall is not None and self.first_cpu is not None:
                    self.active_span=(self.first_wall,self.first_cpu)
                delta=value-getattr(self,'first_'+name)
                dimension='wall_ns'if name=='wall'else'cpu_ns'
                self.completed[dimension]=delta
                self.spent[dimension]=self.launch_anchor['native_preentry_reserved'][dimension]+delta
                if name=='wall':require(self.origin<=value<self.deadline,'same original root deadline')
                require(self.spent[dimension]+self.terminal[dimension]<=
                        self.limits[dimension],'original clock reservation including retained earlier allocation')
            except BaseException as e:self.retain(e,'operator_clock_'+name,name+'_ns')
        if self.raw_first is not None:raise self.raw_first

    def read_once(self):
        require(not self.read_entered and self.fd==197,'single original bounded intake occurrence')
        self.read_entered=True
        try:
            expected=self.launch_anchor['operator_selection_bytes'];uint(expected,1)
            require(expected<=min(1048576,self.profile['body_cap']),'unchanged installed body bound')
            attempts=(expected+65535)//65536+1
            require(attempts<=self.profile['attempt_cap'],'whole intake attempt schedule before body reads')
            self.reserve('read_bytes',((expected+65535)//65536)*min(expected,65536)+1)
            self.reserve('retained_bytes',expected*8+16384)
            self.reserve('work_units',expected*128+attempts*4096+16384)
            self.observe_clock()
            before=os.fstat(self.fd)
            require(stat.S_ISREG(before.st_mode)and before.st_size==expected,'exact original memfd extent')
            flags=fcntl.fcntl(self.fd,fcntl.F_GETFL)
            require(flags&os.O_ACCMODE==os.O_RDONLY,'actual readonly inherited file description')
            seals=fcntl.fcntl(self.fd,fcntl.F_GET_SEALS)
            required=fcntl.F_SEAL_SEAL|fcntl.F_SEAL_SHRINK|fcntl.F_SEAL_GROW|fcntl.F_SEAL_WRITE
            require(required==15 and seals&required==required,'actual immutable sealed original memfd')
            require(os.lseek(self.fd,0,os.SEEK_CUR)==0,'original beginning, no reset or replay')
            self.observation={'device':before.st_dev,'inode':before.st_ino,'mode':before.st_mode,
                              'size':before.st_size,'flags':flags,'seals':seals,'initial_offset':0}
            os.set_inheritable(self.fd,False)
            remaining=expected
            while remaining:
                require(self.read_attempts<attempts-1,'fixed complete body attempt ceiling')
                self.read_attempts+=1
                requested=min(65536,remaining);self.requested_read_bytes+=requested
                chunk=os.read(self.fd,requested)
                self.read_prefixes.append(chunk) # Raw actual return retained first.
                if type(chunk)is bytes:self.completed['read_bytes']+=len(chunk)
                require(type(chunk)is bytes and 0<len(chunk)<=remaining,'complete original body prefix')
                remaining-=len(chunk)
                self.observe_clock()
            self.read_attempts+=1
            self.requested_read_bytes+=1
            eof=os.read(self.fd,1);self.read_prefixes.append(eof)
            if type(eof)is bytes:self.completed['read_bytes']+=len(eof)
            require(eof==b'','positive EOF at exact admitted extent')
            after=os.fstat(self.fd)
            require((before.st_dev,before.st_ino,before.st_mode,before.st_size)==
                    (after.st_dev,after.st_ino,after.st_mode,after.st_size),'same original immutable object')
            self.raw=b''.join(self.read_prefixes)
            require(len(self.raw)==expected and hashlib.sha256(self.raw).hexdigest()==
                    self.launch_anchor['operator_selection_sha256'],'external trusted launch expected original identity')
            self.body=parse_canonical(self.raw,expected)
            self.observe_clock()
            return self.body
        except BaseException as e:
            self.retain(e,'operator_intake','read_bytes')
            raise self.raw_first

    def close_once(self):
        if self.close_entered:return
        self.close_entered=True
        closing,self.fd=self.fd,None
        if closing is not None:
            try:os.close(closing);self.close_known=True
            except BaseException as e:self.retain(e,'operator_fd_close','fd_close')
        # No failed clock/diagnostic gate can suppress the independent close.
        try:self.observe_clock()
        except BaseException as e:self.retain(e,'operator_postclose_clock')
        if self.raw_first is not None:raise self.raw_first

    def require_transfer_ready(self):
        require(self.read_entered and self.body is not None and self.close_entered and
                self.close_known and self.fd is None and self.raw_first is None and
                not self.transfer_attempted and not self.transferred,
                'complete original intake before once-only transfer')
        return self

def begin_operator_intake(invocation,launch_anchor,profile):
    # The caller is the fixed installed entry; semantic qualification still
    # happens later and this object is not a RootBootstrapAdmission.
    from .operator_entry import InstalledOperatorInvocation
    require(type(invocation)is InstalledOperatorInvocation and
            invocation.launch_anchor is launch_anchor and invocation.profile is profile and
            invocation.intake is None,'one original fixed-entry pre-Q1 custody slot')
    return BootstrapIntakeCustodian(_CUSTODIAN,invocation=invocation,
                                    launch_anchor=launch_anchor,profile=profile)
