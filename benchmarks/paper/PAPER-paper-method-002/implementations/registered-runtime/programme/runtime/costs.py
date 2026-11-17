"""Append-only original-attempt accounting, including failed stages and overhead."""
import time
from .strict import require, integer, canonical_bytes

class Ledger:
    def __init__(self, clock, ceiling):
        self.clock=clock;self.ceiling=ceiling;self.rows=[];self.open={}
        self.logical_reads=0;self.output_bytes=0
    def begin(self,key,role):
        self.clock.check();require(key not in self.open and all(r["key"]!=key for r in self.rows),"attempt namespace reused")
        self.open[key]={"key":key,"role":role,"start_ns":time.monotonic_ns(),"status":"running"}
    def finish(self,key,status,observation=None,error=None):
        row=self.open.pop(key);row.update({"end_ns":time.monotonic_ns(),"status":status})
        require(status in ("complete","failed","refused"),"cost terminal status")
        if observation is not None:row["original_observation"]=observation
        if error is not None:row["error"]={"type":type(error).__name__,"message":str(error)[:1000]}
        self.rows.append(row);return row
    def charge(self,read_bytes=0,output_bytes=0):
        self.logical_reads+=integer(read_bytes,"logical reads")
        self.output_bytes+=integer(output_bytes,"output bytes")
        require(self.logical_reads<=self.ceiling["logical_read_bytes"],"inclusive read ceiling")
        require(self.output_bytes<=self.ceiling["output_bytes"],"inclusive output ceiling")
    def record(self):
        return {"original_start_ns":self.clock.start_ns,"observed_ns":time.monotonic_ns(),
                "deadline_ns":self.clock.end_ns,"cleanup_deadline_ns":self.clock.cleanup_end_ns,
                "stages":self.rows,"unfinished":list(self.open.values()),
                "logical_read_bytes":self.logical_reads,"written_scientific_bytes":self.output_bytes,
                "interval_includes_preparation_collection_scoring_and_failures":True,
                "physical_OS_IO_measured":False,"warm_kernel_time_is_not_total_cost":True}
    def retain(self,root,name):
        return root.write_new(name,canonical_bytes(self.record()),8*1024*1024,clock=self.clock,cleanup=True)
