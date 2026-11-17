"""Authenticated external scientific worker protocol; no candidate-code import.

The concrete selected native_launcher.py is operator code, never participant
code. Its physical source is implemented but unqualified; semantic no-query-fit
and dynamic-operation accounting remain explicit unresolved assumptions. The shipped source has deployment disabled.
"""
from pathlib import Path
from .io import need, exact, read, read_json, identity, canonical, write_json, bind_source
from .contract import require_deployment, load
from .process import scientific_driver_execute

REQUIRED_CAPABILITIES = (
 "fresh_process_filesystem_conversation_cache","no_network_or_private_mounts",
 "readonly_sealed_sources_and_states","single_query_capability",
 "no_query_fitting_calibration_normalization","actual_tool_source_capture",
 "all_descendants_closed","aggregate_cpu_wall_rss_io","model_token_cost_accounting",
 "no_cross_fold_arm_setting_seed_state","complete_bounded_output_streams"
)

def qualified_runtime(selection, operator_root):
    require_deployment()
    exact(selection,["schema","launcher","qualification","environment","capabilities","root_execution_review","runtime_profile"])
    need(selection["schema"]=="n097-qualified-runtime-selection-v1","Selected runtime schema")
    # These are protected operator-selected documents; not a candidate-declared
    # boolean. Their byte/source/environment joins are verified independently.
    q=read_json(Path(operator_root)/selection["qualification"]["path"],2_000_000,selection["qualification"])
    review=read_json(Path(operator_root)/selection["root_execution_review"]["path"],2_000_000,selection["root_execution_review"])
    need(q["status"]=="independently_qualified"and review["scientific_execution_authorized"]is True,"Qualified independently selected execution")
    need(q["environment"]==selection["environment"]and q["launcher"]==selection["launcher"],"Actual runtime/source join")
    need(q["capabilities"]==selection["capabilities"]and all(q["capabilities"].get(k)is True for k in REQUIRED_CAPABILITIES),"All semantic isolation/resource mechanisms qualified")
    need(q["runtime_profile"]==selection["runtime_profile"],"Exact native profile joins independent source/runtime review")
    read_json(Path(operator_root)/selection["runtime_profile"]["path"],2_000_000,selection["runtime_profile"])
    read(Path(operator_root)/selection["launcher"]["path"],2_000_000,selection["launcher"])
    return q

class Runtime:
    def __init__(self,selection,operator_root):
        self.selection=selection;self.root=Path(operator_root)
        self.qualification=qualified_runtime(selection,self.root)
        self.profile=read_json(self.root/selection["runtime_profile"]["path"],2_000_000,selection["runtime_profile"])

    def launch(self,request,output):
        require_deployment()
        need(request["schema"]=="n097-worker-request-v1","Exact worker request")
        need(request["runtime_environment"]==self.selection["environment"],"Selected runtime environment")
        request={**request,"runtime_profile":self.profile}
        closure=request["source_closure"]
        checked=bind_source(closure["root"],closure["files"])
        need(all(closure[k]==checked[k]for k in ("files","closure_sha256","total_bytes")),"Actual submitted source bytes before every launch")
        launcher=self.selection["launcher"]
        result=scientific_driver_execute(self.root/launcher["path"],launcher,request,output,
                   wall_seconds=request["budget_remaining"]["wall_seconds"],stream_cap=8_000_000)
        # Original process evidence remains even if subsequent collection fails.
        need(result["status"]=="process_completed"and result["returncode"]==0,"Original runtime launcher completion")
        receipt=read_json(Path(output)/"worker_output.json",16_000_000)
        exact(receipt,["schema","request_identity","environment","contract","source_closure","inputs","outputs",
                       "actual_processes","actual_tool_operations","training_state_identity","resources",
                       "descendants_closed","isolation_qualification","status","failure_reasons"])
        need(receipt["schema"]=="n097-runtime-worker-receipt-v1"and receipt["request_identity"]==identity(canonical(request)),"Controller-created request join")
        need(receipt["environment"]==self.selection["environment"]and receipt["contract"]==request["contract"],"Runtime/contract identity")
        need(receipt["source_closure"]==request["source_closure"]and receipt["inputs"]==request["inputs"],"Actual original source/input joins")
        need(receipt["actual_processes"]and receipt["descendants_closed"]is True,"Original process tree and closure")
        need(receipt["isolation_qualification"]==self.selection["qualification"],"Exact qualified enforcement")
        for resource in ("cpu_seconds","wall_seconds","memory_bytes","input_view_bytes","scratch_bytes",
                         "trained_state_bytes","outcome_bytes","model_input_tokens","model_output_tokens","tool_calls"):
            value=receipt["resources"][resource]
            need(type(value)in(int,float)and value>=0 and value<=request["budget_remaining"][resource],"Complete original resource observation within selected cumulative budget")
        # Operator driver paths must remain in this fresh output namespace;
        # candidate-authored paths are never followed into private storage.
        for role,artifact in receipt["outputs"].items():
            if role in ("query_program","training_program","training_state"):
                if role=="training_state":
                    closure=artifact
                else:
                    closure=artifact["actual_source_closure"]
                # Root is protected collector output, never followed from a candidate manifest.
                root=Path(closure["root"]).absolute()
                need(root.is_relative_to(Path(output).absolute()),"Adaptive source stays in original operation output")
                checked=bind_source(root,closure["files"])
                need(all(closure[k]==checked[k]for k in ("files","closure_sha256","total_bytes")),"Captured actual adaptive source")
            else:
                path=Path(artifact["path"]).absolute()
                need(path.is_relative_to(Path(output).absolute()),"Runtime output custody namespace")
                read(path,16_000_000,artifact)
        from .custody import capture_operation
        return capture_operation(output,request,self.selection,self.root)

