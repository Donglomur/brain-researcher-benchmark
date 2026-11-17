"""Concrete central routes into the full authorized V4 stage implementation."""
import hashlib,os
from pathlib import Path
from owner.io import Artifact,ArtifactStore,ByteMeter,ContractError,capture,decode,ordinary
from owner.cli import _keys
from owner.evidence import verify,issue
from owner.workflow import run_stage
from owner.worker import bounded_runner
from .source import load_source
from .method import validate_method,bind_actual_method,bind_attempt,method_identity

DEPLOYMENT_FIELDS={"schema","status","keyring","issuers","output_root","minimum_other_reserve_bytes"}
REVIEW_FIELDS={"operation","action","stage","method_sha256","request","output","other_reserve_bytes",
              "deployment_sha256","consent_record"}

def load_deployment(path,sha,meter):
    body=capture(path,65536,meter=meter)
    if hashlib.sha256(body).hexdigest()!=sha:raise ContractError("exact selected deployment metadata required")
    value=decode(body)
    if not isinstance(value,dict) or set(value)!=DEPLOYMENT_FIELDS or value["schema"]!="neural063_deployment_v1":
        raise ContractError("closed deployment metadata required")
    if value["status"]!="independently_configured":raise ContractError("deployment unconfigured; no method, key, model or source-data body admitted")
    keyring=Artifact.parse(value["keyring"])
    if keyring.role!="operator_keyring" or keyring.visibility!="operator" or not 0<keyring.bytes<=65536:
        raise ContractError("bounded separately provisioned operator keyring required")
    if (set(value["issuers"])!={"authorization","allocation","implementation_runtime","completion"} or
            len(set(value["issuers"].values()))!=4 or type(value["minimum_other_reserve_bytes"]) is not int or value["minimum_other_reserve_bytes"]<0):
        raise ContractError("independent issuer roles and finite extra-reserve policy required")
    return value,keyring

