"""Original cumulative reservations, actual effects and all-outcome closure.

Admission capacity and observed physical effects are separate. Original failure,
resume history and recovered final child telemetry are never refunded or reset.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
import math
import os
import time
from .common import Refusal, require, encode, digest_bytes, error_record

@dataclass(frozen=True)
class Limits:
    read_bytes: int
    write_bytes: int
    child_cpu_seconds: float
    controller_cpu_seconds: float
    job_wall_seconds: float
    job_cpu_seconds: float
    job_rss_bytes: int
    jobs: int
    events: int
    closure_bytes: int = 1024 * 1024

class Meter:
    def __init__(self, limits, original_deadline, *, clock=time.monotonic,
                 cpu=time.process_time, prior=None):
        self.limits,self.clock,self.cpu=limits,clock,cpu
        require(type(original_deadline) in (int,float) and math.isfinite(original_deadline),'ORIGINAL_DEADLINE_REQUIRED')
        for key,value in asdict(limits).items():
            require(type(value) in (int,float) and math.isfinite(value) and value>=0,'INVALID_RESOURCE_LIMIT',key)
        self.deadline=original_deadline;self.started_cpu=cpu()
        self.reserved={'read_bytes':0,'write_bytes':0,'jobs':0,'events':0}
        self.observed={'read_bytes':0,'write_bytes':0,'child_cpu_seconds':0.0,
            'controller_cpu_seconds':0.0,'jobs':0,'events':0,'closure_bytes':0,'peak_child_rss_bytes':0}
        self.prior_controller_cpu=0.0;self.unknown_effects=[];self.failed=None;self.child_observations={};self.closed_child_count=0;self.closed_child_chain='0'*64
        if prior is not None:
            require(prior['deadline']==original_deadline and prior['limits']==asdict(limits),'RESUME_RESOURCE_IDENTITY_MISMATCH')
            self.reserved=dict(prior['reserved']);self.observed=dict(prior['observed'])
            self.unknown_effects=list(prior['unknown_effects']);self.failed=prior['failed']
            self.prior_controller_cpu=self.observed['controller_cpu_seconds']
            self.child_observations={k:dict(v) for k,v in prior.get('child_observations',{}).items()}
            self.closed_child_count=prior.get('closed_child_count',0);self.closed_child_chain=prior.get('closed_child_chain','0'*64)

    def refuse(self,code,detail):
        if self.failed is None:self.failed={'code':code,'detail':detail}
        raise Refusal(code,detail)

    def observe_controller(self):
        value=self.prior_controller_cpu+self.cpu()-self.started_cpu
        require(math.isfinite(value) and value>=self.observed['controller_cpu_seconds'],'INVALID_CONTROLLER_CPU_OBSERVATION')
        self.observed['controller_cpu_seconds']=value

    def checkpoint(self,effect):
        self.observe_controller()
        if self.failed:raise Refusal('ORIGINAL_RESOURCE_FAILURE',self.failed)
        if self.clock()>=self.deadline:self.refuse('ORIGINAL_DEADLINE_EXPIRED',effect)
        if self.observed['controller_cpu_seconds']>self.limits.controller_cpu_seconds:self.refuse('CONTROLLER_CPU_EXCEEDED',effect)
        for kind in self.reserved:
            if self.observed[kind]>self.reserved[kind]:self.refuse('OBSERVED_EFFECT_EXCEEDED_RESERVATION',kind)
        if self.observed['child_cpu_seconds']>self.limits.child_cpu_seconds:self.refuse('FINAL_CUMULATIVE_CPU_EXCEEDED',effect)

    def reserve(self,kind,amount,effect):
        self.checkpoint(effect)
        require(kind in self.reserved and type(amount)is int and amount>=0,'INVALID_RESERVATION')
        cap=getattr(self.limits,kind)
        if self.reserved[kind]+amount>cap:self.refuse('RESERVATION_EXHAUSTED',{'kind':kind,'effect':effect,'required':amount,'remaining':cap-self.reserved[kind]})
        self.reserved[kind]+=amount

    def observe(self,kind,amount):
        require(kind in self.observed and type(amount) in (int,float) and math.isfinite(amount) and amount>=0,'INVALID_OBSERVATION')
        self.observed[kind]+=amount
        if kind in self.reserved and self.observed[kind]>self.reserved[kind]:self.refuse('OBSERVED_EFFECT_EXCEEDED_RESERVATION',kind)
        if kind=='closure_bytes' and self.observed[kind]>self.limits.closure_bytes:self.refuse('FAILURE_RESERVE_EXHAUSTED',kind)

    def unknown(self,effect,exc):self.unknown_effects.append({'effect':effect,'error':error_record(exc)})

    def child_complete(self,telemetry,*,job_id=None,write_capacity=None,terminal=False):
        """Charge every available final snapshot once, then test all final limits.

        This records original observed counters even after a prior error/deadline.
        It authorizes no further normal effect. A repeated completion contributes
        only its nonnegative cumulative delta for the same original job identity.
        """
        required={'cpu_seconds','peak_rss_bytes','cumulative_write_bytes','descendants_closed','original_wait_complete','observation_complete'}
        require(required<=set(telemetry),'INCOMPLETE_CHILD_TELEMETRY')
        vals={k:telemetry[k] for k in ('cpu_seconds','peak_rss_bytes','cumulative_write_bytes')}
        require(all(type(v) in (int,float) and math.isfinite(v) and v>=0 for v in vals.values()),'INVALID_CHILD_COUNTER')
        require(type(vals['peak_rss_bytes'])is int and type(vals['cumulative_write_bytes'])is int,'NONINTEGER_CHILD_BYTE_COUNT')
        ident=job_id or 'legacy-unkeyed-'+str(len(self.child_observations))
        old=self.child_observations.get(ident,{'cpu_seconds':0.,'peak_rss_bytes':0,'cumulative_write_bytes':0})
        require(all(vals[k]>=old[k] for k in vals),'REGRESSED_ORIGINAL_CHILD_COUNTER',ident)
        self.observed['child_cpu_seconds']+=vals['cpu_seconds']-old['cpu_seconds']
        self.observed['write_bytes']+=vals['cumulative_write_bytes']-old['cumulative_write_bytes']
        self.observed['peak_child_rss_bytes']=max(self.observed['peak_child_rss_bytes'],vals['peak_rss_bytes'])
        self.child_observations[ident]=dict(vals)
        failures=[]
        if not all(telemetry[k] is True for k in ('observation_complete','descendants_closed','original_wait_complete')):failures.append('UNQUALIFIED_CHILD_COMPLETION')
        if vals['cpu_seconds']>self.limits.job_cpu_seconds:failures.append('FINAL_JOB_CPU_EXCEEDED')
        if vals['peak_rss_bytes']>self.limits.job_rss_bytes:failures.append('FINAL_JOB_RSS_EXCEEDED')
        if write_capacity is not None and vals['cumulative_write_bytes']>write_capacity:failures.append('CUMULATIVE_CHILD_WRITE_CAP_EXCEEDED')
        if self.observed['child_cpu_seconds']>self.limits.child_cpu_seconds:failures.append('FINAL_CUMULATIVE_CPU_EXCEEDED')
        if self.observed['write_bytes']>self.reserved['write_bytes']:failures.append('OBSERVED_EFFECT_EXCEEDED_RESERVATION')
        if failures:self.refuse(failures[0],{'job_id':ident,'all_final_violations':failures,'original_observed':vals})
        if not terminal:self.checkpoint('after_original_child_completion')

    def finish_child(self,job_id):
        # The caller invokes this once, after its last original completion attempt.
        # Full counters remain in its immutable process receipt, not duplicated in
        # every future programme/capsule snapshot. No observed cost is refunded.
        counters=self.child_observations.get(job_id)
        node={'job_id':job_id,'closed_sequence':self.closed_child_count,
              'previous':self.closed_child_chain,'counters':dict(counters) if counters is not None else None}
        digest=digest_bytes(encode(node))
        self.closed_child_count+=1;self.closed_child_chain=digest
        self.child_observations.pop(job_id,None)
        return {**node,'sha256':digest,'counter_values_available':counters is not None}

    def snapshot(self):
        self.observe_controller()
        return {'limits':asdict(self.limits),'deadline':self.deadline,'reserved':dict(self.reserved),
            'observed':dict(self.observed),'unknown_effects':list(self.unknown_effects),'failed':self.failed,
            'child_observations':{k:dict(v) for k,v in self.child_observations.items()},
            'closed_child_count':self.closed_child_count,'closed_child_chain':self.closed_child_chain}

class Journal:
    """Append-only evidence with preallocated independently metered terminal space."""
    def __init__(self,path,meter,*,prior_head=None,signer=None):
        self.path,self.meter,self.signer=path,meter,signer;self.seq=0;self.head='0'*64
        self.prior_head=prior_head;self.emergency_offset=0;self.broken=False
        self.fd=None;self.emergency=None
        meter.checkpoint('before_journal_and_failure_reserve_creation')
        try:
            self.fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            meter.checkpoint('before_failure_reserve_creation')
            self.emergency_path=str(path)+'.failure-reserve'
            self.emergency=os.open(self.emergency_path,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            os.ftruncate(self.emergency,meter.limits.closure_bytes);os.fsync(self.emergency)
            meter.checkpoint('after_failure_reserve_creation')
        except BaseException:
            for fd in (self.fd,self.emergency):
                if fd is not None:
                    try:os.close(fd)
                    except OSError:pass
            raise

    def append(self,event,detail,*,terminal=False):
        record={'sequence':self.seq,'previous':self.head,'prior_run_head':self.prior_head,'event':event,'detail':detail}
        body=encode(record)+b'\n'
        if terminal:
            require(self.emergency_offset+len(body)<=self.meter.limits.closure_bytes,'FAILURE_RESERVE_EXHAUSTED')
            fd=self.emergency;os.lseek(fd,self.emergency_offset,os.SEEK_SET)
        else:
            require(not self.broken,'ORIGINAL_JOURNAL_WRITE_FAILURE')
            self.meter.reserve('events',1,'journal_event');self.meter.reserve('write_bytes',len(body),'journal_write');fd=self.fd
        sent=0
        try:
            while sent<len(body):
                if not terminal:self.meter.checkpoint('journal_partial_write')
                n=os.write(fd,body[sent:]);require(n>0,'ZERO_WRITE');sent+=n
                if terminal:self.emergency_offset+=n
                self.meter.observe('closure_bytes' if terminal else 'write_bytes',n)
            os.fsync(fd)
            if not terminal:self.meter.checkpoint('after_journal_sync')
        except BaseException as exc:
            if not terminal:self.broken=True
            self.meter.unknown({'effect':'journal_write_or_sync','event':event,'written_prefix':sent},exc)
            raise
        if not terminal:self.meter.observe('events',1)
        self.seq+=1;self.head=digest_bytes(body)
        receipt={'sequence':record['sequence'],'sha256':self.head,'event':event,'bytes':sent,'terminal':terminal}
        if self.signer is not None and not terminal:
            try:
                self.meter.checkpoint('before_original_receipt_signer');receipt['signature']=self.signer(encode(receipt))
                self.meter.checkpoint('after_original_receipt_signer')
            except BaseException as primary:
                fallback={'original_event':event,'unsigned_receipt':receipt,'signer_error':error_record(primary)}
                try:self.append('SIGNER_FAILURE',fallback,terminal=True)
                except BaseException as secondary:
                    self.meter.unknown('signer_failure_fallback',secondary)
                    primary.add_note('Original signer failure preserved; fallback failed: '+repr(error_record(secondary)))
                setattr(primary,'journal_outcome',fallback)
                raise
        return receipt

    def close(self,primary=None,secondary=()):
        original=primary;other=list(secondary)
        if original is None:
            try:self.meter.checkpoint('before_final_journal_close')
            except BaseException as exc:original=exc
        result={'primary':error_record(original) if original else None,'secondary':[error_record(x) for x in other],
            'meter':self.meter.snapshot(),'prior_head':self.head}
        closure_error=None
        try:
            self.append('TERMINAL_FAILURE' if original else 'TERMINAL_CLOSURE',result,terminal=True)
            if original is None:self.meter.checkpoint('after_terminal_receipt_before_fd_close')
        except BaseException as exc:closure_error=exc
        finally:
            for fd in (self.fd,self.emergency):
                if fd is None:continue
                try:os.close(fd)
                except OSError as exc:
                    other.append(exc)
                    if closure_error is None:closure_error=exc
        if original is None and closure_error is None:
            try:self.meter.checkpoint('after_all_journal_close_effects')
            except BaseException as exc:closure_error=exc
        result['final_meter']=self.meter.snapshot();result['closure_failure']=error_record(closure_error) if closure_error else None
        if original is not None:
            setattr(original,'journal_closure',result)
            if closure_error:original.add_note('Original cause preserved over journal closure: '+repr(error_record(closure_error)))
            if primary is None:raise original
        elif closure_error is not None:
            setattr(closure_error,'journal_closure',result);raise closure_error
        return result