def capture_submission(root,manifest,binding,setting,pre_data_evidence):
    exact(manifest,["schema","files","entrypoints","family_policy","campaign_agent_policy","dependencies"])
    need(manifest["schema"]=="n097-submitted-program-v1","Actual submitted source programme")
    closure={**bind_source(root,manifest["files"]),"root":str(Path(root).absolute())}
    files={x["path"]for x in manifest["files"]}
    needed=("train","predict")if setting["mode"]=="F"else("investigate","query_analysis")
    need(set(manifest["entrypoints"])==set(needed)and all(manifest["entrypoints"][k]in files for k in needed),"Complete F/I source entry surface")
    need(manifest["family_policy"]and manifest["campaign_agent_policy"]and manifest["dependencies"],"Prespecified policy/dependency closure")
    need(pre_data_evidence["no_evaluation_views_exposed"]is True,"F source/I policy seals precede evaluation views")
    return {"schema":"n097-learner-seal-v1","contract":binding,"setting":setting,"source_closure":closure,
            "entrypoints":manifest["entrypoints"],"family_policy":manifest["family_policy"],
            "campaign_agent_policy":manifest["campaign_agent_policy"],"dependencies":manifest["dependencies"],
            "pre_data_controller_evidence":pre_data_evidence}

def request(seal,operation,inputs,remaining,runtime_environment,episode,query=None):
    need(operation in ("train","investigate","predict","query_analysis","query_execute","reference_train","reference_predict","interpret"),"Declared operation")
    need(query is None or operation in ("predict","query_analysis","query_execute","reference_predict"),"Query absent during fitting")
    if "knowledge_view"in seal:
        inputs=[*inputs,{"role":"knowledge_view","artifact":seal["knowledge_view"]}]
    return {"schema":"n097-worker-request-v1","contract":seal["contract"],"operation":operation,
            "source_closure":seal["source_closure"],"entrypoints":seal["entrypoints"],
            "protected_job":seal["protected_job"],"protected_binding":seal["protected_binding"],
            "inputs":inputs,"budget_remaining":remaining,"runtime_environment":runtime_environment,
            "opaque_episode_nonce":episode,"opaque_query_nonce":query,
            "family_policy":seal["family_policy"],"dependencies":seal["dependencies"],
            "mount_rules":{"sources":"read_only","training_state":"read_only","queries":0 if query is None else 1,
                           "other_folds":False,"private_targets_references":False,"network":False},
            "worker_view":{"schema":"n097-untrusted-worker-view-v1","contract":seal["contract"],"operation":operation,
                           "opaque_episode_nonce":episode,"opaque_query_nonce":query,
                           "input_root":"/inputs","source_root":"/programme","state_root":"/state","output_root":"/work/results",
                           "condition":seal.get("setting",{"access":"REFERENCE","mode":"FIXED","seed":97097}),
                           "family_policy":seal["family_policy"],
                           "public_inputs":"Runtime must project each capability to neutral fixed mount names; operator paths, global job/person/half IDs and private joins never enter worker views."},
            "model_tool_policy":"Only qualified controller-mediated tools within this isolated operation; no provider/credential handling in this programme."}


