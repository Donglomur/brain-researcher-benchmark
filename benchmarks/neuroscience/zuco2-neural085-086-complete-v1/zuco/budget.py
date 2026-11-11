"""Nonrecursive monotone accounting; debit first, refuse final overshoots explicitly."""
import copy,time,resource
from .io import need,finite,Refusal
class Ledger:
    def __init__(self,spec,clock=time.monotonic):
        self.spec=copy.deepcopy(spec);self.clock=clock;self.bytes=spec["prior_bytes"];self.cpu=spec["prior_cpu_seconds"];self.records=[];self.reserved={};self.unknown=False;self.closed=False
        need(type(spec["deadline_monotonic"])in(int,float) and finite(spec["deadline_monotonic"]),"deadline_value");need(spec["closure_seconds"]>0,"closure_reserve")
        for name in ('prior_bytes','storage_bytes'):
            need(type(spec[name])is int and spec[name]>=0,'budget_byte_value',name)
        for name in ('prior_cpu_seconds','cpu_seconds','controller_cpu_reserve'):
            need(finite(spec[name]) and spec[name]>=0,'budget_CPU_value',name)
        self.guard()
    def guard(self,closing=False):
        need(not self.unknown,"unmeasured_resources");need(self.clock()+(0 if closing else self.spec["closure_seconds"])<self.spec["deadline_monotonic"],"deadline")
        need(self.cpu<=self.spec["cpu_seconds"] and self.bytes<=self.spec["storage_bytes"],"budget_exceeded")
    def reserve_bytes(self,n,purpose):
        self.guard();need(type(n)is int and n>=0,"byte_reservation");need(self.bytes+n<=self.spec["storage_bytes"],"storage_reservation",purpose);self.bytes+=n
    def reserve_job(self,key,limit):
        self.guard();need(key not in self.reserved,"reused_job")
        for name in ('output_bytes','stream_bytes','receipt_bytes','files'):
            need(type(limit[name])is int and limit[name]>0,'job_byte_file_cap',name)
        for name in ('cpu_seconds','wall_seconds','cleanup_seconds','completion_cpu_reserve'):
            need(finite(limit[name]) and limit[name]>0,'job_time_cap',name)
        need(limit['completion_cpu_reserve']<limit['cpu_seconds'],'completion_reserve_inside_job_cap')
        pending=sum(v["cpu_seconds"] for v in self.reserved.values() if not v["closed"])
        need(self.cpu+pending+limit["cpu_seconds"]+self.spec["controller_cpu_reserve"]<=self.spec["cpu_seconds"],"cpu_reservation")
        self.reserve_bytes(limit["output_bytes"]+limit["stream_bytes"]*4+limit["receipt_bytes"]*4,"job outputs/streams/receipt")
        self.reserved[key]={**copy.deepcopy(limit),"closed":False};return copy.deepcopy(self.reserved[key])
    def settle(self,key,resources):
        v=self.reserved[key];need(not v["closed"],"duplicate_settlement");v["closed"]=True;cpu=resources.get("cpu_seconds")
        if not finite(cpu) or cpu<0 or resources.get("measurement_complete")is not True:self.unknown=True
        else:self.cpu+=cpu
        error=None
        try:
            need(not self.unknown,"unmeasured_resources");need(cpu<=v["cpu_seconds"],"final_job_cpu");self.guard(closing=True)
        except BaseException as e:error={"type":type(e).__name__,"message":str(e),"code":getattr(e,"code",None)}
        self.records.append({"job":key,"resources":copy.deepcopy(resources),"budget_failure":error});return error
    def charge_controller(self,seconds):
        need(finite(seconds) and seconds>=0,"controller_measurement");self.cpu+=seconds
        self.guard(closing=True)
    def final(self):
        self.guard(closing=True);need(all(v["closed"] for v in self.reserved.values()),"open_reservations");return self.snapshot()
    def snapshot(self):return {"spec":copy.deepcopy(self.spec),"actual_charged_cpu_seconds":self.cpu,"reserved_materialized_bytes":self.bytes,"records":copy.deepcopy(self.records),"reservations":copy.deepcopy(self.reserved),"unknown":self.unknown}
