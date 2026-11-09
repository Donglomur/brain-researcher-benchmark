"""Declared method budgets intersect at context, method and programme levels."""
import copy,time,math,hashlib
from .common import exact,need,canonical
COSTS=("read_bytes","write_bytes","provider_requests","input_tokens","output_tokens")
NATIVE=("cpu_us","memory_bytes","pids","stdout_bytes","stderr_bytes","output_bytes","threads")
def validate_limits(value,mode):
    exact(value,["per_context","all_contexts"])
    exact(value["per_context"],["wall_seconds",*COSTS,*NATIVE])
    exact(value["all_contexts"],["wall_seconds",*COSTS,"cpu_us"])
    for scope,row in value.items():
        for key,v in row.items():
            floor=0 if key in ("provider_requests","input_tokens","output_tokens") else 1
            need(type(v) is int and v>=floor,"Integral method "+scope+" "+key+" bound")
    for key in value["all_contexts"]:
        need(value["per_context"][key]<=value["all_contexts"][key],"Context budget exceeds cumulative method budget")
    if mode=="F":need(all(value[s][k]==0 for s in value for k in ("provider_requests","input_tokens","output_tokens")),"F has no provider access")
    else:need(all(value[s][k]>0 for s in value for k in ("provider_requests","input_tokens","output_tokens")),"I provider reservations must be explicit")
    return value
def comparison(F,I):
    f=validate_limits(F["limits"],"F");i=validate_limits(I["limits"],"I")
    for scope in ("per_context","all_contexts"):
        for key in f[scope]:
            if key not in ("provider_requests","input_tokens","output_tokens"):
                need(f[scope][key]==i[scope][key],"Matched F/I "+scope+" "+key+" policy")
    return {"matched_nonprovider_limits":True,"intentional_asymmetry":"F provider budgets are zero; I has independently admitted requests/token maxima. Both retain identical nonprovider limits."}
class MethodMeter:
    def __init__(self,root,contract):
        validate_limits(contract["limits"],contract["mode"])
        self.root=root;self.mode=contract["mode"];self.limits=contract["limits"]
        self.used={k:0 for k in self.limits["all_contexts"]};self.observed={k:0 for k in COSTS};self.phases=[];self.unknown_final_CPU=0
    def context(self,name,native=None):
        return Context(self,name,native)
    def summary(self,compact=False):
        return {"mode":self.mode,"limits":self.limits,"reserved_costs":self.used,"observed_costs":self.observed,
                "phases":None if compact else self.phases,"phase_count":len(self.phases),"phase_sha256":hashlib.sha256(canonical(self.phases)).hexdigest(),
                "source_phase":self.phases[0] if self.phases and self.phases[0]["name"]=="pre-release source snapshot" else None,
                "remaining_phase_evidence":"Each original context receipt, including failures, is separately reserved and written.",
                "unknown_final_CPU":self.unknown_final_CPU}
class Context:
    def __init__(self,method,name,native):
        self.method=method;self.root=method.root;self.name=name;self.clock=self.root.clock
        self.limits=method.limits["per_context"];self.used={k:0 for k in self.limits};self.observed={k:0 for k in COSTS}
        remaining=method.limits["all_contexts"]["wall_seconds"]-method.used["wall_seconds"]
        need(remaining>0,"Method cumulative wall allowance exhausted")
        self.started=self.clock();self.deadline=min(self.root.work_deadline,self.started+self.limits["wall_seconds"],self.started+remaining)
        self.work_deadline=self.deadline;self.closed=False;self.native=None
        if native:
            self.native=copy.deepcopy(native);p=self.native["limits"]
            for key in NATIVE:
                p[key]=min(p[key],self.limits[key])
            p["cpu_us"]=min(p["cpu_us"],method.limits["all_contexts"]["cpu_us"]-method.used["cpu_us"])
            need(p["cpu_us"]>0 and p["cleanup_seconds"]<self.deadline-self.started,"Context resources cover original work plus cleanup")
            p["job_wall_seconds"]=min(p["job_wall_seconds"],self.limits["wall_seconds"]-p["cleanup_seconds"])
            self.work_deadline=min(self.work_deadline,self.deadline-p["cleanup_seconds"])
    def live(self):
        self.root.live();need(self.clock()<self.deadline,"Original context interval exhausted")
    def charge(self,kind,amount,role):
        self.live();need(kind in COSTS and type(amount) is int and amount>=0,"Typed context reservation")
        need(self.used[kind]+amount<=self.limits[kind],"Context "+kind+" exhausted")
        need(self.method.used[kind]+amount<=self.method.limits["all_contexts"][kind],"Method cumulative "+kind+" exhausted")
        self.root.charge(kind,amount,role)
        self.used[kind]+=amount;self.method.used[kind]+=amount
    def reserved_write(self,amount,role):
        """Root already reserved failure/stream space; enforce child scopes without double charging root."""
        self.live();need(type(amount) is int and amount>=0,"Reserved child write")
        need(self.used["write_bytes"]+amount<=self.limits["write_bytes"],"Context evidence allowance")
        need(self.method.used["write_bytes"]+amount<=self.method.limits["all_contexts"]["write_bytes"],"Method evidence allowance")
        self.used["write_bytes"]+=amount;self.method.used["write_bytes"]+=amount
    def observe(self,kind,amount,role):
        self.root.observe(kind,amount,role);self.observed[kind]+=amount;self.method.observed[kind]+=amount
    def record_read_failure(self,observation):
        self.root.record_read_failure({**observation,"method":self.method.mode,"context":self.name})
    def finish(self,cpu_us=0):
        need(not self.closed,"Context closes once");self.closed=True
        elapsed=max(0,self.clock()-self.started)
        self.used["wall_seconds"]=elapsed;self.used["cpu_us"]=cpu_us
        self.method.used["wall_seconds"]+=elapsed
        if type(cpu_us) is int and cpu_us>=0:self.method.used["cpu_us"]+=cpu_us
        else:self.method.unknown_final_CPU+=1
        record={"name":self.name,"selected_limits":self.limits,"effective_native_limits":self.native["limits"] if self.native else None,
                "reserved_costs":dict(self.used),"observed_costs":dict(self.observed),"elapsed_seconds":elapsed,"original_deadline":self.deadline,"closed_at":self.clock()}
        self.method.phases.append(record)
        need(type(cpu_us) is int and cpu_us>=0,"Known typed original CPU observation")
        need(elapsed<=self.limits["wall_seconds"] and self.clock()<self.deadline,"Final original context deadline")
        need(cpu_us<=self.limits["cpu_us"],"Final context CPU cap")
        for k in ("wall_seconds","cpu_us"):need(self.method.used[k]<=self.method.limits["all_contexts"][k],"Final cumulative method "+k+" cap")
        return record

