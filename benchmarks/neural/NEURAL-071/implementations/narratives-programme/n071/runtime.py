"""Actual source-pinned external worker invocation; no local uncontained fallback.

The future launcher is a separately qualified dependency. It must own a whole
isolated process tree, enforce the supplied mounts/quotas, wait every descendant,
and publish a protected accounting receipt. Merely supplying a Docker label or
participant JSON is not qualification. This module does not invent that receipt.
"""
import os
import selectors
import signal
import subprocess
import time
from .errors import Custody,need
from .identity import identity,parse,exact,descriptor,relative
from .store import Store
from . import codec

class Runtime:
    def __init__(self,qualification,store,journal):
        self.qualification=qualification;self.store=store;self.journal=journal
        self.binding=qualification.require(journal.generation,journal.source)
        self.materialized={}
        self.observations=[];self.process_observations=[];self.accounting_observations=[];self.process_records=[]

    def _assets(self,role):
        """Materialize only explicit qualification-selected immutable source assets."""
        assets=self.binding["runtime_assets"]
        need(type(assets)is list and assets,"runtime-assets-required")
        selected={}
        for item in assets:
            exact(item,("source_root","source","destination","roles"))
            need(type(item["source_root"])is str and os.path.isabs(item["source_root"]),
                 "asset-source-root")
            descriptor(item["source"]);target=descriptor(item["destination"])
            need(type(item["roles"])is list and item["roles"] and
                 len(set(item["roles"]))==len(item["roles"]),"asset-role-selection")
            if role not in item["roles"]:continue
            name=target["path"]
            need(name not in selected,"unique-runtime-asset-path")
            selected[name]=target
            if name in self.materialized:
                need(self.materialized[name]==item,"runtime-asset-rebinding")
                self.store.read(target)
            else:
                reader=Store(item["source_root"],self.store.budget)
                self.store.copy_from(reader,item["source"],target)
                self.materialized[name]=item
        launcher=self.binding["launcher"]
        required=[launcher["executable_descriptor"]]+launcher["dependencies"]
        need(launcher["path"]==launcher["executable_descriptor"]["path"],"launcher-logical-path")
        need(launcher["adopted_source_identity"]==launcher["executable_descriptor"]["sha256"],
             "launcher-source")
        need(launcher["executable_descriptor"]["mode"]==0o500,"launcher-executable-mode")
        need(all(selected.get(d["path"])==d for d in required),"launcher-complete-assets")
        return selected,required

    def _prepare(self,role,programme,request,mounts,rid):
        selected,launcher_assets=self._assets(role)
        descriptor(programme);descriptor(request)
        if role.startswith("reference-"):
            need(programme==self.binding["reference_worker"] and
                 selected.get(programme["path"])==programme,"reference-capsule-selected")
        capsule=self.store.json(programme)
        exact(capsule,("files","entrypoint","context"),"programme-capsule-fields")
        need(type(capsule["files"])is dict and capsule["files"] and
             type(capsule["entrypoint"])is list and capsule["entrypoint"] and
             all(type(x)is str for x in capsule["entrypoint"]),"programme-capsule")
        need(capsule["entrypoint"][0] in capsule["files"],"capsule-entrypoint")
        for logical,d in capsule["files"].items():
            relative(logical);descriptor(d)
            if role.startswith("reference-"):
                need(selected.get(d["path"])==d,"reference-complete-source-assets")
        artifacts={programme["path"]:programme}
        for mount in mounts:
            exact(mount,("artifact","visibility","kind"),"runtime-mount-fields")
            need(mount["visibility"]=="read-only" and
                 mount["kind"] in ("packed","opaque","capsule"),"runtime-input-kind")
            d=descriptor(mount["artifact"])
            if mount["kind"]=="capsule":
                need(d==programme,"only-selected-programme-capsule")
                members=[d]
            else:
                members=codec.artifacts(self.store,d) if mount["kind"]=="packed" else [d]
            for member in members:
                name=member["path"]
                need(name not in artifacts or artifacts[name]==member,"runtime-input-collision")
                artifacts[name]=member
        need(artifacts.get(request["path"])==request,"request-explicitly-mounted")
        base="worker-"+rid
        self.store.directory(base,exclusive=True)
        data_root=self.store.directory(base+"/data",exclusive=True)
        program_root=self.store.directory(base+"/programme",exclusive=True)
        child=Store(data_root,self.store.budget);program=Store(program_root,self.store.budget)
        staged=[];restoration=[]
        for d in artifacts.values():
            need(d["mode"] in (0o400,0o444),"immutable-worker-input")
            child.copy_from(self.store,d,d)
            staged.append({"artifact":d,"host_path":child.path(d["path"]),
                           "guest_path":"data/"+d["path"],"visibility":"read-only"})
        for logical,d in capsule["files"].items():
            target=dict(d,path=logical,mode=0o500 if logical==capsule["entrypoint"][0] else 0o400)
            program.copy_from(self.store,d,target)
            restoration.append({"logical":logical,"source":d,"restored":target})
            staged.append({"artifact":target,"host_path":program.path(logical),
                           "guest_path":"programme/"+logical,"visibility":"read-only"})
        # The launcher and its explicit dependencies are source-authenticated host
        # assets, not participant mounts. No other host path is inferred.
        envelope={"generation":self.journal.generation,"source":self.journal.source,
                  "context":self.journal.context,"scope":self.journal.context+"/worker/"+rid,
                  "root":data_root,"request":request,"output_prefix":"outputs/"+rid,
                  "input_directories":sorted(child.directories),
                  "limits":self.binding["worker_reservations"][role],
                  "historical_layer8_direct_consumer":self.journal.direct,
                  "original_parent":dict(self.journal.parents.get(self.journal.context,
                                     {"request_id":None,"receipt":None})),
                  "owning_runtime_request":self.journal.owned[rid]["request_artifact"]}
        return {"worker_root":data_root,"programme_root":program_root,
                "entrypoint":capsule["entrypoint"],"restoration":restoration,
                "input_artifacts":list(artifacts.values()),"mounts":staged,"output_prefix":"outputs/"+rid,
                "launcher_assets":launcher_assets,"envelope":envelope}

    def _import_outputs(self,prepared,outputs,result,role):
        """Import exact protected launcher output identities; no namespace guessing."""
        need(type(outputs)is list and outputs,"worker-output-manifest")
        inputs={d["path"]:d for d in prepared["input_artifacts"]}
        selected={}
        for d in outputs:
            descriptor(d);name=d["path"]
            need(name not in selected and name not in inputs,"worker-output-freshness")
            if role.startswith("reference-"):
                need(name.startswith(prepared["output_prefix"]+"/"),"worker-output-namespace")
            need(d["mode"] in (0o400,0o444),"immutable-worker-output")
            selected[name]=d
        # The source-owned reference entry writes its namespace before JSON/array
        # publication. Opaque participant outputs are mapped at this controller
        # seam without inspecting or rewriting their bodies.
        mapped={name:(d if name.startswith(prepared["output_prefix"]+"/") else
                      dict(d,path=prepared["output_prefix"]+"/"+name))
                for name,d in selected.items()}
        need(len({d["path"] for d in mapped.values()})==len(mapped),"output-mapping-collision")
        allowed=inputs|selected
        def project(v):
            if type(v)is dict:
                if set(v)=={"path","bytes","sha256","mode"}:
                    descriptor(v);need(allowed.get(v["path"])==v,"worker-result-artifact-closure")
                    return mapped.get(v["path"],v)
                return {k:project(x) for k,x in v.items()}
            if type(v)is list:return [project(x) for x in v]
            return v
        projected=project(result)
        reader=Store(prepared["worker_root"],self.store.budget)
        imported=[]
        for name,d in selected.items():
            # O_EXCL prevents overwriting any source or previously imported state.
            # Mapping is explicit and is recorded beside the original driver result.
            imported.append(self.store.copy_from(reader,d,mapped[name]))
        return imported,projected


    def _uncertain(self,custody,effect,**facts):
        try:self.store.budget.unknown.append({"effect":effect,
            "unacknowledged_capacity":"runtime accounting or closure",**facts})
        except BaseException as exc:custody.retain(exc,"runtime-unknown-record")

    def _settle(self,custody,token,acknowledged,unknown,phase):
        # Each caller removes the token from its remaining-attempt roster
        # before entry. An ambiguous settlement is never retried or refunded.
        observation={"token":token,"acknowledged":acknowledged,"unknown_prefix":unknown,
                     "phase":phase,"settled":False,"custody":custody}
        self.accounting_observations.append(observation)
        try:
            self.store.budget.settle(token,acknowledged,unknown=unknown)
            observation["settled"]=True
        except BaseException as exc:
            custody.retain(exc,phase)
            self._uncertain(custody,phase,token=token,acknowledged=acknowledged,
                            unknown_possible_prefix=unknown)
        return observation["settled"]

    def _transfer(self,destination,source):
        # Both carriers were allocated by this Runtime/Journal. Never inspect
        # attributes, dictionaries, type names or text on raw exception objects.
        if source.first is not None:
            destination.retain(source.first[1],source.first[0])
        for phase,exc in source.secondary:destination.retain(exc,phase)

    def invoke(self,role,programme,request,mounts,output_name,output_cap):
        custody=Custody();self.observations.append(custody)
        budget=self.store.budget;rid=None;worker_tokens={};dispatched=False
        process_mark=None;projected=None;rec=None
        try:
            need(role in ("candidate-author-tool","candidate-fit","candidate-infer",
                          "reference-fit","reference-infer","trusted-preparation","postscore-review"),
                 "runtime-role")
            need(type(output_cap)is int and output_cap>0,"runtime-output-cap")
            rid=self.journal.begin("runtime",role,[request,programme],
                                   {"bytes":output_cap,"pipe_eof_probe_bytes":1})
            # This private strong owner is never part of a serialized receipt.
            self.journal.owned[rid]["runtime_custody"]=custody
            prepared=self._prepare(role,programme,request,mounts,rid)
            worker_limits=self.binding["worker_reservations"][role]
            for dim in ("read_bytes","write_bytes","creation_attempts","child_attempts"):
                worker_tokens[dim]=budget.reserve(dim,worker_limits[dim],"worker-allocation-"+role)
            call={"role":role,"programme":programme,"request":request,**prepared,
                  "limits":worker_limits,"qualification":self.qualification.identity,
                  "network":False,"descendant_cleanup_required":True,
                  "pipe_output":{"payload_cap_bytes":output_cap,"eof_probe_bytes":1,"streams":2},
                  "output_rule":"new immutable worker-root artifacts only; protected complete manifest"}
            call_record=self.store.put("runtime-call-"+rid+".json",call)
            launcher=self.binding["launcher"]
            argv=[self.store.path(launcher["executable_descriptor"]["path"]),
                  "--request",self.store.path(call_record["path"])]
            dispatched=True;process_mark=len(self.process_observations)
            result=self._process(argv,output_cap)
            stdout=self.store.write(output_name+"-stdout.bin",result.pop("stdout"))
            stderr=self.store.write(output_name+"-stderr.bin",result.pop("stderr"))
            need(result["exit_code"]==0,"worker-nonzero")
            returned=parse(self.store.read(stdout))
            receipt=self.store.json(returned["launcher_receipt"])
            need(receipt["call"]==call_record and receipt["qualification"]==self.qualification.identity and
                 receipt["all_descendants_waited"] is True and receipt["mounts"]==prepared["mounts"] and
                 receipt["worker_root"]==prepared["worker_root"] and
                 receipt["input_artifacts"]==prepared["input_artifacts"] and
                 receipt["network"] is False and receipt["unknown_costs"]==[],"launcher-custody")
            budget.observe_process(result["wait_cpu_seconds"]+receipt["descendant_cpu_seconds"],
                                   receipt["whole_tree_peak_rss_bytes"])
            for dim in ("read_bytes","write_bytes","creation_attempts","child_attempts"):
                acknowledged=receipt["worker_costs"][dim]
                token=worker_tokens.pop(dim)
                self._settle(custody,token,acknowledged,False,"worker-cost-"+dim)
            custody.raise_first()
            imported,projected=self._import_outputs(prepared,receipt["output_artifacts"],returned["result"],role)
            rec=self.journal.finish(rid,{"stdout":stdout,"stderr":stderr,"result":returned,
                                        "imported_outputs":imported,"projected_result":projected},
                                   result|{"launcher":returned["launcher_receipt"]})
        except BaseException as exc:
            # Copy actual process-carrier ordering before later parent-token
            # settlement. A returned original object is not annotated or queried.
            process_error=False
            if process_mark is not None:
                for owner in self.process_observations[process_mark:]:
                    if owner.first is not None:
                        self._transfer(custody,owner)
                        if owner.first[1]is exc:process_error=True
            if not process_error and (custody.first is None or custody.first[1]is not exc):
                custody.retain(exc,"runtime")
        finally:
            # Removal is before the attempt, even if settle fails after mutating
            # Budget. Other reservations still receive independent attempts.
            for dim in tuple(worker_tokens):
                token=worker_tokens.pop(dim)
                self._settle(custody,token,0,dispatched,"worker-remainder-"+dim)
        if custody.first is not None:
            if rid is not None:
                self.journal.owned[rid]["failed"]=True
            self._transfer(self.journal.custody,custody)
        custody.raise_first()
        return projected,rec

    def _process(self,argv,cap):
        budget=self.store.budget;custody=Custody()
        self.process_observations.append(custody)
        read=None;probe=None;fd_slots=[];p=None;selector=None;buffers=[bytearray(),bytearray()]
        consumed=0;unknown=False;payload_unknown=False;probe_unknown=False
        eof=[False,False];probe_attempts=0
        status=None;usage=None;wait_owned=False;start=None
        observation={"custody":custody,"fd_slots":fd_slots,"read_token":None,
                     "probe_token":None,"payload_cap":cap,"probe_capacity":1,
                     "acknowledged_read":0,"acknowledged_payload_read":0,"acknowledged_probe_read":0,
                     "unknown_read":False,"payload_unknown":False,"probe_unknown":False,
                     "eof_observed":eof,"probe_attempts":0,"wait_owned":False}
        self.process_records.append(observation)
        try:
            # Own reservations before every fallible reservation/birth operation.
            read=budget.reserve("read_bytes",cap,"worker-pipes");observation["read_token"]=read
            # A separate one-byte reservation is shared serially by the two EOF
            # observations. Zero-byte EOF returns consume none; the first byte
            # or ambiguous read aborts, so this token can never cover two bytes.
            # Payload cap and original cumulative budget are unchanged.
            probe=budget.reserve("read_bytes",1,"worker-pipe-eof-probe")
            observation["probe_token"]=probe
            for _ in range(2):
                token=budget.reserve_fd("worker-pipe")
                fd_slots.append({"token":token,"acquisition_attempted":False,"acquired":False,
                                 "stream":None,"close_attempted":False,"closed":False})
            try:budget.attempt("child_attempts","worker-birth")
            except BaseException as exc:
                custody.retain(exc,"worker-birth-accounting")
                self._uncertain(custody,"worker-birth-accounting")
                raise
            start=time.monotonic()
            try:
                p=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                   shell=False,close_fds=True,start_new_session=True,cwd=self.store.root,
                                   env={"PATH":"/usr/bin:/bin","PYTHONHASHSEED":"0"})
            except BaseException:
                unknown=True;payload_unknown=True;probe_unknown=True
                raise
            # Both returned objects belong to the owner before either accounting
            # operation, selector creation or registration can fail.
            fd_slots[0]["stream"]=p.stdout;fd_slots[1]["stream"]=p.stderr
            for slot in fd_slots:
                slot["acquisition_attempted"]=True
                try:
                    budget.acquired_fd(slot["token"]);slot["acquired"]=True
                except BaseException as exc:
                    custody.retain(exc,"pipe-acquisition-accounting")
                    self._uncertain(custody,"pipe-acquisition-accounting",token=slot["token"])
            custody.raise_first()
            selector=selectors.DefaultSelector()
            for index,slot in enumerate(fd_slots):
                stream=slot["stream"]
                os.set_blocking(stream.fileno(),False)
                selector.register(stream,selectors.EVENT_READ,index)
            while selector.get_map() or not wait_owned:
                budget.checkpoint()
                if not wait_owned:
                    pid,s,u=os.wait4(p.pid,os.WNOHANG)
                    if pid:
                        status=s;usage=u;wait_owned=True
                        p.returncode=os.waitstatus_to_exitcode(s)
                for key,_ in selector.select(.05):
                    at_cap=consumed==cap
                    capacity=1 if at_cap else min(65536,cap-consumed)
                    need(capacity>0,"worker-pipe-cap")
                    if at_cap:probe_attempts+=1
                    try:part=os.read(key.fileobj.fileno(),capacity)
                    except BlockingIOError:continue
                    except BaseException:
                        unknown=True
                        if at_cap:probe_unknown=True
                        else:payload_unknown=True
                        raise
                    consumed+=len(part)
                    # Even the refused overflow byte is acknowledged and charged.
                    # It never enters a returned payload or successful receipt.
                    need(consumed<=cap,"worker-pipe-cap")
                    if part:buffers[key.data].extend(part)
                    else:
                        eof[key.data]=True
                        selector.unregister(key.fileobj)
        except BaseException as exc:
            if custody.first is None or custody.first[1]is not exc:custody.retain(exc,"worker")
        finally:
            if p is not None and not wait_owned:
                try:os.killpg(p.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                except BaseException as exc:custody.retain(exc,"worker-kill")
                try:
                    _,status,usage=os.wait4(p.pid,0)
                    wait_owned=True;p.returncode=os.waitstatus_to_exitcode(status)
                except BaseException as exc:custody.retain(exc,"worker-wait")
            if selector is not None:custody.close(selector,lambda s:s.close(),"selector-close")
            for slot in fd_slots:
                stream=slot["stream"]
                if stream is not None:
                    slot["close_attempted"]=True
                    try:
                        stream.close();slot["closed"]=True
                    except BaseException as exc:custody.retain(exc,"pipe-close")
                    if slot["acquired"]:
                        try:budget.fd_closed(slot["closed"])
                        except BaseException as exc:
                            custody.retain(exc,"pipe-close-accounting")
                            self._uncertain(custody,"pipe-close-accounting",token=slot["token"],
                                            physical_close_acknowledged=slot["closed"])
                    else:
                        self._uncertain(custody,"pipe-acquisition-unsettled",token=slot["token"],
                                        physical_close_acknowledged=slot["closed"])
                elif not slot["acquisition_attempted"]:
                    # No acquired descriptor exists. Keep ambiguous Popen cost
                    # unknown; never rerun an attempted acquisition settlement.
                    slot["acquisition_attempted"]=True
                    self._settle(custody,slot["token"],0,unknown,"unacquired-pipe-reservation")
            observation.update(acknowledged_read=consumed,unknown_read=unknown,wait_owned=wait_owned,
                acknowledged_payload_read=min(consumed,cap),acknowledged_probe_read=max(0,consumed-cap),
                payload_unknown=payload_unknown,probe_unknown=probe_unknown,probe_attempts=probe_attempts)
            if read is not None:
                self._settle(custody,read,min(consumed,cap),payload_unknown,"worker-pipe-settlement")
            if probe is not None:
                self._settle(custody,probe,max(0,consumed-cap),probe_unknown,"worker-eof-probe-settlement")
        custody.raise_first()
        try:
            need(wait_owned and usage is not None,"original-child-wait")
            need(eof==[True,True],"both-worker-pipes-observed-eof")
            result={"stdout":bytes(buffers[0]),"stderr":bytes(buffers[1]),"exit_code":p.returncode,
                    "raw_wait_status":status,"wait_cpu_seconds":usage.ru_utime+usage.ru_stime,
                    "wall_seconds":time.monotonic()-start,"cleanup":custody.diagnostic(),
                    "pipe_observation":{"payload_cap_bytes":cap,"probe_capacity_bytes":1,
                        "payload_bytes":min(consumed,cap),"probe_bytes":max(0,consumed-cap),
                        "eof_observed":list(eof),"probe_attempts":probe_attempts}}
        except BaseException as exc:custody.retain(exc,"worker-result")
        custody.raise_first()
        return result
