"""Signed, non-authoritative central overhead; missing observations stay unknown."""
import time
from pathlib import Path
from owner.io import Artifact,ContractError,capture,decode
from owner.evidence import verify

def bindings(source,spec,stage):
    return {"DONE_"+dep:Artifact.parse(spec["completions"][dep]).sha256 for dep in source["contract"]["nodes"][stage]["depends_on"]}

def envelope_payload(content,spec,source):
    now=int(time.time())
    return {"schema":"neural063_evidence_v1","issuer":spec["issuers"]["completion"],"kind":"publication_observation",
        "evidence_id":"CENTRAL_COST_"+spec["stage"],"attempt":spec["attempt"],"stage":spec["stage"],
        "implementation_sha256":source["manifest"].sha256,"contract_sha256":source["contract_sha256"],
        "prerequisites":bindings(source,spec,spec["stage"]),"issued_at":now,
        "expires_at":max(spec["attempt_expires_at"],now+86400),"content":content}

def prior_closure(spec,source,keys,meter,method_id):
    if spec["stage"]!="E02":raise ContractError("complete central cost closure belongs to E02")
    records={};unknown=[];read=written=inspection=0
    for stage in source["contract"]["order"]:
        if stage=="E02":continue
        try:
            path=Path(spec["output_root"])/"central"/(stage+".return.json")
            cap=min(262144,max(0,meter.read_limit-meter.read_bytes))
            content=verify(decode(capture(path,cap,meter=meter)),keys=keys,expected_issuer=spec["issuers"]["completion"],
                kind="publication_observation",evidence_id="CENTRAL_COST_"+stage,attempt=spec["attempt"],stage=stage,
                implementation_sha256=source["manifest"].sha256,contract_sha256=source["contract_sha256"],prerequisites=bindings(source,spec,stage))
            if (content.get("schema")!="neural063_central_stage_delivery_v1" or content.get("stage")!=stage or
                    content.get("method_identity")!=method_id or content.get("result",{}).get("receipt")!=spec["completions"][stage]):
                raise ContractError("central cost observation differs from exact committed predecessor/method")
            usage=content.get("central_logical_usage_before_delivery",{});values=[usage.get("logical_read_bytes"),usage.get("logical_write_bytes"),content.get("source_inspection_read_bytes")]
            if any(type(v) is not int or v<0 for v in values):raise ContractError("typed nonnegative observed central counters required")
            read+=values[0];written+=values[1];inspection+=values[2]
            records[stage]={"status":"authenticated_observed_part","counters_before_delivery":usage,"source_inspection_read_bytes":values[2],"self_delivery_and_physical_tail":None}
        except Exception as exc:
            unknown.append(stage);records[stage]={"status":"unavailable","reason":type(exc).__name__+": "+str(exc)[:512],"counters":None}
    return {"schema":"neural063_central_common_cost_closure_v1","prior_stages":records,"missing_prior_observations":unknown,
        "known_prior_central_logical_read_bytes":read,"known_prior_central_logical_write_bytes":written,
        "known_prior_source_inspection_read_bytes":inspection,"current_E02_counters":"separate enclosing observation",
        "complete_physical_or_delivery_total":None,"terminal_authority_changed":False,
        "policy":"Authenticated known parts only; each immutable observation precedes its own delivery. Missing/lost/invalid records and physical/delivery tails remain unknown. Never add these to overlapping counters or call them a complete physical cost total."}
