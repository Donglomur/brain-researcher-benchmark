"""Full five-mode source controller with one cumulative budget and no automatic retries."""
from pathlib import Path
import os,json,copy
from .common import need,exact,canonical,decode,object_pin,pin,read,read_json,publish,fresh_dir,absolute,relative,Ledger,observed_write
from .deployment import load,code_snapshot,method,qualified_outer
from .packets import collect,compile_jobs
from .legacy.scorer_core import public_contract,admit,score
from .development import validate
from .native import LinuxExecutor,NativeFailure,private_mount_namespace
from .provider import ProviderBridge
from .budgets import MethodMeter,comparison
from .evidence import Reserve
from .execution import job as execute_job
def snapshot(source,manifest,destination,ledger):
    """Only exact source members; performed before any current prepared context is read."""
    root=fresh_dir(destination);exact(manifest,["schema","files"])
    need(manifest["schema"]=="neural047-source-freeze-v1","Exact source graph");seen=set()
    for row in manifest["files"]:
        exact(row,["path","bytes","sha256"]);name=relative(row["path"]);need(name not in seen,"No duplicate source");seen.add(name)
        body=read(absolute(source)/name,{k:row[k] for k in ("bytes","sha256")},ledger,"selected method source")
        dest=root/name;dest.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        ledger.charge("write_bytes",len(body),"immutable method snapshot")
        with dest.open("xb") as f:
            n=observed_write(f.write,body,ledger,"immutable method snapshot")
            need(n==len(body),"Complete immutable method snapshot")
            f.flush();os.fsync(f.fileno())
        dest.chmod(0o444)
    for d in sorted((x for x in root.rglob("*") if x.is_dir()),key=lambda p:len(p.parts),reverse=True):d.chmod(0o555)
    root.chmod(0o555);return root
def load_prepared(root,manifest_pin,ledger):
    root=absolute(root);manifest=read_json(root/"MANIFEST.json",manifest_pin,ledger,"full prepared manifest")
    exact(manifest,["schema","files","packet_id"]);need(manifest["schema"]=="neural047-prepared-programme-v1","Prepared source generation")
    mapping={}
    for row in manifest["files"]:
        exact(row,["path","bytes","sha256"]);name=relative(row["path"]);need(name not in mapping and "/" not in name,"Flat unique exact prepared files");mapping[name]={k:row[k] for k in ("bytes","sha256")}
    need({"panel.json","targets.json","audit.json","programme.json"}<=set(mapping),"All prepared roles")
    panel=read_json(root/"panel.json",mapping["panel.json"],ledger,"label-free all-animal panel");public_contract(panel)
    need(panel["packet_id"]==manifest["packet_id"],"Same full preparation")
    wanted={"panel.json","targets.json","audit.json","programme.json"}|{f["fold_id"]+"_"+a+".json" for f in panel["folds"] for a in ("N","B","NB")}
    need(set(mapping)==wanted,"No missing/extra source context")
    programme=read_json(root/"programme.json",mapping["programme.json"],ledger,"exact programme")
    return panel,mapping,programme
def validate_programme(panel,programme,packets):
    recomputed=compile_jobs({"panel":panel,"folds":packets})
    need(programme==recomputed,"Complete programme and fit-count equations, no fabricated job list")
    return recomputed
def private_report(panel,collections,load_targets):
    """Admit every mode before one private read; abstention in any mode prevents all target access."""
    admitted={mode:admit(panel,c) for mode,c in collections.items()}
    need(set(admitted)=={"F","I","R0","R1","R2"},"All modes")
    if any(abstentions for _,abstentions in admitted.values()):
        return {"schema":"neural047-full-grade-v1","status":"abstained","private_reads":0,"grades":None}
    targets=load_targets();grades={mode:score(panel,c,lambda:targets) for mode,c in collections.items()}
    return {"schema":"neural047-full-grade-v1","status":"scored","private_reads":1,"grades":grades,
            "scope":"prospective retrospective public-development cross-animal task","scientific_qualification":False}
