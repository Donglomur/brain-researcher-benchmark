"""Full-method admission and immutable attempt-local method identity."""
import hashlib,time
from pathlib import Path
from owner.io import Artifact,ArtifactStore,ContractError,canonical,capture,decode
from owner.evidence import issue,verify
from .source import SCOPE,CONDITIONS,PROFILE

FIELDS={"schema","task_id","profile","scope","conditions","stage_order","implementation_sha256",
        "contract_sha256","assets","recipes","request"}

def method_identity(method):
    return hashlib.sha256(canonical({k:v for k,v in method.items() if k!="request"})).hexdigest()

def validate_method(method,source):
    if (not isinstance(method,dict) or set(method)!=FIELDS or method["schema"]!="neural063_complete_method_v1" or
            method["task_id"]!="NEURAL-063" or method["profile"]!=PROFILE or method["scope"]!=SCOPE or
            method["conditions"]!=CONDITIONS or method["stage_order"]!=source["contract"]["order"] or
            method["implementation_sha256"]!=source["manifest"].sha256 or method["contract_sha256"]!=source["contract_sha256"]):
        raise ContractError("exact complete method/source/scope/condition/stage binding required")
    if set(method["assets"])!={"checkpoint","tokenizer","model_runtime"} or set(method["recipes"])!={"development","report"}:
        raise ContractError("complete shared method assets and development/report recipes required")
    for name,value in method["assets"].items():
        ref=Artifact.parse(value)
        if ref.role!=name or ref.visibility!="operator":raise ContractError("operator asset descriptor required")
    for name,role in (("development","candidate_development_recipe"),("report","report_recipe")):
        ref=Artifact.parse(method["recipes"][name])
        if ref.role!=role or ref.visibility!="operator":raise ContractError("exact protected recipe descriptor required")
    request=Artifact.parse(method["request"])
    if request.role!="stage_request" or request.visibility!="operator" or request.bytes>4_000_000:
        raise ContractError("bounded operator stage request metadata required")
    return request

def bind_actual_method(method,spec,admitted):
    """Called only after actual stage authorization, before the bounded worker."""
    stage=spec["stage"];past=admitted["receipts"]
    development=spec["inputs"] if stage=="D00" else past.get("D00",{}).get("input_descriptors")
    report=spec["inputs"] if stage=="N00" else past.get("N00",{}).get("input_descriptors")
    for inputs,recipe,label in ((development,"development","candidate_development_recipe"),(report,"report","report_recipe")):
        if inputs is not None:
            if inputs.get(label)!=method["recipes"][recipe]:raise ContractError("actual authorized recipe differs from complete method")
            if any(inputs.get(k)!=v for k,v in method["assets"].items()):raise ContractError("actual authorized model assets differ from complete method")
    if stage in {"D01","Q00","Q01","Q02","Q03","N00","E00","E01","E02"} and development is None:
        raise ContractError("signed actual D00 method lineage missing")

def bind_attempt(method,spec,source,deployment_sha,keys,meter):
    store=ArtifactStore(spec["output_root"],meter);store.mkdir("central")
    path=Path(spec["output_root"])/"central"/"method.json"
    content={"method_identity":method_identity(method),"deployment_sha256":deployment_sha,
             "complete_method":{k:v for k,v in method.items() if k!="request"}}
    issuer=spec["issuers"]["authorization"]
    if path.exists():
        observed=verify(decode(capture(path,65536,meter=meter)),keys=keys,expected_issuer=issuer,kind="authorization",
            evidence_id="CENTRAL_METHOD",attempt=spec["attempt"],stage="ALL",implementation_sha256=source["manifest"].sha256,
            contract_sha256=source["contract_sha256"],prerequisites={})
        if observed!=content:raise ContractError("attempt cannot change its selected complete method")
    else:
        payload={"schema":"neural063_evidence_v1","issuer":issuer,"kind":"authorization","evidence_id":"CENTRAL_METHOD",
            "attempt":spec["attempt"],"stage":"ALL","implementation_sha256":source["manifest"].sha256,
            "contract_sha256":source["contract_sha256"],"prerequisites":{},"issued_at":int(time.time()),
            "expires_at":spec["attempt_expires_at"],"content":content}
        store.json("central/method.json",issue(payload,keys[issuer]),role="central_method_binding",visibility="operator",producer="central")
    return content["method_identity"]
