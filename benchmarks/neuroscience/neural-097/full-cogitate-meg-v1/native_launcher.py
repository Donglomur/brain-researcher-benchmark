#!/usr/bin/env python3
"""Concrete local-Docker physical launcher. BUILD source: deployment disabled.

Adapted lifecycle invariants from the retained NEURAL088 engine/transport:
owned exact resources, prestart inspected boundaries, original completion,
producer removal before capture, readonly holder, full streams and exact absence.
No inherited image, task data, model or qualification is reused.
"""
import base64,hashlib,json,os,selectors,signal,stat,subprocess,sys,time,uuid
from pathlib import Path
NATIVE_DEPLOYMENT=False

def need(ok,message):
    if not ok:raise ValueError(message)

def encode(obj):return (json.dumps(obj,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode()

def pin(body):return {"bytes":len(body),"sha256":hashlib.sha256(body).hexdigest()}

def decode(body):
    def pairs(rows):
        out={}
        for k,v in rows:need(k not in out,"Duplicate JSON key");out[k]=v
        return out
    return json.loads(body,object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in()).throw(ValueError("Nonfinite JSON")))

def relative(name):
    p=Path(name)
    need(type(name)is str and name and not p.is_absolute()and p.as_posix()==name and "\\"not in name and all(x not in(".","..")for x in p.parts),"Canonical relative file")
    return p

def read(path,expected,cap):
    p=Path(path).absolute()
    need(all(not q.is_symlink()for q in(p,*p.parents)),"No source symlink")
    s=p.stat();need(stat.S_ISREG(s.st_mode)and s.st_nlink==1 and s.st_size==expected["bytes"]<=cap,"Bounded complete ordinary input")
    with p.open("rb")as stream:b=stream.read(cap+1)
    t=p.stat();need((s.st_ino,s.st_size,s.st_mtime_ns)==(t.st_ino,t.st_size,t.st_mtime_ns)and pin(b)=={k:expected[k]for k in("bytes","sha256")},"Exact captured file")
    return b

def put(path,body):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("xb")as stream:stream.write(body)
    p.chmod(0o444);return pin(body)

class Engine:
    def __init__(self,profile,out,deadline):
        self.profile=profile;self.out=out;self.deadline=deadline;self.commands=[];self.owned=[];self.sequence=0
        self.binary=profile["docker_binary"]
        need(Path(self.binary).is_absolute(),"Explicit existing local Docker binary")
        need(profile["docker_host"].startswith("unix:///"),"Only selected local Docker socket")
        need(profile["image"].startswith("sha256:")and len(profile["image"])==71,"Exact preexisting image digest")
        config=out/"empty-docker-config";config.mkdir();put(config/"config.json",b"{}\n")
        self.env={"PATH":os.defpath,"DOCKER_HOST":profile["docker_host"],"DOCKER_CONFIG":str(config)}
    def call(self,args,seconds=10,cap=2_000_000):
        end=min(self.deadline,time.monotonic()+seconds);need(end>time.monotonic(),"Original native deadline")
        self.sequence+=1;seq=self.sequence;p=None;sel=None;buf={"stdout":bytearray(),"stderr":bytearray()}
        rec={"sequence":seq,"argv":[self.binary,*args],"returncode":None}
        try:
            p=subprocess.Popen([self.binary,*args],env=self.env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
            sel=selectors.DefaultSelector()
            for name,pipe in(("stdout",p.stdout),("stderr",p.stderr)):
                os.set_blocking(pipe.fileno(),False);sel.register(pipe,selectors.EVENT_READ,name)
            while sel.get_map():
                left=end-time.monotonic();need(left>0,"Native CLI stream deadline")
                for key,_ in sel.select(min(.05,left)):
                    b=os.read(key.fileobj.fileno(),min(65536,cap-len(buf[key.data])+1))
                    if not b:sel.unregister(key.fileobj);continue
                    buf[key.data].extend(b);need(len(buf[key.data])<=cap,"Bounded full native CLI stream")
            remaining=end-time.monotonic();need(remaining>0,"Native CLI EOF remaining deadline")
            rec["returncode"]=p.wait(timeout=remaining)
            return rec["returncode"],bytes(buf["stdout"]),bytes(buf["stderr"])
        except BaseException as exc:
            rec["failure"]=type(exc).__name__+": "+str(exc);raise
        finally:
            if p is not None:
                try:os.killpg(p.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                try:p.wait(timeout=.25)
                except subprocess.TimeoutExpired:rec["cleanup_unconfirmed"]=True
                rec["returncode"]=p.poll()
                for pipe in(p.stdout,p.stderr):
                    if pipe is not None:pipe.close()
            if sel is not None:sel.close()
            for name,body in buf.items():
                rec[name]=put(self.out/"commands"/f"{seq:06d}-{name}.bin",bytes(body))
            put(self.out/"commands"/f"{seq:06d}.json",encode(rec));self.commands.append(rec)
    def inspect(self,kind,name):
        args=["volume","inspect",name]if kind=="volume"else["inspect","--type","container",name]
        rc,out,err=self.call(args)
        need(rc==0,"Successful original resource inspection")
        rows=decode(out);need(type(rows)is list and len(rows)==1,"One inspected resource")
        obj=rows[0];need(obj["Name"]==(name if kind=="volume"else"/"+name),"Exact owned name")
        return obj
    def create(self,kind,name,args):
        cmd=["volume","inspect",name]if kind=="volume"else["inspect","--type","container",name]
        rc,out,err=self.call(cmd)
        need(absence(rc,out.decode(),err.decode(),kind,name),"Exact resource absent before creation")
        row={"kind":kind,"name":name,"attempted_before_dispatch":True,"identity":None};self.owned.append(row)
        put(self.out/"ownership"/f"{len(self.owned):03d}-intent.json",encode(row))
        rc,_,_=self.call(args);need(rc==0,"Native resource create")
        obj=self.inspect(kind,name)
        row["identity"]=obj["Id"]if kind=="container"else[obj["Name"],obj["CreatedAt"],obj["Mountpoint"],obj["Driver"],obj.get("Options")]
        put(self.out/"ownership"/f"{len(self.owned):03d}-created.json",encode(row))
        return obj,row
    def cleanup_one(self,row):
        result={"kind":row["kind"],"name":row["name"],"identity":row["identity"],"absence_verified":False}
        try:
            need(row["identity"]is not None,"Unknown created identity cannot be blindly deleted")
            obj=self.inspect(row["kind"],row["name"])
            now=obj["Id"]if row["kind"]=="container"else[obj["Name"],obj["CreatedAt"],obj["Mountpoint"],obj["Driver"],obj.get("Options")]
            need(now==row["identity"],"Same owned immutable resource")
            target=row["identity"]if row["kind"]=="container"else row["name"]
            self.call(["rm","--force",target]if row["kind"]=="container"else["volume","rm",target],seconds=3)
            checks=[]
            for name in([row["name"],row["identity"]]if row["kind"]=="container"else[row["name"]]):
                rc,out,err=self.call(["inspect","--type","container",name]if row["kind"]=="container"else["volume","inspect",name],seconds=3)
                checks.append(absence(rc,out.decode(),err.decode(),row["kind"],name))
            result["absence_verified"]=all(checks)
        except BaseException as exc:result["reason"]=type(exc).__name__+": "+str(exc)
        return result

def safe_mount(source,dest,readonly=True,volume=False):
    need(not any(c in str(source)for c in(",","\n","\r")),"Literal Docker mount source")
    return f"type={'volume'if volume else'bind'},src={source},dst={dest}"+(",volume-nocopy"if volume else"")+(",readonly"if readonly else"")

def verify_container(obj,name,image,mounts,memory,worker,argv):
    h,c,s=obj["HostConfig"],obj["Config"],obj["State"]
    need(obj["Name"]=="/"+name and obj["Image"]==image and c["Image"]==image,"Exact immutable runtime image")
    need(s["Status"]=="created"and not s["Running"]and s["Pid"]==0,"Inspect before original start")
    need(h["NetworkMode"]=="none"and h["ReadonlyRootfs"]and not h["Privileged"]and not h.get("Devices")and not h.get("DeviceRequests")and not h.get("PortBindings"),"Offline readonly unprivileged namespace")
    need(h.get("PidMode")!="host"and h.get("IpcMode")!="host"and h.get("CgroupnsMode")=="private","Private PID/IPC/cgroup namespaces")
    need(h["Memory"]==h["MemorySwap"]==memory and h["NanoCpus"]==1_000_000_000 and h["PidsLimit"]==64,"Exact physical resource ceilings")
    need(h.get("CapDrop")==["ALL"]and set(h.get("CapAdd")or[])==(set(("KILL","SETUID","SETGID"))if worker else set()),"Only trusted PID1 identity/cleanup capabilities")
    need("no-new-privileges:true"in(h.get("SecurityOpt")or[])and c["User"]=="0:0","Trusted supervisor only; child must drop all effective/permitted/ambient caps")
    need(c["Entrypoint"]==["python3"]and c["Cmd"]==argv and not h["AutoRemove"],"Exact supervisor command and original lifecycle")
    observed={x["Destination"]:x for x in obj["Mounts"]if x["Type"]!="tmpfs"}
    need(set(observed)==set(mounts),"No unselected data/state/target mounts")
    for dest,want in mounts.items():
        got=observed[dest];actual=got.get("Name")if want["volume"]else got["Source"]
        same=actual==want["source"]or(not want["volume"]and str(want["source"]).startswith("/Users/")and actual=="/host_mnt"+want["source"])
        need(same and got["RW"]is(not want["readonly"]),"Exact physical mount source/mode")
    need(h["RestartPolicy"]["Name"]in("","no"),"No hidden restarts")

def stage_inputs(request,root):
    root.mkdir();public={}
    def artifact(role,art):
        name=role+".json";b=read(art["path"],art,100_000_000);put(root/name,b)
        public[role]={"path":"/inputs/"+name,**pin(b)}
        if role=="knowledge_view":
            view=decode(b);directory=Path(art["path"]).parent
            for member in view["files"]:
                name=relative(member["path"]).as_posix()
                put(root/name,read(directory/name,member,100_000_000))
        if role=="training_view":
            view=decode(b);directory=Path(art["path"]).parent
            for key in("features_member","training_rows_member","inner_validation_plan_member"):
                member=view[key];name=relative(member["path"]).as_posix()
                put(root/name,read(directory/name,member,100_000_000))
    state=None
    for item in request["inputs"]:
        if "role"in item:artifact(item["role"],item["artifact"])
        elif "training_state"in item:state=item["training_state"]
        elif "opaque_query_nonce"in item:
            artifact("query",item)
        elif "opaque_episode_nonce"in item:
            artifact("training_view",item)
        else:raise ValueError("Unknown protected input capability")
    actual_input_bytes=sum(p.stat().st_size for p in root.rglob("*")if p.is_file())
    need(actual_input_bytes<=request["budget_remaining"]["input_view_bytes"],"Complete aggregate input view cap, including knowledge")
    return public,state


def validate_state(actual,kind,cap):
    """Typed non-executable serialization only; no model/semantic-fit attestation."""
    body=read(actual["path"],actual,cap)
    if kind=="json":decode(body);return
    if kind=="raw_float64":
        need(len(body)%8==0,"Whole raw float64 elements");return
    import ast,struct
    need(body[:8]==b"\x93NUMPY\x01\x00"and len(body)>=10,"Exact NPY1 format")
    n=struct.unpack("<H",body[8:10])[0]
    need(10+n<=len(body)and body[10+n-1:10+n]==b"\n","Complete NPY1 header")
    h=ast.literal_eval(body[10:10+n].decode("ascii"))
    need(type(h)is dict and set(h)=={"descr","fortran_order","shape"}and h["descr"]=="<f8"and h["fortran_order"]is False,"Nonobject little-endian C float64 only")
    need(type(h["shape"])is tuple and all(type(x)is int and x>=0 for x in h["shape"]),"Typed complete array shape")
    size=8
    for dimension in h["shape"]:
        size*=dimension;need(size<=cap,"Declared complete state array bounded")
    need(len(body)==10+n+size,"Exact state EOF; no trailing archive/pickle")

def main():
    request=decode(Path(sys.argv[1]).read_bytes());destination=Path(sys.argv[2])
    need(NATIVE_DEPLOYMENT,"Native scientific deployment disabled in this source release")
    profile=request["runtime_profile"];out=destination.parent/"native";out.mkdir()
    started=time.monotonic();end=started+request["budget_remaining"]["wall_seconds"];engine=Engine(profile,out,end-12)
    attempt={"schema":"n097-native-attempt-v1","request_identity":pin(encode(request)),"status":"started","cleanup":[],"physical_enforcement_only":True}
    worker_row=None;holder_row=None;volume_row=None;artifacts={}
    try:
        src=out/"programme";src.mkdir()
        closure=request["source_closure"]
        for row in closure["files"]:
            name=relative(row["path"]);put(src/name,read(Path(closure["root"])/name,row,100_000_000))
        inputs,state=stage_inputs(request,out/"inputs")
        helpers={}
        for role in("monitor","holder"):
            selected=profile["helper_sources"][role];body=read(selected["path"],selected,200000)
            helpers[role]=out/(role+".py");put(helpers[role],body)
        operation=request["operation"]
        need(operation in request["entrypoints"],"Actual submitted operation entrypoint")
        worker={**request["worker_view"],"entrypoint":request["entrypoints"][operation],
                "input_capabilities":inputs,"budget":{**request["budget_remaining"],"threads":1},
                "reference_recipe":request.get("reference_recipe"),
                "frozen_state":None if state is None else {"root":"/state","files":[{**row,"format":state["formats"][row["path"]]}for row in state["files"]]}}
        put(out/"inputs/worker_request.json",encode(worker))
        suffix=uuid.uuid4().hex;vn="n097-volume-"+suffix;hn="n097-holder-"+suffix;wn="n097-worker-"+suffix
        cap=request["budget_remaining"]["scratch_bytes"]-16777216
        need(cap>0,"Combined output/tmp plus16MiB shared-memory scratch budget")
        options=f"size={cap},nr_inodes=10000,mode=0755,uid=0,gid=0,nosuid,nodev,noexec"
        volume,volume_row=engine.create("volume",vn,["volume","create","--driver","local","--opt","type=tmpfs","--opt","device=tmpfs","--opt","o="+options,vn])
        need(volume["Driver"]=="local"and volume["Options"]=={"type":"tmpfs","device":"tmpfs","o":options},"Memory-backed exact output volume")
        def create(name,worker_flag,mounts,command,memory):
            args=["create","--pull","never","--name",name,"--network","none","--read-only","--user","0:0","--cap-drop","ALL",
                  "--security-opt","no-new-privileges:true","--memory",str(memory),"--memory-swap",str(memory),"--cpus","1",
                  "--pids-limit","64","--cgroupns","private","--ipc","private","--shm-size","16777216","--restart","no","--log-driver","none"]
            if worker_flag:
                args+=["--env","N097_SOURCE_REQUEST_ID="+json.dumps(pin(encode(request)),sort_keys=True)]
                for capability in("KILL","SETUID","SETGID"):args+=["--cap-add",capability]
            for dest,row in mounts.items():args+=["--mount",safe_mount(row["source"],dest,row["readonly"],row["volume"])]
            args+=["--entrypoint","python3",profile["image"],*command]
            obj,row=engine.create("container",name,args);verify_container(obj,name,profile["image"],mounts,memory,worker_flag,command)
            return obj,row
        hm={"/trusted/holder.py":{"source":str(helpers["holder"].absolute()),"readonly":True,"volume":False},
            "/capture":{"source":vn,"readonly":True,"volume":True}}
        _,holder_row=create(hn,False,hm,["-I","-B","/trusted/holder.py","hold"],134217728)
        need(engine.call(["start",hn])[0]==0,"Readonly holder starts before producer")
        wm={"/trusted/monitor.py":{"source":str(helpers["monitor"].absolute()),"readonly":True,"volume":False},
            "/programme":{"source":str(src.absolute()),"readonly":True,"volume":False},
            "/inputs":{"source":str((out/"inputs").absolute()),"readonly":True,"volume":False},
            "/work":{"source":vn,"readonly":False,"volume":True}}
        if state is not None:
            frozen=out/"frozen-state";frozen.mkdir()
            for row in state["files"]:
                name=relative(row["path"]);put(frozen/name,read(Path(state["root"])/name,row,request["budget_remaining"]["trained_state_bytes"]))
            wm["/state"]={"source":str(frozen.absolute()),"readonly":True,"volume":False}
        _,worker_row=create(wn,True,wm,["-I","-B","/trusted/monitor.py"],request["budget_remaining"]["memory_bytes"])
        need(engine.call(["start",wn])[0]==0,"Original worker start")
        left=end-time.monotonic()-18;need(left>0,"Full remaining work and cleanup envelope")
        wait=engine.call(["wait",wn],seconds=left,cap=100000);need(wait[0]==0,"Original Docker wait completes")
        stopped=engine.inspect("container",wn)["State"]
        need(not stopped["Running"]and stopped["Pid"]==0,"Original producer stopped")
        removal=engine.cleanup_one(worker_row);attempt["cleanup"].append(removal)
        need(removal["absence_verified"],"Producer absent before immutable output capture")
        rc,b,_=engine.call(["exec",hn,"python3","-I","/trusted/holder.py","inventory",str(cap)],cap=4_000_000)
        need(rc==0,"Readonly complete output inventory");inventory=decode(b)
        for row in inventory["files"]:
            name=relative(row["path"]);target=out/"captured"/name;target.parent.mkdir(parents=True,exist_ok=True)
            h=hashlib.sha256();total=0
            with target.open("xb")as stream:
                while total<row["bytes"]:
                    rc,b,_=engine.call(["exec",hn,"python3","-I","/trusted/holder.py","chunk",str(name),str(total),"1048576"],cap=1_500_000)
                    need(rc==0,"Original bounded output chunk");part=decode(b);raw=base64.b64decode(part["base64"],validate=True)
                    need(part["path"]==str(name)and part["offset"]==total and len(raw)==part["bytes"]and raw,"Exact complete chunk sequence")
                    stream.write(raw);h.update(raw);total+=len(raw)
            need(total==row["bytes"]and h.hexdigest()==row["sha256"],"Complete immutable output bytes")
            artifacts[str(name)]={"path":str(target.absolute()),"bytes":total,"sha256":row["sha256"]}
        need("control/MONITOR.json"in artifacts,"Protected original PID1 evidence")
        monitor=decode(read(artifacts["control/MONITOR.json"]["path"],artifacts["control/MONITOR.json"],1_000_000))
        attempt["monitor"]=monitor;attempt["artifacts"]=artifacts
        if "results/PRODUCTS.json"in artifacts:
            manifest=decode(read(artifacts["results/PRODUCTS.json"]["path"],artifacts["results/PRODUCTS.json"],1_000_000))
            need(set(manifest)=={"schema","status","products","failure_reasons"}and manifest["schema"]=="n097-worker-products-v1","Exact untrusted product manifest")
            need(manifest["status"]in("complete","failed","abstain"),"Declared product status")
            products=manifest["products"];bound={}
            allowed={"train":{"training_state"},"investigate":{"training_state","training_program"},
                     "predict":{"prediction"},"query_analysis":{"query_program"},"query_execute":{"prediction"},
                     "reference_train":{"reference_bank"},"reference_predict":{"prediction"},"interpret":{"interpretation"}}
            need(set(products)<=allowed[operation],"Only products declared for current operation")
            required={"investigate":{"training_state"}}.get(operation,allowed[operation])
            if manifest["status"]=="complete":need(required<=set(products),"Complete operation requires every actual product")
            def member(name):
                relative(name);key="results/"+name;need(key in artifacts,"Actual captured product member")
                return artifacts[key]
            for role,product in products.items():
                if role in("training_state","query_program","training_program"):
                    need(type(product["files"])is list and product["files"],"Complete captured source/state member set")
                    rows=[]
                    for item in product["files"]:
                        name=item["path"];actual=member(name);rows.append({"path":name,"bytes":actual["bytes"],"sha256":actual["sha256"]})
                        if role=="training_state":
                            need(item["format"]in("json","npy_float64","raw_float64"),"Declared non-executable state formats; no pickle")
                            validate_state(actual,item["format"],request["budget_remaining"]["trained_state_bytes"])
                    need(len({r["path"]for r in rows})==len(rows),"Unique frozen product files")
                    closure={"root":str((out/"captured/results").absolute()),"files":rows,
                             "closure_sha256":pin(encode(rows))["sha256"],"total_bytes":sum(r["bytes"]for r in rows)}
                    if role=="training_state":
                        need(closure["total_bytes"]<=request["budget_remaining"]["trained_state_bytes"],"Complete frozen state byte ceiling")
                        state={**closure,"sealed_before_query":operation in("train","investigate"),"formats":{r["path"]:r["format"]for r in product["files"]}}
                        bound[role]=state
                    else:
                        need(closure["total_bytes"]<=request["budget_remaining"]["outcome_bytes"],"Complete generated source output cap")
                        need(product["entrypoint"]in{r["path"]for r in rows},"Actual captured generated programme entry")
                        bound[role]={"actual_source_closure":closure,"entrypoint":product["entrypoint"]}
                else:
                    captured=member(product["path"])
                    need(captured["bytes"]<=request["budget_remaining"]["outcome_bytes"],"Complete declared outcome cap; no prefix/subset capture")
                    bound[role]=captured
            attempt["bound_products"]=bound;attempt["candidate_product_status"]=manifest["status"]
            attempt["candidate_failure_reasons"]=manifest["failure_reasons"]
        need(monitor["source_request"]==pin(encode(request))and monitor["all_descendants_reaped"],"Original request and full descendant closure")
        attempt["status"]="physical_process_completed"if stopped["ExitCode"]==0 else"physical_process_failed"
    except BaseException as exc:
        attempt.update(status="failed",error_type=type(exc).__name__,reason=str(exc))
    finally:
        engine.deadline=end
        already={r["name"]for r in attempt["cleanup"]if r["absence_verified"]}
        for row in reversed(engine.owned):
            if row["name"]not in already:attempt["cleanup"].append(engine.cleanup_one(row))
        attempt["all_owned_absent"]=len(attempt["cleanup"])==len(engine.owned)and all(r["absence_verified"]for r in attempt["cleanup"])
        attempt["elapsed_seconds"]=time.monotonic()-started;attempt["commands"]=engine.commands
        put(out/"NATIVE_ATTEMPT.json",encode(attempt))
    # Physical evidence is never inflated into a scientific no-fit/tool/model
    # attestation. The complete accepted scientific rule remains an open gate.
    receipt={"schema":"n097-runtime-worker-receipt-v1","request_identity":pin(encode(request)),
        "environment":request["runtime_environment"],"contract":request["contract"],
        "source_closure":request["source_closure"],"inputs":request["inputs"],"outputs":attempt.get("bound_products",{}),
        "actual_processes":attempt,"actual_tool_operations":None,"training_state_identity":state if 'state'in locals()else None,
        "resources":{"cpu_seconds":None,"wall_seconds":attempt["elapsed_seconds"],"memory_bytes":None,
                     "input_view_bytes":None,"scratch_bytes":None,"trained_state_bytes":None,"outcome_bytes":None,
                     "model_input_tokens":None,"model_output_tokens":None,"tool_calls":None},
        "descendants_closed":attempt["all_owned_absent"],"isolation_qualification":None,
        "status":"physical_only_semantic_qualification_unavailable",
        "failure_reasons":["Arbitrary Python no-query-fitting and complete dynamic tool/model accounting are not established by physical isolation."]}
    if "monitor"in attempt:
        m=attempt["monitor"];receipt["resources"]["cpu_seconds"]=(m["final_cgroup"]["cpu_microseconds"]-m["initial_cgroup"]["cpu_microseconds"])/1e6
        receipt["resources"]["memory_bytes"]=m["final_cgroup"]["memory_peak_bytes"]
        receipt["physical_cgroup_observations"]=m
    put(destination,encode(receipt))
    return 2

"""Reused exact strict missing-resource parser; no runtime contract changes."""
import json

def absence(returncode,stdout,stderr,kind,name):
    """Only exact direct or single-message JSON Docker missing-resource errors.

    Preserve resource-name case, reject ambiguous/extra keys, and never use
    substring matching. JSON does not convert a denied/transport error to absence.
    """
    if (type(returncode)is not int or returncode!=1 or type(stdout)is not str or type(stderr)is not str
            or len(stdout.encode())>64 or stdout.strip()not in ('','[]') or len(stderr.encode())>4096
            or kind not in ('volume','container') or type(name)is not str):return False
    observed=stderr.strip()
    bodies=({f'get {name}: no such volume'}if kind=='volume'else {f'No such container: {name}',f'no such container: {name}'})
    direct=({f'Error response from daemon: get {name}: no such volume',f'Error: No such volume: {name}',
             f'error response from daemon: get {name}: no such volume',f'error: no such volume: {name}'}if kind=='volume'
            else {f'Error: No such object: {name}',f'Error response from daemon: No such container: {name}',
                  f'error: no such object: {name}',f'error response from daemon: no such container: {name}'})
    if observed in direct:return True
    prefix='Error response from daemon: '
    if not observed.startswith(prefix):return False
    def unique_object(pairs):
        value={}
        for key,item in pairs:
            if key in value:raise ValueError('duplicate Docker error key')
            value[key]=item
        return value
    try:
        wrapper=json.loads(observed[len(prefix):],object_pairs_hook=unique_object)
    except (ValueError,TypeError,RecursionError):return False
    return type(wrapper)is dict and set(wrapper)=={'message'} and type(wrapper['message'])is str and wrapper['message']in bodies


if __name__=="__main__":raise SystemExit(main())
