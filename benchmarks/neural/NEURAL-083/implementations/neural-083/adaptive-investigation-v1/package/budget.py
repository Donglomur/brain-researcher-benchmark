"""Incremental conservative reservations; no retained-history filesystem scans.

This trusted operator ledger is not a disk quota or physical-I/O meter. Only
successfully closed captures or durably retired operator-owned files release
live payload reservations. Cumulative read/write reservations never decrease.
"""
import math
import os
from pathlib import Path
import shutil
import stat
import time


def need(value,message):
    if not value:raise ValueError(message)


def rounded(n):
    need(type(n)is int and n>=0,'non-negative exact byte count')
    return ((n+4095)//4096)*4096


class Budget:
    def __init__(self,root,other,end,limits):
        need(type(other)is int and other>=0,'fresh other allocation')
        need(type(end)in (int,float) and math.isfinite(end),'finite original deadline')
        self.root=Path(root).absolute();self.other=other;self.end=end;self.limits=limits
        self.reads=0;self.writes=0;self.live=4096;self.peak=self.live
        self.native_counts={'fit':0,'infer':0};self.last_phase=None
        self.serial=0;self.pending={};self.retirements={};self.retired_payload=0
        self.settled_capture_count=0;self.capture_released=0
    def tick(self):
        if time.monotonic()>=self.end:raise TimeoutError('original adaptive resource deadline')
    def read(self,n):
        need(type(n)is int and n>=0 and self.reads+n<=self.limits['reads'],'whole managed read allowance')
        self.reads+=n;self.tick()
    def capacity(self,extra=0):
        need(type(extra)is int and extra>=0,'non-negative allocation reservation')
        self.tick();cap=self.limits['retained']
        need(self.live+extra<=cap,'whole retained allocation reservation')
        where=self.root if self.root.exists() else self.root.parent
        need(os.statvfs(where).f_frsize<=4096,'bounded allocation granularity')
        need(shutil.disk_usage(where).free>=self.limits['free_floor_bytes']+self.other+cap-self.live,
             'physical free floor plus unconsumed reservation')
        self.tick();return self.live
    def _reserve(self,n,allocation):
        need(type(n)is int and n>=0 and self.writes+n<=self.limits['writes'],'whole cumulative write allowance')
        self.capacity(allocation);self.writes+=n;self.live+=allocation;self.peak=max(self.peak,self.live)
    def write(self,n):
        # At most one file per inherited save/write_array call. Four allocation
        # blocks also reserve its directory entries/owned directory ancestry.
        self._reserve(n,rounded(n)+16384)
    def native(self,kind,ordinal):
        need(kind in self.native_counts and type(ordinal)is int and ordinal>=0,'known native phase')
        amount=1000000000 if kind=='fit' else 16000000
        self.read(amount);self.native_counts[kind]+=1
        self.last_phase={'kind':kind,'ordinal':ordinal,'read_reservation':amount}
    def _token(self):
        self.serial+=1;return self.serial
    def reserve_capture(self,maximum_bytes,file_count=5):
        need(type(file_count)is int and file_count==5,'fixed five provider captures')
        allocation=rounded(maximum_bytes)+file_count*20480
        self._reserve(maximum_bytes,allocation);token=self._token()
        self.pending[token]={'bytes':maximum_bytes,'allocation':allocation,'files':file_count}
        return token
    def settle_capture(self,token,root,descriptors):
        need(type(token)is int and token in self.pending,'unsettled capture reservation')
        reservation=self.pending[token];root=Path(root)
        need(type(descriptors)is list and len(descriptors)==reservation['files'],'complete capture descriptor set')
        names=[];used=0;total=0
        for descriptor in descriptors:
            need(type(descriptor)is dict and set(descriptor)=={'name','bytes','sha256'},'exact capture extent descriptor')
            name=descriptor['name'];n=descriptor['bytes']
            need(type(name)is str and Path(name).name==name and name not in names,'distinct local captures')
            need(type(n)is int and n>=0,'exact capture extent')
            p=root/name;s=p.lstat()
            need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and s.st_size==n,'observed complete ordinary capture')
            names.append(name);total+=n;used+=rounded(n)+16384
        # Bounded to exactly five entries; never traverse the retained history.
        with os.scandir(root) as entries:
            actual=[]
            for entry in entries:
                need(len(actual)<reservation['files'],'bounded capture directory')
                actual.append(entry.name)
        need(set(actual)==set(names) and total<=reservation['bytes'],'complete bounded capture directory')
        need(used<=reservation['allocation'],'capture fits prospective allocation')
        released=reservation['allocation']-used
        self.live-=released;self.capture_released+=released
        self.settled_capture_count+=1;del self.pending[token];self.tick()
    def register_retirement(self,root,pins):
        # Called only by trusted stage/model code after its charged writes,
        # never by generated analysis. It grants no credit until durable absence.
        root=Path(root).absolute()
        need(root==self.root or self.root in root.parents,'owned retirement root')
        need(type(pins)is dict and 0<len(pins)<=2,'bounded staged retirement set')
        paths=[];payload=0
        for name,pin in pins.items():
            need(type(name)is str and Path(name).name==name,'local retirement member')
            need(type(pin)is dict and set(pin)=={'bytes','sha256'},'exact retirement pin')
            p=root/name;s=p.lstat()
            need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and s.st_size==pin['bytes'],'actual charged staged file')
            need(all(str(p) not in old['paths'] for old in self.retirements.values()),'one live retirement claim')
            paths.append(str(p));payload+=rounded(pin['bytes'])
        need(payload<=self.live,'covered live payload')
        token=self._token();self.retirements[token]={'paths':paths,'payload':payload}
        return token
    def retired(self,token):
        need(type(token)is int and token in self.retirements,'one active retirement token')
        record=self.retirements[token]
        need(all(not os.path.lexists(p) for p in record['paths']),'actual durable owned-file absence')
        need(record['payload']<=self.live,'covered retirement credit')
        self.live-=record['payload'];self.retired_payload+=record['payload']
        del self.retirements[token];self.tick()
    def record(self):
        return dict(schema='neural083_incremental_reservations_v1',
            read_reservations=self.reads,write_reservations=self.writes,
            live_allocation_reservation=self.live,peak_allocation_reservation=self.peak,
            retired_payload_allocation=self.retired_payload,
            capture_allocation_released=self.capture_released,
            unknown_capture_reservations=len(self.pending),
            active_retirement_obligations=len(self.retirements),
            settled_capture_count=self.settled_capture_count,
            native_phase_counts=dict(self.native_counts),last_native_phase=self.last_phase,
            physical_IO_measured=False,physical_filesystem_quota_enforced=False,
            directory_overhead_never_credited=True,failed_and_retired_costs_retained=True)