def initial_budget(resource_contract, authoring_share=None):
    """Exact public resource names -> runtime counters, without a new ceiling."""
    b=dict(resource_contract["future_evaluation_envelope_not_authorization"]["per_fold_arm_access_mode_seed"])
    b["cpu_seconds"]=b.pop("total_descendant_cpu_seconds")
    if authoring_share is not None:
        need(authoring_share["independently_qualified"]is True,"Observed original authoring allocation required")
        for k in("cpu_seconds","wall_seconds","model_input_tokens","model_output_tokens","tool_calls"):
            v=authoring_share["allocated_resources"][k]
            need(type(v)in(int,float)and 0<=v<=b[k],"Nonnegative observed authoring share within same envelope")
            b[k]-=v
    return b

def spend(remaining,receipt):
    out=dict(remaining)
    additive=("cpu_seconds","wall_seconds","model_input_tokens","model_output_tokens","tool_calls")
    for k in additive:
        out[k]-=receipt["resources"][k]
        need(out[k]>=0,"Cumulative fold budget; clones do not reset it")
    return out

def train_and_query(runtime,seal,train_input,query_inputs,state_output,job_root,budget):
    """Actual source-driven F/I sequence. No fixed-reference wrapper substitution."""
    require_deployment()
    root=Path(job_root);need(not root.exists(),"Fresh isolated job root");root.mkdir(parents=True)
    mode=seal["setting"]["mode"];op="train"if mode=="F"else"investigate"
    episode=train_input["opaque_episode_nonce"]
    first=request(seal,op,[train_input],budget,runtime.selection["environment"],episode)
    train=runtime.launch(first,root/"training")
    receipt=train["runtime_receipt"];need(receipt["status"]=="complete","Training failure retained, not silently retried")
    budget=spend(budget,receipt)
    state=receipt["training_state_identity"];need(state and state["sealed_before_query"]is True,"Actual immutable trained-state closure")
    outcomes=[];operations=[train]
    for ordinal,query in enumerate(query_inputs):
        # Each launch is a fresh qualified clone; no candidate sees other queries.
        qid=query["opaque_query_nonce"]
        inputs=[{"training_state":state},query]
        qop="predict"if mode=="F"else"query_analysis"
        req=request(seal,qop,inputs,budget,runtime.selection["environment"],episode,qid)
        analysis=runtime.launch(req,root/f"query-{ordinal:06d}-analysis")
        operations.append(analysis);rr=analysis["runtime_receipt"];budget=spend(budget,rr)
        need(rr["training_state_identity"]==state,"No query-induced frozen-state replacement")
        if mode=="I":
            source=rr["outputs"].get("query_program")
            need(source and source["actual_source_closure"]and source["entrypoint"],"Capture real adaptive query programme")
            adaptive={**seal,"source_closure":source["actual_source_closure"],"entrypoints":{"query_execute":source["entrypoint"]}}
            req=request(adaptive,"query_execute",inputs,budget,runtime.selection["environment"],episode,qid)
            execution=runtime.launch(req,root/f"query-{ordinal:06d}-execution")
            operations.append(execution);rr=execution["runtime_receipt"];budget=spend(budget,rr)
            need(rr["training_state_identity"]==state,"Adaptive query programme only probes frozen states")
        outcomes.append({"query":qid,"status":rr["status"],"prediction_artifact":rr["outputs"].get("prediction"),
                         "failure_reasons":rr["failure_reasons"],"runtime_receipt_identity":identity(canonical(rr))})
    result={"schema":"n097-controlled-fold-collection-v1","seal":seal,"training_state":state,
            "outcomes":outcomes,"operations":operations,"budget_remaining":budget,"engineering_only":False}
    write_json(root/"FOLD_COLLECTION.json",result,32_000_000)
    return result


def capture_interpreter(root,manifest,binding,condition_id,prediction_report_identity):
    exact(manifest,["schema","files","entrypoints","family_policy","campaign_agent_policy","dependencies"])
    need(manifest["schema"]=="n097-submitted-interpretation-v1"and set(manifest["entrypoints"])=={"interpret"},"Actual separate interpretation programme")
    closure={**bind_source(root,manifest["files"]),"root":str(Path(root).absolute())}
    need(manifest["entrypoints"]["interpret"]in{r["path"]for r in manifest["files"]},"Interpreter source captured")
    from .contract import condition
    a,m,seed=condition_id.split("-");seed=int(seed);need(condition(a,m,seed)==condition_id,"Exact original interpretation setting")
    return {"schema":"n097-interpretation-seal-v1","contract":binding,"condition":condition_id,"setting":{"access":a,"mode":m,"seed":seed},
            "source_closure":closure,"entrypoints":manifest["entrypoints"],"family_policy":manifest["family_policy"],
            "campaign_agent_policy":manifest["campaign_agent_policy"],"dependencies":manifest["dependencies"],
            "after_prediction_report":prediction_report_identity}
