"""Whole-program authentic coordinator. No scientific authority is created here.

Every concrete deployment, producer and scientific profile must be independently
qualified and source-pinned. BUILD ONLY leaves those admissions absent. CPU Linux
isolation is implemented; whole-paper multi-device execution remains a named gap.
"""
from contextlib import ExitStack
import os
from .strict import Root, Clock, require, canonical_bytes, digest, decode
from .authority import Authority
from .profiles import admit_profile, CONDITIONS
from .catalogue import compile_manifest, condition_job
from .programme import build_contracts, ordered_groups
from .access import make_view, paired_views
from .views import verify_tree
from .sandbox import command, Cgroup
from .process import launch_observe
from .collection import collect, complete_collection
from .barrier import seal
from .costs import Ledger
from .scoring import score_job, report, bind_operands
from .errors import SourceGap
from .dataflow import materialize

def exact_stage_plan(authority, manifest):
    plans=authority.receipt.get("stage_plans",{})
    expected={condition+":"+j["job_id"] for condition in CONDITIONS for j in manifest["jobs"]}
    require(set(plans)==expected,"full four-condition stage graph")
    for key,stages in plans.items():
        require([s["role"] for s in stages]==["constructor","reference","candidate","exporter"],"complete native/candidate/exporter graph")
        for s in stages:
            require(s.get("source_pin") and s.get("input_manifest") and s.get("program_manifest") and s.get("output_contract"),"incomplete concrete stage")
            require(s.get("all_output_paths_fresh") is True,"stage state reuse")
            if s["role"]=="reference":require(s.get("reference_competence_evidence"),"unqualified native reference")
    return plans

def execute_stage(authority, stage, job, condition, deployment, ledger, evidence, clock, upstream):
    """Real OS invocation; a function return can never stand in for native evidence."""
    key=condition+"-"+job["job_id"]+"-"+stage["role"]
    ledger.begin(key,stage["role"]);obs=None
    try:
        p=authority.producer(stage["producer_id"])
        require(p["source"]==stage["source_pin"],"stage producer source binding")
        require(p["output_contract"]==stage["output_contract"],"qualified output contract changed")
        require(stage["roots"]["rootfs"]==deployment["rootfs"],"unqualified dependency root")
        rootspec=stage["roots"]
        require(set(rootspec)=={"rootfs","program","inputs","output"},"mount role roster")
        paths=list(rootspec.values())+[authority.receipt["target_root"],evidence.path]
        require(len(set(paths))==len(paths),"private/public root collision")
        for a in paths:
            for b in paths:
                require(a==b or not b.startswith(a+"/"),"nested custody/mount roots")
        with ExitStack() as stack:
            roots={k:stack.enter_context(Root(v,private=k in ("inputs","output"))) for k,v in rootspec.items()}
            require(not os.listdir(roots["output"].fd),"output must be exclusive and empty")
            dynamic=materialize(stage,upstream,roots["inputs"],clock=clock,ledger=ledger,cap=deployment["mount_byte_cap"])
            for role in ("program","inputs"):
                rows=stage["input_manifest" if role=="inputs" else "program_manifest"]+(dynamic if role=="inputs" else [])
                observed=verify_tree(roots[role],rows,byte_cap=deployment["mount_byte_cap"],file_cap=deployment["mount_file_cap"],clock=clock)
                ledger.charge(read_bytes=observed["authenticated_bytes"])
            inv=roots["inputs"].json("invocation.json",2*1024*1024,clock=clock)
            require(inv["scientific_job"]["job_id"]==job["job_id"] and inv["scientific_job"]["condition"]==condition,"invocation job binding")
            require(inv["source"]==stage["source_pin"],"native invocation source")
            limits={**deployment["resource_limits"],**job["cost_ceiling"]}
            args,fds=command({**deployment["sandbox"],**p["sandbox_binding"]},roots,limits,clock)
            parent=stack.enter_context(Root(deployment["cgroup_parent"]))
            group=Cgroup(parent,key,limits,clock)
            try:obs=launch_observe(args,fds,group,limits,clock,evidence,key)
            finally:group.close()
            require(obs.get("status")=="complete","native stage failed; no automatic retry")
            effective={**job,"source_profile_sha256":authority.receipt["scientific_profile_sha256"],
                       "producer_source_sha256":stage["source_pin"]["sha256"],
                       "contract_sha256":digest(canonical_bytes(stage["output_contract"]))}
            result=collect(roots["output"],effective,condition,stage["output_contract"],obs,clock=clock,total_cap=limits["output_bytes"])
            ledger.charge(read_bytes=result["read_bytes"],output_bytes=result["output_bytes"])
            ledger.finish(key,"complete",obs)
            result["materialized_predecessor_inputs"]=dynamic
            return result
    except BaseException as exc:
        ledger.finish(key,"failed",obs,exc)
        raise