def operate(request):
    exact(request,["deployment_path","deployment_pin","limits","failure_evidence","prepared_root","prepared_manifest_pin","method_F_root","method_F_manifest_path","method_I_root","method_I_manifest_path","programme_root","programme_manifest_path","work_root"])
    L=Ledger(request["limits"]);E=Reserve(L,request["failure_evidence"]);work=absolute(request["work_root"]);owned=False
    results=[];receipts=[];completed=[];report=None;failure=None;primary=None;meters={};current_job=None
    try:
        work=fresh_dir(work);owned=True;(work/"receipts").mkdir(mode=0o700)
        dep,docs=load(request["deployment_path"],request["deployment_pin"],L)
        F=method(docs["candidate_F"],"F");I=method(docs["candidate_I"],"I")
        method_comparison=comparison(F,I)
        meters={mode:MethodMeter(L,contract) for mode,contract in (("F",F),("I",I))}
        runtime=docs["runtime_environment"]
        exact(runtime,["schema","source_manifest_pin","python_executable","native_profile_pin","version_recipe","runtime_image_pin"])
        need(runtime["schema"]=="neural047-runtime-environment-v1","Qualified runtime schema")
        qualified_outer(docs["native_execution"])
        need({k:dep["authorities"]["native_execution"][k] for k in ("bytes","sha256")}==runtime["native_profile_pin"],"Original-byte runtime/native qualification join")
        need(docs["reference_numerics"]["source_manifest_pin"]==runtime["source_manifest_pin"],"Independent numerical qualification binds this exact source")
        need(docs["retention_feasibility"]["prepared_manifest_pin"]==request["prepared_manifest_pin"],"Qualified full retention, not subset")
        methods={}
        for mode,contract in [("F",F),("I",I)]:
            scope=meters[mode].context("pre-release source snapshot")
            try:
                manifest=read_json(request["method_"+mode+"_manifest_path"],contract["source_manifest_pin"],scope,"globally precommitted method manifest")
                methods[mode]=snapshot(request["method_"+mode+"_root"],manifest,work/("source_"+mode),scope)
            finally:scope.finish()
        manifest=read_json(request["programme_manifest_path"],runtime["source_manifest_pin"],L,"qualified programme source graph")
        source=snapshot(request["programme_root"],manifest,work/"reference_source",L)
        # Method snapshots are frozen before current run releases any fold context.
        panel,pins,programme=load_prepared(request["prepared_root"],request["prepared_manifest_pin"],L)
        packetmap={}
        for fold in panel["folds"]:
            for arm in ("N","B","NB"):
                name=fold["fold_id"]+"_"+arm+".json"
                packet=read_json(absolute(request["prepared_root"])/name,pins[name],L,"complete context authentication")
                validate(packet);need(packet["packet_id"]==panel["packet_id"] and packet["test_group"]==fold["test_group"] and [r["case_key"] for r in packet["query"]]==fold["case_keys"],"Exact fold case join")
                key=(packet["fold_id"],packet["arm"]);need(key==(fold["fold_id"],arm),"Source fold identity");packetmap[key]=packet
        validate_programme(panel,programme,list(packetmap.values()))
        # Reserve the whole possible original-evidence graph before the first producer.
        n=len(panel["folds"]);needed=0
        for mode in ("F","I","R0","R1","R2"):
            caps=docs["native_execution"]["limits"]
            leaf=meters[mode].limits["per_context"] if mode in meters else caps
            perjob=E.policy["job_receipt_bytes"]+min(caps["stdout_bytes"],leaf["stdout_bytes"])+min(caps["stderr_bytes"],leaf["stderr_bytes"])
            part=3*n*perjob
            if mode=="I":
                bridge=docs["provider_bridge"];calls=min(meters["I"].limits["all_contexts"]["provider_requests"],3*n*leaf["provider_requests"])
                part+=calls*(bridge["response_bytes"]+bridge["stderr_bytes"]+E.policy["provider_receipt_bytes"])
            needed+=part
            if mode in meters:need(meters[mode].used["write_bytes"]+part<=meters[mode].limits["all_contexts"]["write_bytes"],"Method cannot reserve mandatory original evidence")
        need(needed<=E.remaining,"Whole original evidence graph does not fit reserved total")
        private_mount_namespace()
        for job in programme["jobs"]:
            L.live();current_job=job["job_id"]
            packet=packetmap[(job["fold_id"],job["arm"])]
            need(object_pin(packet)==job["input_pin"],"Exact job input")
            mode=job["mode"];provider_profile=None
            scope=meters[mode].context(job["job_id"],docs["native_execution"]) if mode in meters else L
            profile=scope.native if mode in meters else docs["native_execution"]
            if mode.startswith("R"):
                root=source;argv=[runtime["python_executable"],"-I","/method/reference_entry.py","--reference",mode]
            else:
                contract=F if mode=="F" else I;root=methods[mode];argv=contract["argv"]
                if mode=="I":
                    need(docs["provider_bridge"]["model"]==I["provider_model"],"Exact global I policy model")
                    provider_profile=docs["provider_bridge"]
            outputs,receipt=execute_job(job,packet,work,root,argv,profile,scope,E,provider_profile)
            prediction=decode(outputs["prediction.json"])
            if mode.startswith("R"):
                evidence=decode(outputs["reference.json"])
                need(evidence["reference"]==mode and evidence["fits"]==(1 if mode=="R0" else (5 if mode=="R1" else 4)*(len(panel["folds"])-1)+1),"Complete counted reference development")
                trace=read(work/job["job_id"]/"logs"/"stdout.txt",{"bytes":receipt["stdout"]["retained_bytes"],"sha256":receipt["stdout"]["sha256"]},L,"original reference fit lifecycle")
                events=[decode(line) for line in trace.splitlines()]
                need(len(events)==2*evidence["fits"],"Every original reference fit has start and end")
                for seq in range(evidence["fits"]):
                    begin,end=events[seq*2:seq*2+2]
                    need(begin["schema"]==end["schema"]=="neural047-fit-lifecycle-v1" and begin["sequence"]==end["sequence"]==seq and begin["event"]=="start" and end["event"]=="end","Unbroken fit lifecycle")
            results.append({"mode":mode,"job_id":job["job_id"],"prediction":prediction})
            receipts.append(receipt);completed.append(job["job_id"])
        collections=collect(panel,results)
        # All required outputs must be committed to root custody before any private targets.
        for mode,value in collections.items():publish(work/(mode+"_collection.json"),value,L,"complete "+mode+" prediction commitment")
        report=private_report(panel,collections,lambda:read_json(absolute(request["prepared_root"])/"targets.json",pins["targets.json"],L,"one final private target read"))
        publish(work/"GRADE.json",report,L,"full protected grade")
        return {"status":"complete","completed":completed,"report":report,"accounting":L.summary(compact=True),"method_comparison":method_comparison,"method_summaries":{k:v.summary(compact=True) for k,v in meters.items()},"scientific_qualification":False}
    except BaseException as error:
        primary=error
        failure={"type":type(error).__name__,"message":str(error)[:1024],"completed":completed,"scientific_qualification":False}
        if isinstance(error,NativeFailure):failure["original_native_receipt"]=error.receipt
        raise
    finally:
        terminal={"schema":"neural047-original-programme-terminal-v2","completed":completed,"current_job":current_job,"failure":failure,"accounting":L.summary(compact=True),"method_summaries":{k:v.summary(compact=True) for k,v in meters.items()},"evidence_reservation":E.summary(),"science_claim":False,
                  "terminal_own_persistence":"not_self_attested; outer original command completion required"}
        E.terminal_or_fallback(work/"TERMINAL.json" if owned else None,terminal,primary)