def execute(action,method_path,output,review_path,deployment_path,deployment_sha,other_reserve_bytes):
    source=load_source();meter=ByteMeter(8*1024*1024,1024*1024)
    deployment,keyring=load_deployment(deployment_path,deployment_sha,meter)
    method_bytes=capture(method_path,65536,meter=meter);method=decode(method_bytes)
    request=validate_method(method,source);spec=decode(capture(request.path,4_000_000,descriptor=request,meter=meter))
    stage=spec.get("stage");route=next((name for name,stages in source["routes"].items() if stage in stages),None)
    if route is None or (action!="run" and action!=route):raise ContractError("command does not admit this exact graph stage")
    if spec.get("implementation")!=source["manifest"].object():raise ContractError("request must bind actual portable executing source")
    if spec.get("issuers")!=deployment["issuers"] or spec.get("output_root")!=deployment["output_root"]:
        raise ContractError("stage request differs from selected deployment issuer/output binding")
    root=ordinary(spec["output_root"],directory=True);st=root.stat()
    if st.st_uid!=os.geteuid() or st.st_mode&0o077:raise ContractError("private owned output root required before any central effect")
    expected=root/"central"/(stage+".return.json")
    if Path(output).absolute()!=expected or expected.exists():raise ContractError("fresh fixed stage delivery path required")
    if type(other_reserve_bytes) is not int or other_reserve_bytes<deployment["minimum_other_reserve_bytes"]:
        raise ContractError("explicit additional reservation below deployment policy")
    review=decode(capture(review_path,65536,meter=meter))
    # Key material is accessed only for an explicitly configured invocation;
    # inspect and unconfigured default routes cannot reach this read.
    if ordinary(keyring.path).stat().st_size!=keyring.bytes:raise ContractError("keyring extent differs from explicit deployment")
    meter.read(keyring.bytes)
    keys=_keys(keyring.path,keyring.sha256)
    content=verify(review,keys=keys,expected_issuer=deployment["issuers"]["authorization"],kind="authorization",
        evidence_id="CENTRAL_STAGE",attempt=spec["attempt"],stage="ALL",implementation_sha256=source["manifest"].sha256,
        contract_sha256=source["contract_sha256"],prerequisites={})
    expected_content={"operation":"neural063_complete_central_stage","action":action,"stage":stage,
        "method_sha256":hashlib.sha256(method_bytes).hexdigest(),"request":request.object(),"output":str(expected),
        "other_reserve_bytes":other_reserve_bytes,"deployment_sha256":deployment_sha,"consent_record":content.get("consent_record")}
    consent=content.get("consent_record")
    if (set(content)!=REVIEW_FIELDS or content!=expected_content or not isinstance(consent,dict) or
            set(consent)!={"issuer_record_id","scope"} or any(not isinstance(v,str) or not v for v in consent.values())):
        raise ContractError("external review must bind exact action/method/request/source/output/reserve/deployment")
    def selected_worker(actual_spec,admitted):
        bind_actual_method(method,actual_spec,admitted)
        bind_attempt(method,actual_spec,source,deployment_sha,keys,meter)
        return bounded_runner(actual_spec,admitted)
    # Cache safe metadata before core execution. The failure return below must
    # not recompute method serialization or depend on output-root custody.
    selected_method_identity=method_identity(method)
    known_usage=meter.snapshot()
    result=run_stage(spec,keys,worker_runner=selected_worker)
    # Every subsequent observation/custody/serialization operation is optional
    # delivery of this already-known result, never a new authority decision.
    phase="observation_construction"
    closure=None
    try:
        known_usage=meter.snapshot()
        delivery={"schema":"neural063_central_stage_delivery_v1","task_id":"NEURAL-063","stage":stage,"action":action,
            "method_identity":selected_method_identity,"source_sha256":source["manifest"].sha256,"result":result,
            "central_logical_usage_before_delivery":known_usage,"source_inspection_read_bytes":source["source_reads"],
            "physical_CPU_IO_RAM":None,"delivery_tail_seconds":None,"scientific_qualification_inferred":False,
            "cost_policy":"Additional central authentication/method custody/delivery is common controller cost, separate from stage usage; unknown physical and final delivery tails are never zero-imputed."}
        phase="cost_closure"
        from .costs import prior_closure,envelope_payload
        if stage=="E02":
            closure=prior_closure(spec,source,keys,meter,selected_method_identity)
            delivery["complete_central_common_cost_closure"]=closure
            known_usage=meter.snapshot()
            delivery["central_logical_usage_before_delivery"]=known_usage
        phase="store_construction"
        store=ArtifactStore(root,meter)
        phase="directory_custody"
        store.mkdir("central")
        phase="serialization_signing_and_write"
        delivered=store.json("central/"+stage+".return.json",
            issue(envelope_payload(delivery,spec,source),keys[spec["issuers"]["completion"]]),
            role="signed_central_delivery_observation",visibility="operator",producer="central")
        phase="delivery_descriptor"
        descriptor=delivered.object()
        known_usage=meter.snapshot()
        return {"status":"delivered","delivery":descriptor,"result":result,"central_usage":known_usage,
                "terminal_authority_changed":False}
    except BaseException as exc:
        # Retain the original core return, never arbitrary exception messages,
        # private method/request/key bodies, or a fabricated delivery descriptor.
        usage_status="observed_after_delivery_failure"
        try:known_usage=meter.snapshot()
        except BaseException:usage_status="last_known_snapshot; later usage unavailable"
        return {"status":"delivery_unavailable","result":result,"delivery_error_type":type(exc).__name__,
                "delivery_failure_phase":phase,"terminal_authority_changed":False,
                "method_identity":selected_method_identity,"central_usage":known_usage,
                "central_usage_observation_status":usage_status,"source_inspection_read_bytes":source["source_reads"],
                "complete_central_common_cost_closure":closure,"unobserved_delivery_or_physical_costs":None}
