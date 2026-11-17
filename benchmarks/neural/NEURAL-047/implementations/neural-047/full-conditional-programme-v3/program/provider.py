"""Protected root provider bridge. No keys, network requests or workers run on import."""
import os,subprocess,selectors,time,json,hashlib,copy
from pathlib import Path
from .common import exact,need,absolute,read,canonical,decode,pin
class ProviderBridge:
    def __init__(self,profile,ledger,root,evidence):
        exact(profile,["schema","executable","argv","environment_names","input_token_reservation","output_token_reservation","request_bytes","response_bytes","stderr_bytes","timeout_seconds","model"])
        need(profile["schema"]=="neural047-provider-bridge-v1","Qualified bridge profile")
        self.p=profile;self.L=ledger;self.root=absolute(root);self.calls=[];self.ids=set();self.E=evidence
        for key in ("input_token_reservation","output_token_reservation","request_bytes","response_bytes","stderr_bytes","timeout_seconds"):
            need(type(profile[key]) is int and profile[key]>0,"Positive typed provider limit")
        read(profile["executable"]["path"],{k:profile["executable"][k] for k in ("bytes","sha256")},ledger,"qualified provider executable",retain=False)
        self.cgroup=None
    def bind_cgroup(self,parent):
        self.cgroup=absolute(parent)
    def snapshot(self):return copy.deepcopy(self.calls)
    def request(self,message,tick,outer_deadline):
        index=len(self.calls);token=None;primary=None;result=None
        try:
            token=self.E.allocate(self.E.policy["provider_receipt_bytes"],"original provider attempt receipt",self.L)
            result=self._request(message,tick,outer_deadline)
        except BaseException as error:primary=error
        finally:
            if len(self.calls)==index:
                self.calls.append({"request_id":message.get("request_id") if type(message) is dict else None,
                    "status":"prelaunch_admission_failed","request_process_starts":0,"input_tokens":None,"output_tokens":None,
                    "usage_status":"no_provider_process_started","provider_receipt":None,"original_error":None if primary is None else type(primary).__name__})
            obs=self.calls[index]
            if primary is not None:
                obs["status_before_failure"]=obs.get("status");obs["status"]="failed"
                obs["original_error"]={"type":type(primary).__name__,"message":str(primary)[:512]}
            if token is not None:
                try:obs["evidence"]=self.E.emit(token,self.root/(str(index)+"_ATTEMPT.json"),obs)
                except BaseException as error:obs["attempt_receipt_error"]=type(error).__name__
        if primary is not None or any(k.endswith("_error") for k in obs):
            raise RuntimeError("Original provider attempt failed; available usage and uncertainty retained") from primary
        return result
    def _request(self,message,tick,outer_deadline):
        p=self.p;L=self.L;exact(message,["type","request_id","payload"])
        ident=message["request_id"];need(type(ident) is str and 0<len(ident)<=128 and ident not in self.ids,"Unique provider request");self.ids.add(ident)
        # Conservatively reserve maxima before launching; unused reservation is never refunded.
        for key,amount in [("provider_requests",1),("input_tokens",p["input_token_reservation"]),("output_tokens",p["output_token_reservation"])]:L.charge(key,amount,"provider admission "+ident)
        body=canonical({"request_id":ident,"model":p["model"],"max_input_tokens":p["input_token_reservation"],"max_output_tokens":p["output_token_reservation"],"payload":message["payload"]})
        need(len(body)<=p["request_bytes"],"Complete provider request cap")
        L.charge("write_bytes",len(body),"provider request transport")
        env={"PATH":"/usr/bin:/bin","LANG":"C.UTF-8"}
        for name in p["environment_names"]:
            need(type(name) is str and name in os.environ,"Explicit qualified credential environment");env[name]=os.environ[name]
        need(self.cgroup is not None,"Provider must share the owned monitored worker cgroup")
        cg=self.cgroup/("provider_"+str(len(self.calls)));cg.mkdir(mode=0o700)
        argv=[p["executable"]["path"],*p["argv"]]
        proc=None;sel=selectors.DefaultSelector();buffers={"stdout":bytearray(),"stderr":bytearray()};started=time.monotonic();sinks={}
        stop=min(L.deadline,outer_deadline,started+p["timeout_seconds"]);obs={"request_id":ident,"model":p["model"],"request_pin":pin(body),"returncode":None,"EOF":{},"status":"started","request_process_starts":0,
            "input_tokens":None,"output_tokens":None,"usage_status":"unknown_no_authoritative_response","provider_receipt":None}
        try:
            for label,cap in (("stdout",p["response_bytes"]),("stderr",p["stderr_bytes"])):
                sinks[label]=self.E.stream(self.root/(str(len(self.calls))+"_"+label+".txt"),cap,L,"original provider "+label)
            def attach():
                os.setsid()
                with (cg/"cgroup.procs").open("w") as f:f.write(str(os.getpid()))
            tick();obs["launch_outcome"]="attempted_outcome_uncertain"
            proc=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,close_fds=True,preexec_fn=attach)
            obs["launch_outcome"]="process_handle_returned"
            obs["request_process_starts"]=1
            for label in ("stdout","stderr"):
                f=getattr(proc,label);os.set_blocking(f.fileno(),False);sel.register(f,selectors.EVENT_READ,label)
            os.set_blocking(proc.stdin.fileno(),False);sent=0
            while sent<len(body):
                tick();need(time.monotonic()<stop,"Original bridge deadline")
                try:
                    n=os.write(proc.stdin.fileno(),body[sent:]);sent+=n
                    obs["request_written_bytes"]=sent;L.observe("write_bytes",n,"original provider request write")
                except BlockingIOError:time.sleep(.002)
            proc.stdin.close()
            while sel.get_map() or proc.poll() is None:
                tick();need(time.monotonic()<stop,"Original bridge deadline")
                for key,_ in sel.select(.01):
                    chunk=os.read(key.fd,65536)
                    if not chunk:sel.unregister(key.fileobj);obs["EOF"][key.data]=True;continue
                    cap=p["response_bytes"] if key.data=="stdout" else p["stderr_bytes"]
                    buffers[key.data].extend(chunk[:max(0,cap-len(buffers[key.data]))])
                    sinks[key.data].append(chunk)
            obs["returncode"]=proc.wait()
            result=decode(bytes(buffers["stdout"]))
            if type(result) is dict:
                usage=result.get("usage")
                if type(usage) is dict:
                    for key in ("input_tokens","output_tokens"):
                        if type(usage.get(key)) is int and usage[key]>=0:obs[key]=usage[key]
                bill=result.get("provider_receipt")
                if type(bill) is str:obs["provider_receipt"]=bill[:512]
                if result.get("request_id")==ident and result.get("model")==p["model"] and type(bill) is str and 0<len(bill)<=512 and all(obs[k] is not None for k in ("input_tokens","output_tokens")):
                    obs["usage_status"]="authoritative_bound_response"
                    for key in ("input_tokens","output_tokens"):L.observe(key,obs[key],"original authoritative provider usage")
                    L.observe("provider_requests",1,"original authoritative provider request")
                else:obs["usage_status"]="unverified_reported_fields; actual_usage_unknown"
            need(obs["returncode"]==0,"Original bridge failure")
            exact(result,["request_id","model","response","usage","provider_receipt"])
            need(result["request_id"]==ident and result["model"]==p["model"],"Qualified original provider response")
            exact(result["usage"],["input_tokens","output_tokens"])
            need(obs["usage_status"]=="authoritative_bound_response","Complete bounded original provider usage identity")
            for key in ("input_tokens","output_tokens"):
                value=result["usage"][key];need(type(value) is int and value>=0,"Authoritative typed provider usage")
                obs[key]=value;need(value<=p[key.replace("_tokens","_token_reservation")],"Observed provider cost exceeded admission")
            need(type(result["provider_receipt"]) is str and result["provider_receipt"],"Original provider billing/request identity")
            obs["provider_receipt"]=result["provider_receipt"];obs["status"]="closed"
            response=result["response"]
        finally:
            if proc is not None:
                try:
                    with (cg/"cgroup.kill").open("w") as f:f.write("1")
                except BaseException as error:obs["subtree_cleanup_error"]=type(error).__name__
                try:proc.wait(timeout=max(.001,stop-time.monotonic()))
                except subprocess.TimeoutExpired:obs["status"]="cleanup_unresolved"
                while time.monotonic()<stop:
                    try:
                        if "populated 0" in (cg/"cgroup.events").read_text():obs["subtree_empty"]=True;break
                        tick();time.sleep(.005)
                    except BaseException as error:obs["subtree_cleanup_error"]=type(error).__name__;break
            # Always attempt each original prefix separately; data remains operator-private.
            for label,sink in sinks.items():
                try:
                    obs[label]=sink.close(obs["EOF"].get(label,False))
                    need(not obs[label]["errors"],"Original provider stream persistence")
                except BaseException as error:obs[label]=sink.summary();obs[label+"_persistence_error"]=type(error).__name__
            obs["elapsed_seconds"]=time.monotonic()-started;self.calls.append(obs);sel.close()
        need(time.monotonic()<stop and obs["status"]=="closed" and obs.get("subtree_empty") is True and all(obs["EOF"].get(x) for x in ("stdout","stderr"))
             and not any(k.endswith("_error") for k in obs),"Provider original evidence or cleanup incomplete")
        return response,obs