def run(authority_root, receipt_path, receipt_pin, programme, profile, coordinates, metric_specs,
        producer_map, design_sha, source_sha, banks, global_limits):
    """No candidate target read occurs until all four full outputs are retained.

    The public CLI does not call this while deployment gaps remain. Calling this
    directly still requires the exact independently selected operator receipt.
    """
    clock=Clock.begin(global_limits["wall_ns"],global_limits["cleanup_ns"])
    ledger=Ledger(clock,global_limits);evidence=None;outcome=None
    with ExitStack() as stack:
        custody=stack.enter_context(Root(authority_root,private=True))
        try:
            ledger.begin("admission","whole-program admission")
            authority=Authority(custody,receipt_path,receipt_pin,clock=clock)
            profile=admit_profile(profile,design_sha)
            authority.bind(source_sha,digest(canonical_bytes(profile)))
            contracts=build_contracts(programme,coordinates,metric_specs)
            manifest=compile_manifest(profile,contracts,producer_map)
            plans=exact_stage_plan(authority,manifest)
            deployment=authority.receipt["deployment"]
            require(deployment.get("whole_controller_resource_observer") and deployment.get("immutable_sealed_mount_evidence"),"whole controller resources/custody unqualified")
            if deployment.get("multi_device_required",True):
                raise SourceGap("Full paper requires qualified GPU/multi-host execution and timing adapter; CPU adapter cannot substitute")
            evidence=stack.enter_context(Root(authority.receipt["evidence_root"],private=True))
            views={c:make_view(c,authority.receipt["common_view"],authority.receipt["author_view"],authority.receipt["private_targets"]) for c in CONDITIONS}
            paired_views(views["A_R"],views["B_R"]);paired_views(views["A_I"],views["B_I"])
            # Candidate input mounts must physically match the selected view plus
            # its exact job invocation. Native/reference code is never mounted in A.
            for condition in CONDITIONS:
                for job in manifest["jobs"]:
                    stage=plans[condition+":"+job["job_id"]][2]
                    expected=views[condition]["public"]
                    actual=[r for r in stage["input_manifest"] if r["path"]!="invocation.json"]
                    require(actual==expected,"physical candidate input differs from A/B view")
                    require(stage["program_manifest"]==authority.receipt["candidate_programs"][condition],"candidate program/code-view mismatch")
            ledger.finish("admission","complete")
            collected={c:[] for c in CONDITIONS};by_group=ordered_groups()
            # Full source DAG order; final collection is restored to canonical job order.
            for condition in CONDITIONS:
                condition_predecessors={}
                for group in by_group:
                    for job0 in (j for j in manifest["jobs"] if j["group"]==group):
                        job=condition_job(manifest,condition,job0["job_id"])
                        job_clock=clock.child(job["cost_ceiling"]["wall_ns"],job["cost_ceiling"]["cleanup_ns"])
                        results=[];upstream=dict(condition_predecessors)
                        for stage in plans[condition+":"+job["job_id"]]:
                            result=execute_stage(authority,stage,job,condition,deployment,ledger,evidence,job_clock,upstream)
                            results.append(result)
                            upstream[stage["role"]]={"collection":result,"output_root":stage["roots"]["output"]}
                            condition_predecessors[job["job_id"]+":"+stage["role"]]=upstream[stage["role"]]
                        final=results[-1]
                        require(final["contract_sha256"]==job["contract_sha256"],"exporter full scientific contract mismatch")
                        final["all_original_stage_collections"]=results[:-1]
                        collected[condition].append(final)
            order={j["job_id"]:i for i,j in enumerate(manifest["jobs"])}
            commits={c:complete_collection(manifest,c,sorted(collected[c],key=lambda j:order[j["job_id"]])) for c in CONDITIONS}
            for a,b in (("A_R","B_R"),("A_I","B_I")):
                for ca,cb in zip(commits[a]["collections"],commits[b]["collections"]):
                    ia=ca["all_original_stage_collections"][2]["materialized_predecessor_inputs"]
                    ib=cb["all_original_stage_collections"][2]["materialized_predecessor_inputs"]
                    require(ia==ib,"A/B generated candidate input mismatch")
            ledger.begin("assessment_commit","protected full collection barrier")
            permit=seal(manifest,commits,authority.receipt["method_freezes"],evidence,clock)
            ledger.finish("assessment_commit","complete")
            target=stack.enter_context(permit.open_targets(authority,authority.receipt["target_root"]))
            reports={}
            for condition in CONDITIONS:
                grades=[]
                for job in manifest["jobs"]:
                    key=condition+":"+job["job_id"]
                    ledger.begin("grade-"+key,"protected scoring")
                    stage=plans[key][-1]
                    with Root(stage["roots"]["output"],private=True) as output, Root(plans[key][1]["roots"]["output"],private=True) as reference_output:
                        collection=next(c for c in commits[condition]["collections"] if c["job_id"]==job["job_id"])
                        spec=bind_operands(authority.receipt["metric_operands"][key],collection)
                        grade=score_job(job,contracts[job["group"]],spec,output,target,banks,clock,
                                        deployment["scoring_budget"],permit=permit,condition=condition,reference_root=reference_output)
                    ledger.finish("grade-"+key,"complete");grades.append(grade)
                reports[condition]=report(manifest,grades,condition,ledger.record())
            clock.check()
            outcome={"status":"complete","reports":reports,"manifest_sha256":digest(canonical_bytes(manifest))}
            evidence.write_new("full-programme-report.json",canonical_bytes(outcome),global_limits["report_bytes"],clock=clock)
        except BaseException as exc:
            outcome={"status":"failed","error_type":type(exc).__name__,"reason":str(exc)[:2000],"scientific_success":False}
            for key in list(ledger.open):ledger.finish(key,"failed",error=exc)
            if evidence is not None:
                try:evidence.write_new("failed-programme.json",canonical_bytes(outcome),4096,clock=clock,cleanup=True)
                except BaseException as persist:outcome["failure_record_lost"]=type(persist).__name__
        finally:
            outcome=outcome or {"status":"failed","scientific_success":False}
            outcome["original_costs"]=ledger.record()
            if evidence is not None:
                try:outcome["cost_record"]=ledger.retain(evidence,"original-programme-costs.json")
                except BaseException as exc:outcome["status"]="failed";outcome["cost_record_lost"]=type(exc).__name__
            else:outcome["admission_failure_has_no_selected_evidence_root"]=True
    return outcome
